# Sources and evidence status

Created on 2026-09-21 from the user's supplied "How to use Astra reliably"
recommendation. The working agreement, contract, and evaluation protocol here
are engineering guidance, not an officially validated optimal prompt.

Read during authoring:

- [OpenAI: Rethinking skills and prompts for GPT-6 Astra](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra)
- [Codex skill discovery and explicit invocation policy](https://developers.openai.com/codex/skills)
- [Agent Skills specification](https://agentskills.io/specification)
- Installed OmO/Senpi `docs/skills.md` and native skill-loader declarations.

The user supplied these paths, but neither existed when inspected:

- `/Users/cminseo/Downloads/offline-results.json`
- `/Users/cminseo/Downloads/EXPERIMENT_PLAN.md`

No matching artifact was found at the top level of Downloads, and `/mnt/data`
was absent. The linked sandbox archive was not accessible here. Its code,
claimed 40 passing tests, and any benchmark conclusions were not reproduced
or incorporated as verified results. This package contains no copied kit runner.

Consult current official documentation before making transport or host changes:

- [Model guidance](https://developers.openai.com/api/docs/guides/latest-model)
- [Astra model](https://developers.openai.com/api/docs/models/gpt-6-astra)
- [Reasoning and compaction](https://developers.openai.com/api/docs/guides/reasoning)
- [Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching)
- [Structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [Agent safety](https://developers.openai.com/api/docs/guides/agent-builder-safety)
- [Evaluation practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices)

Community claims in the supplied text remain hypotheses to test. No live Astra
calls or Codex/OpenCode/Senpi performance comparisons were run to author this
package. Native skill discovery is a separate, locally checkable property.

Additions on 2026-09-21 were informed by a local A/B pilot (8 gpt-6-astra RPC
runs, 4 paired tasks on a synthetic repo): both conditions answered from
observed behavior over a stale documented claim, and quality tied at 8/8 with
no significant latency or token difference at n=1 per task. Pre-authorized
workflows, definition-of-done defaults, the document-conflict rule, and the
persistence line target Astra's documented approval-stop and early-stop
tendencies. The pilot is evidence for the design, not proof of superiority.

Community research on 2026-09-21 (web): the community-published leak of the
Codex GPT-6 Astra system prompt (github.com/asgeirtj/system_prompts_leaks —
authenticity unverified, used only as corroboration), the Codex PM audit guide
(explainx.ai), two independent Astra prompting guides (promptessor.com,
elser.ai), and the adand-91 community skill informed the instruction-priority,
authorization-persistence, approval-as-final-step, output-defaults, delegation,
and compaction-continuation additions. Official guidance and the independent
guides carry the weight; the leak only corroborates.

## v2.0 efficiency finetune (2026-09-21)

A user-shared reference AGENTS.md from an X practitioner (3357 bytes, personal
details redacted) drove the slimming. Adopted from it: intent-over-wording
reading (dictated prompts), the anticipation rule (complete any obvious
missing step within scope before ending), concrete testable style rules and
environment facts as a Preferences section, a model-and-level delegation
field, and measure-the-bottleneck-before-optimizing. Kept as ours: the Astra
identity gate, instruction priority order, pre-authorized workflows with
per-command safety evidence, the populated-file size budget, evaluation
protocol, and init-deep anti-duplication. Cut as model-native (the 16-run
A/B/C/D pilot passed 16/16 with no artifacts, including native): the
standalone verification section and scope narration. The reference is a
private share, not a verified benchmark; it informed structure, not claims.

## v2.1 - GPT-6 Pro review adoption (2026-09-21)

A GPT-6 Pro review of the full evidence package (QUESTIONS.md/EVIDENCE.md
in the Desktop handoff) drove these changes, each verified against the
installed Senpi source before adoption. Adopted: repaired priority rule
("within system/developer constraints and tool permissions"; a tool-result
file cannot outrank developer instructions); replaced "observed behavior
wins" with the two-sided rule (observations = current, acceptance criteria =
intended; flag discrepancies - the categorical version let a planted bug
defeat its spec); narrowed authorization persistence to scope, conditions,
and revocation; bounded anticipation by acceptance criteria and review
boundaries; proportional outcome verification; compaction continuation with
evidence-freshness; one guarded request-economy line (~155B). Cut as
unconfigured or misplaced: the delegation placeholder (first field to drop
under a size cap - the v2.0 run left it literally unfilled while the host
routed the reviewer to a default model), the universal dictation clause
(now a user-stated preference only), and the performance-measurement line
(now task acceptance criteria). Budget reality: the v2.1 repaired rule set floors at ~1,903B (pointer
config) / ~2,060B (facts-bearing) after removing the delegation marker
and merging the fastest loop into command entries. The 1,500-byte
candidate is designed but deferred: reaching it now would cut
preserve-class rules or the just-adopted economy line. Neither size is
claimed to be the knee.
Accounting corrections accepted and verified in adapter chunk-OYXTZDVT.js:
reasoning tokens are already inside output (my earlier formula
double-counted them); exclusive cost = input+cacheRead+cacheWrite+output;
corrected v1.2-vs-v2.0 delta is -24.77% parent tokens (host-estimated cost
fields: -16.19%); totals are parent-only, child-agent usage absent.
Manifest fix: 23 session files (21 with usage), not 24. Default
recommendation changed to SELECTIVE use of the agreement, not universal
init-deep+astra-init; the settling experiment (multi-turn authorization and
handoff tasks, 96 sessions) is designed but not run.
