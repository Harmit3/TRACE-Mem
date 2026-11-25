# Literature comparison planning notes

These notes track source selection and experimental design for team review.

| Source | Relevant overlap | Implication for TRACE-Mem |
| --- | --- | --- |
| [Memora, Findings of ACL 2026](https://aclanthology.org/2026.findings-acl.1337/) | Recall and omission after updates or deletion, with a shared FAMA scorer | Use official scoring. Record stale-fact and historical-query outcomes separately where the available questions support them. |
| [MemFSM, EMNLP 2026](https://aclanthology.org/2026.emnlp-main.260/) | Training-free lifecycle tracking distinguishes supersession and expiry; retrieval visibility depends on query intent | Treat temporal visibility as an established approach. Keep visibility fixed across verification policies so gains from routing verifier calls can be measured separately. |
| [LongMemEval, ICLR 2025](https://github.com/xiaowu0162/LongMemEval) | Knowledge updates, temporal reasoning and abstention | Use the cleaned non-oracle data for a frozen transfer evaluation. Keep benchmark evidence and answers out of controller training. |
| [AgeMem, ACL 2026](https://aclanthology.org/2026.acl-long.981/) | Learns long- and short-term memory operations through progressive reinforcement learning | A comparison would need to account for differences in training and action space. The TRACE-Mem test concerns the allocation of an independent verifier under a call budget. |
| [A-Mem, NeurIPS 2025](https://proceedings.neurips.cc/paper_files/paper/2025/hash/19909c36f51abc4856b4560aff3d36d6-Abstract-Conference.html) | Evolves linked memory notes as new information arrives | Document differences in memory representation, prompts and update mechanisms before comparing end-to-end results. |

Memora and LongMemEval pins and licenses are recorded in [the data audit](data_audit.md). Candidate external baseline sources include [MemFSM at `4bf1957`](https://github.com/zhoushuo119-creator/MemFSM/tree/4bf195721890f1a3d4e31a5631838963586cdb08), [ValidMem at `786d5cd`](https://huggingface.co/datasets/Zhou11Alex/ValidMem/tree/786d5cd9f18e65bff6172d81fcb7c9009350a400), and [A-Mem evaluation code at `f9a173d`](https://github.com/WujiangXu/A-mem/tree/f9a173dec325d84fcc97e7828775c7b241c33466). Resolve license terms at the selected revisions and pin any external system dependencies before incorporating them. AgeMem is currently a methodological reference.

## Novelty risks to resolve before evaluation

- **Lifecycle and query intent.** MemFSM establishes close prior work. Where feasible, compare the same lifecycle with verification disabled and with each budget-matched verification policy. Use ValidMem as a diagnostic of current and historical visibility if the evaluation setup and terms permit.
- **Selective verification.** This source set leaves the closest prior work on cost-constrained verification unresolved. Expand the search across selective prediction, active verification and learned memory updates. Record whether each candidate allocates inference-time calls, adjudicates memory updates using independent evidence, and matches realized calls across policies.
- **Budget-matching artifacts.** Policies must make decisions with the information available at the replay step. Predeclare how unused budget, failed verification attempts and ties are counted. Report realized calls and token usage per method at each budget.
- **Circular supervision.** Define verification utility through independently adjudicated update decisions. Inspect baseline and verifier outputs against those decisions while keeping gold labels out of policy inputs and final benchmark answers out of tuning.
