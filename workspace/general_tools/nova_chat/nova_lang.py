"""
nova_chat/nova_lang.py -- Nova Command Language (NCL) Parser
============================================================
Parses Nova's structured module calls from Nova Chat messages into an
executable task graph (parallel groups containing sequential chains).

NCL Tokens (full reference in workspace/NCL_MASTER.md):
  @role           Call to an AI module — @eyes, @mentor, @thinkorswim, ...
  <<file.md>>     Context file to inject into the module's system prompt.
                  Single brackets <file.md> also accepted (backward compat).
  [[instructions]] Nova's specific instructions for this call
  ((criteria))    Completion criteria + optional Task ID for inbox routing
                  Format: ((task_id:TASKNAME; what must be returned))
  ;;              Separator between PARALLEL role groups (run concurrently)
  ::              Pipe — SEQUENTIAL steps within one chain (run in order)
  **text**        Emphasis — marks critical info Nova wants highlighted
  >>target        Output routing — where the module writes its result
  $$prev          Reference to the previous step's output in a :: chain
  %%N             Timeout in seconds before a call is considered failed

Fixed orchestrator names (Claude, Gemini, Nova, mentor, all) are NOT parsed
as NCL module calls — they route through the normal orchestrator instead.

Usage:
    from nova_chat.nova_lang import parse_ncl, summarize_ncl

    result = parse_ncl(message_text)
    if result:
        print(summarize_ncl(result))
        for group in result.parallel_groups:
            for chain in group.chains:
                for step in chain.steps:
                    print(step.role, step.instructions, step.criteria)
"""
import re
from dataclasses import dataclass, field
from typing import Optional


# ── Token patterns ──────────────────────────────────────────────────────────

_ROLE_RE     = re.compile(r'@(\w+)', re.IGNORECASE)

# <<file.md>> preferred; <file.md> accepted for backward compat
# The single-bracket form only matches if it ends in a recognized extension
_CONTEXT_RE  = re.compile(
    r'<<([^>]+?)>>'                       # <<double>>
    r'|(?<![<])<([^<>\s]+\.(?:md|txt|json|jsonl|py|yaml|yml))>(?![>])',  # <single.ext>
    re.IGNORECASE,
)

_INSTR_RE    = re.compile(r'\[\[(.+?)\]\]',   re.DOTALL)   # [[instructions]]
_CRITERIA_RE = re.compile(r'\(\((.+?)\)\)',   re.DOTALL)   # ((criteria))
_OUTPUT_RE   = re.compile(r'>>(\S+)')                       # >>path/to/target
_PREV_RE     = re.compile(r'\$\$prev',        re.IGNORECASE)
_TIMEOUT_RE  = re.compile(r'%%(\d+)')                       # %%30
_EMPHASIS_RE = re.compile(r'\*\*(.+?)\*\*')                # **text**

# These names are handled by the orchestrator's participant/alias system and
# have NO module identity — they should never be parsed as NCL module calls.
# @mentor is intentionally excluded here: it IS a registered NCL module (that
# internally routes to Claude + Gemini), so it must be parseable as a module call.
# Stored lowercase for case-insensitive comparison.
_ORCHESTRATOR_NAMES = frozenset({"claude", "gemini", "nova", "all"})


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class Criteria:
    """Parsed ((criteria)) block."""
    task_id: str       # Empty string if no task_id: prefix was given
    description: str   # The completion requirement text


@dataclass
class ModuleCall:
    """
    A single module call — one @role with all its inline modifiers parsed out.
    Multiple ModuleCalls chained with :: form a ChainGroup.
    """
    role: str                                              # "eyes", "mentor", etc. (no @)
    context_files: list[str]  = field(default_factory=list)   # <<file.md>> paths
    instructions:  str        = ""                              # [[content]]
    criteria:      Optional[Criteria] = None                   # ((criteria))
    output_target: str        = ""                              # >>path
    uses_prev:     bool       = False                           # $$prev present
    timeout_s:     Optional[int] = None                        # %%N
    emphasis:      list[str]  = field(default_factory=list)    # **text** items
    raw:           str        = ""                              # original text


@dataclass
class ChainGroup:
    """
    A :: chain — one or more ModuleCalls executed in strict sequence.
    Each step can reference the previous step's output via $$prev.
    """
    steps: list[ModuleCall] = field(default_factory=list)


@dataclass
class ParallelGroup:
    """
    A ;; parallel group — one or more ChainGroups that execute concurrently.
    In the current implementation each parallel group contains exactly one chain;
    future versions may fan out multiple chains per group.
    """
    chains: list[ChainGroup] = field(default_factory=list)


@dataclass
class NCLCall:
    """Top-level result of parse_ncl(). Represents the full task graph."""
    parallel_groups: list[ParallelGroup]
    raw:             str
    is_ncl:          bool       = True
    all_task_ids:    list[str]  = field(default_factory=list)


# ── Internal helpers ─────────────────────────────────────────────────────────

def _parse_criteria(raw: str) -> Criteria:
    """
    Parse the inner text of a ((criteria)) block.

    Formats supported:
        task_id:TASKNAME; what must be returned
        task_id:TASKNAME;what must be returned
        just a plain description with no task_id
    """
    raw = raw.strip()
    m = re.match(r'task_id\s*:\s*(\S+?)\s*;+\s*(.+)', raw, re.DOTALL | re.IGNORECASE)
    if m:
        return Criteria(
            task_id=m.group(1).strip(),
            description=m.group(2).strip(),
        )
    return Criteria(task_id="", description=raw)


def _parse_segment(text: str) -> ModuleCall:
    """
    Parse one segment of text (split by ::) into a ModuleCall.
    A segment should contain exactly one @role and its modifiers.
    """
    text = text.strip()

    # @role — first non-orchestrator name wins
    role = "unknown"
    for m in _ROLE_RE.finditer(text):
        if m.group(1).lower() not in _ORCHESTRATOR_NAMES:
            role = m.group(1).lower()
            break

    # <<context_files>>
    context_files: list[str] = []
    for m in _CONTEXT_RE.finditer(text):
        f = m.group(1) or m.group(2)
        if f:
            context_files.append(f.strip())

    # [[instructions]] — use the LAST match (most specific override wins)
    instructions = ""
    instr_all = _INSTR_RE.findall(text)
    if instr_all:
        instructions = instr_all[-1].strip()

    # ((criteria)) — use the LAST match
    criteria: Optional[Criteria] = None
    crit_all = _CRITERIA_RE.findall(text)
    if crit_all:
        criteria = _parse_criteria(crit_all[-1])

    # >>output_target
    output_target = ""
    out_m = _OUTPUT_RE.search(text)
    if out_m:
        output_target = out_m.group(1).strip()

    # $$prev
    uses_prev = bool(_PREV_RE.search(text))

    # %%timeout
    timeout_s: Optional[int] = None
    to_m = _TIMEOUT_RE.search(text)
    if to_m:
        try:
            timeout_s = int(to_m.group(1))
        except ValueError:
            pass

    # **emphasis**
    emphasis = _EMPHASIS_RE.findall(text)

    return ModuleCall(
        role=role,
        context_files=context_files,
        instructions=instructions,
        criteria=criteria,
        output_target=output_target,
        uses_prev=uses_prev,
        timeout_s=timeout_s,
        emphasis=emphasis,
        raw=text,
    )


def _parse_chain(chain_text: str) -> ChainGroup:
    """
    Parse a :: chain. Splits on :: and parses each segment individually.
    Returns a ChainGroup with steps in execution order.
    """
    # Split on :: but not inside [[ ]] or (( )) blocks
    # Simple approach: split on standalone :: (surrounded by whitespace or line bounds)
    segments = re.split(r'\s*::\s*', chain_text)
    steps = []
    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue
        # Only include segments that have at least one non-orchestrator @role
        roles = [m.group(1) for m in _ROLE_RE.finditer(seg)
                 if m.group(1).lower() not in _ORCHESTRATOR_NAMES]
        if roles:
            steps.append(_parse_segment(seg))
    return ChainGroup(steps=steps)


# ── Public API ────────────────────────────────────────────────────────────────

def parse_ncl(message: str) -> Optional[NCLCall]:
    """
    Parse a Nova Chat message for NCL content.

    Returns an NCLCall if the message contains any @module mentions that are
    not standard orchestrator names (Claude / Gemini / Nova / mentor / all).
    Returns None if no NCL content is found.

    The returned NCLCall contains the full task graph:
        parallel_groups → chains → steps (ModuleCalls)

    Parallel groups (;; separator) can run concurrently.
    Steps within a chain (:: separator) must run sequentially.
    """
    # Fast path: any non-orchestrator @mentions at all?
    has_module = any(
        m.group(1).lower() not in _ORCHESTRATOR_NAMES
        for m in _ROLE_RE.finditer(message)
    )
    if not has_module:
        return None

    # Split on ;; into parallel blocks
    parallel_blocks = re.split(r'\s*;;\s*', message)
    groups: list[ParallelGroup] = []
    all_task_ids: list[str] = []

    for block in parallel_blocks:
        block = block.strip()
        if not block:
            continue

        # Skip blocks with no module mentions (e.g. preamble text)
        block_modules = [m.group(1) for m in _ROLE_RE.finditer(block)
                         if m.group(1).lower() not in _ORCHESTRATOR_NAMES]
        if not block_modules:
            continue

        chain = _parse_chain(block)
        if not chain.steps:
            continue

        # Collect task IDs (deduplicated, ordered)
        for step in chain.steps:
            if step.criteria and step.criteria.task_id:
                tid = step.criteria.task_id
                if tid not in all_task_ids:
                    all_task_ids.append(tid)

        groups.append(ParallelGroup(chains=[chain]))

    if not groups:
        return None

    return NCLCall(
        parallel_groups=groups,
        raw=message,
        all_task_ids=all_task_ids,
    )


def summarize_ncl(call: NCLCall) -> str:
    """
    One-line human-readable summary of an NCLCall.
    Used for logging and Nova Chat system notices.

    Example output:
        @eyes +1ctx [TradeCheck_0328] ;; @thinkorswim +1ctx [TradeCheck_0328]
    """
    group_parts: list[str] = []
    for group in call.parallel_groups:
        chain_parts: list[str] = []
        for chain in group.chains:
            step_parts: list[str] = []
            for step in chain.steps:
                desc = f"@{step.role}"
                if step.context_files:
                    desc += f" +{len(step.context_files)}ctx"
                if step.criteria and step.criteria.task_id:
                    desc += f" [{step.criteria.task_id}]"
                if step.output_target:
                    desc += f" >>{step.output_target}"
                if step.timeout_s:
                    desc += f" %%{step.timeout_s}"
                step_parts.append(desc)
            chain_parts.append(" :: ".join(step_parts))
        group_parts.append(" | ".join(chain_parts))
    return " ;; ".join(group_parts)


def extract_module_names(message: str) -> list[str]:
    """
    Extract unique module names from a message, filtering out orchestrator names.
    Returns names in order of first appearance, preserving original casing.

    Used by orchestrator.py to check whether a message contains NCL calls.
    """
    seen: set[str] = set()
    result: list[str] = []
    for m in _ROLE_RE.finditer(message):
        name = m.group(1)
        if name.lower() not in _ORCHESTRATOR_NAMES and name.lower() not in seen:
            seen.add(name.lower())
            result.append(name)
    return result


def ncl_to_dict(call: NCLCall) -> dict:
    """
    Serialize an NCLCall to a plain dict (JSON-serializable).
    Useful for logging, debugging, and passing to downstream tools.
    """
    def crit_dict(c: Optional[Criteria]) -> Optional[dict]:
        if c is None:
            return None
        return {"task_id": c.task_id, "description": c.description}

    def step_dict(s: ModuleCall) -> dict:
        return {
            "role": s.role,
            "context_files": s.context_files,
            "instructions": s.instructions,
            "criteria": crit_dict(s.criteria),
            "output_target": s.output_target,
            "uses_prev": s.uses_prev,
            "timeout_s": s.timeout_s,
            "emphasis": s.emphasis,
        }

    def chain_dict(c: ChainGroup) -> dict:
        return {"steps": [step_dict(s) for s in c.steps]}

    def group_dict(g: ParallelGroup) -> dict:
        return {"chains": [chain_dict(c) for c in g.chains]}

    return {
        "is_ncl": call.is_ncl,
        "all_task_ids": call.all_task_ids,
        "parallel_groups": [group_dict(g) for g in call.parallel_groups],
        "summary": summarize_ncl(call),
    }
