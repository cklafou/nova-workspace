<!-- @nova: Record research and brainstorming on adaptive psychological profiles for human-AI collaboration, without implementing a profiling system. -->
# Personalized human-AI collaboration
**Summary:** Cole proposed adaptive, AI-administered psychological testing to produce quantitative user profiles that guide AI collaboration. Evaluated the idea as a research/product proposal; no profile, test, runtime feature or architecture change was implemented.

## Did
- Read Orient README, note-taking rules, file conventions, the latest prior Codex collaboration note, and the newly arrived `2026-10-04_0326_Codex_AgentTeamResearch.md`.
- Consulted the engineering architecture skill for design evaluation and the memory registry for existing boundaries. The deferred Nova architecture map remains deferred.
- Read primary research on adaptive personality testing, learning-style matching, user-history retrieval for LLM personalization, and assisted versus independent student performance.
- Developed a conceptual separation between psychological measurement, declared collaboration preferences, domain mastery, current task/state, and a policy that chooses AI behavior from these inputs.

## Why
A quantitative user representation could make personalization more consistent, inspectable and portable, but numerical precision does not establish psychological validity or recreate a person. A reliable trait score does not itself show which teaching intervention works for that individual. The measurement-to-action mapping needs separate validation.

The proposed profile should retain uncertainty, evidence provenance, context and update times. Adaptive assessment should use calibrated items and psychometric expertise; newly generated questions require evaluation before they can support equivalent scored inferences. Distinguish relatively stable traits from skills, situational constraints and directly stated preferences. Current user instructions should override inferred preferences.

The training-weights analogy is partial: user scores are model inputs or learned representations, while a separate, model-specific policy translates them into behavior. A number in a prompt is not automatically a calibrated control. Retain memory for factual, episodic and contextual evidence; a structured profile complements it.

The human-contribution hypothesis requires outcome measures beyond satisfaction: independent performance, delayed retention, transfer and ability to explain or revise joint work. Users should be able to choose learning, collaboration or delegation goals. A preferred output can still reduce opportunities to practice. User ownership, inspectability, correction, deletion and control over sharing belong in the proposed product design.

## Evidence and limits
- Gao et al. (online March 29, 2026), *Development of a Computerized Adaptive Item Bank for the Big Five Personality Based on Large Language Models*: publisher abstract reports LLM-generated Simplified Chinese items evaluated through two empirical rounds. This establishes close prior work on the assessment component, not validation of the proposed end-to-end collaborator. Full article is restricted; only the public abstract and bibliographic information were inspected. https://journals.sagepub.com/doi/10.1177/10731911261427877
- Nieto et al. (2017), *Calibrating a new item pool to adaptively assess the Big Five*: empirical item calibration and post-hoc CAT simulation; do not describe the simulation as a deployed adaptive service. https://www.psicothema.com/pdf/4411.pdf
- Pashler et al. (2008), *Learning Styles: Concepts and Evidence*: review found inadequate evidence for matching instruction to assessed learning styles. This does not deny preferences, aptitude differences or all forms of personalized instruction. https://digitalcommons.usf.edu/psy_facpub/1765/
- Salemi et al. (ACL 2024), *LaMP: When Large Language Models Meet Personalization*: reported benefits from retrieving user-profile history on benchmark personalization tasks. This does not establish tutoring effectiveness, but contradicts blanket dismissal of retrieval-based personalization. https://aclanthology.org/2024.acl-long.399/
- Bastani et al., *Generative AI Without Guardrails Can Harm Learning*: inspected author manuscript. In the studied high-school math setting, unrestricted assistance improved practice performance but reduced subsequent unassisted exam performance; the tutor condition largely mitigated the loss without demonstrating a positive exam effect. Do not generalize this to every model, domain or long-term retention. https://hamsabastani.github.io/education_llm.pdf

## Verified
- Research sources and their stated scope were checked. No human study, psychological scoring, model calibration or Nova runtime test was performed.
- This note was written using a same-directory temporary file and rename. No existing notes, Nova-owned records or implementation files were edited.

## Open / next
- Proposed first study: one skill domain, same base model and tutoring resources, randomized comparison of a strong memory/preferences baseline, structured contextual profile, and the same system augmented with validated psychometric measurements. Measure independent and delayed performance alongside satisfaction, burden and joint-output quality.
- The incremental benefit of psychological testing beyond explicit preferences and observed task performance remains the central untested question.
- This is brainstorming, not authorization to build a service, administer assessments, collect sensitive profiles, launch experiments or resume earlier Nova work.