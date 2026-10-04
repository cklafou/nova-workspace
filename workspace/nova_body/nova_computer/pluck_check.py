# Last updated: 2026-10-04 13:57:45
# @nova: Proof, not a promise. Run this with only my body on the path and it tells you whether
#        my computer is really mine -- or whether it was quietly leaning on a tool the whole time.
# @claude 2026-09-03: Design_Principles #4 says verify against ground truth, not a claim, and #5
# says a change is not done because it compiled. nova_computer's docstring ASSERTED "pluck-safe,
# stdlib only" while the code held a Windows-only subprocess flag that raises ValueError on
# POSIX. A claim in a comment is not a test. This is the test.
"""
nova_computer.pluck_check -- does her computer survive the pluck?

    cd nova_body && python -m nova_computer.pluck_check
    cd nova_body && python -m nova_computer.pluck_check --live    # also run real commands

Checks, in order:
  1. IMPORT PURITY   every module in the package imports only stdlib or her own body
  2. NO TOOLS LOADED nothing from general_tools ends up in sys.modules
  3. PROBE           a backend is chosen for THIS host, and names itself honestly
  4. DEGRADATION     with no computer at all, the faculty answers instead of exploding
  5. LIVE (opt-in)   bash and pwsh actually run where she is standing
Exit code 0 = pluck passed.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent
BODY = PKG.parent
_STDLIB = set(getattr(sys, "stdlib_module_names", ()))


def _is_stdlib(name: str) -> bool:
    """Python >= 3.10 publishes the list. Older hosts do not, and a pluck test that flags
    `import os` as third-party on an old machine is lying. Fall back to asking where the
    module actually lives."""
    if _STDLIB:
        return name in _STDLIB
    if name in sys.builtin_module_names:
        return True
    import importlib.util
    import sysconfig
    try:
        spec = importlib.util.find_spec(name)
    except Exception:
        return False
    origin = getattr(spec, "origin", None) or ""
    std = sysconfig.get_paths().get("stdlib", "")
    return origin == "built-in" or (bool(std) and origin.startswith(std)
                                    and "site-packages" not in origin)
# Her own body is not a foreign dependency -- it is the thing being plucked.
OWN_PREFIXES = ("nova_computer", "nova_senses", "nova_memory", "nova_logs", "nova_cortex",
                "nova_runtime", "nova_config", "nova_lancedb", "nova_voice", "nova_witness",
                "nova_play", "nova_forge", "nova_imagination")
FORBIDDEN = ("general_tools", "nova_chat", "tool_router")

_ok = True


def report(passed: bool, label: str, detail: str = "") -> None:
    global _ok
    _ok = _ok and passed
    print(f"  [{'PASS' if passed else 'FAIL'}] {label}" + (f" - {detail}" if detail else ""))


def module_names(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield a.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            if node.level:            # relative import: inside her own package
                continue
            if node.module:
                yield node.module.split(".")[0]


def check_import_purity() -> None:
    print("1. IMPORT PURITY - only stdlib and her own body")
    foreign: dict[str, set[str]] = {}
    tools: dict[str, set[str]] = {}
    for py in sorted(PKG.glob("*.py")):
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except Exception as e:
            report(False, py.name, f"will not parse: {e}")
            continue
        for name in module_names(tree):
            if name.startswith(FORBIDDEN):
                tools.setdefault(py.name, set()).add(name)
            elif name.startswith(OWN_PREFIXES):
                continue                      # her own body is not a foreign dependency
            elif not _is_stdlib(name):
                foreign.setdefault(py.name, set()).add(name)
    report(not tools, "no tool imports",
           "; ".join(f"{f}: {sorted(v)}" for f, v in tools.items()) or "clean")
    report(not foreign, "no third-party imports",
           "; ".join(f"{f}: {sorted(v)}" for f, v in foreign.items()) or "stdlib only")


def check_no_tools_loaded() -> None:
    print("2. NO TOOLS LOADED - importing her computer pulls in nothing from general_tools")
    import nova_computer.computer  # noqa: F401
    leaked = sorted(m for m in sys.modules if m.startswith(FORBIDDEN))
    report(not leaked, "sys.modules stays clean", ", ".join(leaked) or "no tool modules present")


def check_probe():
    print("3. PROBE - which computer does she have HERE?")
    from nova_computer.computer import NovaComputer
    pc = NovaComputer()
    name = pc.backend.name
    print(f"       backend: {name}")
    print(f"       where:   {pc.where()}")
    report(True, "faculty answered", f"backend={name}")
    if name == "none":
        print("       (no computer on this host - that is a coherent answer, not a failure)")
    return pc


def check_degradation() -> None:
    print("4. DEGRADATION - with no computer at all, does she answer or explode?")
    from nova_computer.backends import NoBackend
    from nova_computer.computer import NovaComputer, ComputerUnavailable
    pc = NovaComputer()
    pc.backend = NoBackend()
    try:
        rc, out = pc.bash("echo should-not-run")
        report(rc != 0 and "no computer available" in out.lower(),
               "bash() reports absence instead of raising", f"rc={rc}")
    except Exception as e:
        report(False, "bash() raised instead of reporting", repr(e))
    try:
        pc.ensure()
        report(False, "ensure() should refuse when there is no computer")
    except ComputerUnavailable as e:
        report(True, "ensure() refuses with a reason", str(e)[:60] + "...")
    except Exception as e:
        report(False, "ensure() raised the wrong error type", repr(e))


def check_live(pc) -> None:
    print("5. LIVE - can she actually act where she is standing?")
    if pc.backend.name == "none":
        report(True, "skipped", "no computer here to act in")
        return
    rc, out = pc.bash("echo pluck-alive && uname -a && whoami")
    report(rc == 0 and "pluck-alive" in out, "bash runs", (out.splitlines() or [""])[0][:70])
    rc, out = pc.pwsh("'pwsh ' + $PSVersionTable.PSVersion.ToString()")
    if rc == 0:
        report(True, "pwsh runs", out.strip()[:60])
    else:
        print(f"  [note] pwsh unavailable here: {out.strip()[:80]}")


def main() -> int:
    if str(BODY) not in sys.path:
        sys.path.insert(0, str(BODY))
    print(f"PLUCK CHECK - nova_computer\n  body: {BODY}\n  python: {sys.version.split()[0]} "
          f"on {sys.platform}\n")
    check_import_purity()
    check_no_tools_loaded()
    pc = check_probe()
    check_degradation()
    if "--live" in sys.argv:
        check_live(pc)
    print(f"\nPLUCK_RESULT: {'PASS' if _ok else 'FAIL'}")
    return 0 if _ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
