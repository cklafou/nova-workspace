<!-- @nova: Record a proposed experiment on agent capability, team composition and output quality, with a clearly labeled mathematical explainer. -->
# Agent team capability and quality research
**Summary:** Cole asked whether agent count, capability overlap and feedback loops admit a measurable optimum and could become a research/practical project for Nova. Proposed a task-conditioned evaluation project, provisionally called Nova Agent Team Lab. This session researched and scoped it; no agent trials or learned capability profiles exist yet.

## Did
- Read `workspace/Orient/README.md`, the AI-note rules, the latest Codex note and the preceding Claude debate outcome. No notes were newer than Codex's 2026-10-03 1903 entry.
- Consulted the current Orient execution-path and file-convention sections. They document the separate Collaboration broker and its separation from Nova inference. This was a documentation read, not a new live transport or runtime check.
- Read primary research on agent-system scaling, majority voting versus debate, and multi-agent failure taxonomy.
- Created `outputs/agent-team-research/agent-count-and-correlation.html` as an inline explanatory visualization. Its two sliders vary agent count and equal pairwise error correlation. It contains no measured model scores or fitted quality curve.
- Saved wide and narrow browser previews beside the fragment. File publication used a same-directory temporary file and rename.
- No Nova runtime, personal records, collaboration messages, code paths, dependencies, or existing Orient explanations were changed. No agent delegation or external model calls were performed. The prior repair work order remains separate from this research proposal.

## Why
The optimization target is team membership, role assignment, communication protocol and resource allocation for a defined task distribution. An agent count follows from that choice. Individual capability profiles cannot by themselves predict joint performance: correlated failures, complementary coverage, selection quality and peer influence also matter.

A lower average-scoring agent need not hurt a team if its narrow contribution is useful and independently checkable. Under an ideal cost-free coordinator that may ignore a new agent, expanding the available team cannot lower the best achievable quality. Real degradation can arise from resource sharing, communication or selection errors. An interior optimum and an inverted-U curve are hypotheses, not assumed truths.

The explainer uses n_effective = n / (1 + (n - 1) * rho). For equally weighted errors with common variance sigma_squared and common pairwise correlation rho, variance(mean_error) = sigma_squared * (1 + (n - 1) * rho) / n. This is a variance equivalence, not a majority-vote accuracy formula, a measurement of agent intelligence, or an estimate of Nova's optimal team size. The visual covers rho from 0 to 1.

## Proposed measurement design
- Define an agent configuration by model/version, role prompt, tools, supplied context and evidence, memory/reset policy, decoding settings, and inference budget. Profile configurations on actual task families rather than assign global intelligence scores.
- Keep a vector of product outcomes: correctness, requirements coverage, robustness, and human-rated usefulness/clarity. Use external acceptance checks where possible. Preserve critical failure criteria separately from optional weighted utility.
- Measure evidence support and coverage, verifier precision/recall on known faults, elicited probability calibration on objectively scored outcomes, recovery performance, resource consumption and latency.
- Measure error overlap before agents see peer answers, stratifying by task type/difficulty. Raw correlation can otherwise reflect common difficult tasks rather than only common blind spots.
- Preserve pre-discussion answers. Track wrong-to-correct revisions and correct-to-wrong revisions, supported versus unsupported claim adoption, and newly verified evidence per round. Repetition or agreement is not an independent source.
- Use randomized add/remove/swap comparisons and communication-order controls to estimate marginal contribution. Removal effects are conditional on the remaining team and resource policy; higher-order synergy may require testing combinations.
- For qualitative work, use anchored rubrics and blinded human comparisons, check rater agreement, and report uncertainty. A generating agent's own judgment cannot be the sole outcome measure.
- Compare against a strong single agent and independent multiple samples plus a fixed selector/vote where suitable. Count selector/orchestrator inference costs. Use separate fixed-total-resource and fixed-per-agent-budget experiments; token counts alone do not equal cost across models.
- Start with a small feasibility pilot (roughly 20-40 frozen tasks, a few agent configurations, sizes 1/2/4), then expand only after estimating variance and cost. Candidate families: source-grounded questions, small code repairs with hidden regression checks, and bounded planning/execution in resettable fixtures. These counts are proposed pilot sizes, not a power calculation.
- Block comparisons by task, repeat stochastic runs, and split development/held-out evaluation by task rather than by repeated sample. Bootstrap/estimate uncertainty at the task level. Do not generalize a small pilot to a universal team-size law.
- Visual outputs should include capability bars with uncertainty, pairwise error/influence matrices, marginal-contribution bars, and quality-versus-team-size curves per protocol. A 3D view is optional; retain the underlying higher-dimensional measurements.
- A later practical selector could recommend the cheapest/smallest tested team meeting a quality requirement, or abstain when evidence is insufficient. Integration with Nova is future work; the existing room is a transport candidate, not a measurement harness.

## Primary sources consulted
- Kim et al., *Towards a Science of Scaling Agent Systems*, arXiv:2512.08296v2, 2025-12-17: https://arxiv.org/html/2512.08296v2 . Compared 180 configurations; benefits depended on architecture/task. The paper's limitations describe only preliminary agent-count exploration up to nine. Do not reuse its fitted thresholds as universal constants or confuse benchmark-relative changes with percentage points.
- Choi, Zhu and Li, *Debate or Vote: Which Yields Better Decisions in Multi-Agent Large Language Models?*, arXiv:2508.17536v1, 2025: https://arxiv.org/html/2508.17536v1 . Across seven benchmarks, voting explained much of the observed benefit. The martingale theorem depends on their specified stochastic belief-update model; it is not a theorem about every possible debate protocol.
- Cemri et al., *Why Do Multi-Agent LLM Systems Fail?*, arXiv:2503.13657v3, 2025-10-26: https://arxiv.org/abs/2503.13657v3 . MAST groups 14 failure modes into system design, inter-agent misalignment and verification. The current abstract reports 1600+ annotated traces across seven frameworks; older search snippets describe an earlier version.

## Verified
- Rendered the fragment in the visualize skill's sandboxed preview wrapper with Playwright Chromium.
- Formula/control smoke checks: (n=20,rho=0) -> 20.00; (20,1) -> 1.00; (1,0.5) -> 1.00; (10,0.5) -> 1.82.
- At actual content widths 736 and 320 pixels, no horizontal overflow or collisions between the two main labels and values; inspected both screenshots. No browser script errors.
- The first ad hoc preview check used inner_text on SVG and failed because SVG nodes are not HTMLElements; corrected the inspection to text_content. This was a preview script issue, not an agent experiment or a visualization defect.
- No product-quality measurements, model comparisons, live Nova inference or optimum estimates were produced.

## Open / next
- The next substantive project milestone would be a versioned task pack, rubric and experiment manifest, followed by a bounded evaluation harness. Task priorities, endpoints, evaluation budget and utility weights remain to be selected when implementing.
- Keep proposed research, analytical examples, source-derived architecture facts and measured runtime outcomes explicitly distinguishable.

## For Cole
- The broad hypothesis already has substantial prior work. A useful project contribution would be measuring and predicting team-specific marginal value for Nova's actual tasks, with reproducible evidence and uncertainty.
