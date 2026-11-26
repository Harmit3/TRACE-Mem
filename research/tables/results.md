# Experimental results index

See the [chronological inventory](experiment-inventory.csv) for all logged experiments and [full verification grid](verification-grid.csv) for every Step 30 and 31 condition. Unlike denominators are retained separately below.

| Stage | Population or denominator | Result | Scope |
| --- | --- | --- | --- |
| v1 paired outcome collection | 78 train/validation pairs, 52 labeled | All pairs agreed; zero helpful labels; 26 pending | Unfit source cohort |
| v2 full collection | 500 cases, 313 verified candidate rows | Nonpilot train 89/113 positive/negative and validation 35/23 | Repeated scenarios and limited feature diversity |
| v3 feasibility and NLI | 24 pilot histories; 24 independent NLI fixtures | 14 eligible pilot updates; NLI 20/24 with four neutral false contradictions | Feasibility and component check |
| V3 release | 200 histories, 40 family groups, 232 paired rows | 45 helpful, 167 not helpful, 20 pending | Training data and disjoint fit/calibration/evaluation groups |
| T1 fit | 112 labeled train, 63 calibration, 37 labeled evaluation | AP .849 full vs .877 without NLI; 6 vs 5 helpful candidates at 10 calls | Frozen fixed-prefix evaluation |
| Memora prefix and controlled studies | 55-turn prefix or 12-session prefix | 2 and 5 claims respectively; no eligible prefix conflicts | Development diagnostics |
| Step 24 full Memora | One development persona, 151 sessions, 15 questions | Adapted FAMA .000 across all scored policy conditions; 2,184/2,400 rows scorable | Explored policy matrix on one persona |
| Step 25 source audit | 79 question–source nominations | 9 extracted, 7 represented, transcript 47 and oracle 61 supplied | Failure identification under separate diagnostic access |
| Step 26 reader and index | 12 reader fixtures; 18 unresolved scopes in the development persona | V2 11/12, original 7/12; all 1,154 live records quarantined | Conservative authorization and coverage trade-off |
| Step 27 deletion resolution | Seven target-positive fictional cases, 18 real scopes | 6/7 fictional semantic targets, zero real scopes released | Resolver diagnostic |
| Step 29 approved recovery | 18 cases, 57 grants, 14/15 scored | Adapted FAMA .198 scored, .184 failure-inclusive, .106 common-question | Human-assisted, one persona |
| Step 30 fixed T2 vs H-paced | 600 checks each, 250 calls each | 341/600 vs 409/600; −11.3pp [−16.3, −6.3] | Ten family clusters |
| Step 30 chronological T2 vs H-paced | Same 600 checks and call counts | 434/600 vs 394/600; +6.7pp [0.7, 12.3] | Nominal horizon |
| Step 31 nominal T2 vs B3 | 50% allowance, 250 actual calls each | +3.7pp [−1.7, 9.0] | Same Step 30 cohort, post-hoc |
| Step 31 doubled horizon | 50% allowance, T2 211 and B3 250 actual calls | −9.7pp [−16.3, −3.2] | Unequal realized spending |
| Step 31 reader | 30 short questions per policy | T2 7/30, B3 6/30, H-paced 12/30 | Descriptive QA subset |
| Step 32 LongMemEval | 14 retrieval cases, 1 managed replay case | BM25 3/14, MiniLM 2/14, oracle 6/14; every arm 0/1 on common case | Local judge, exploratory external diagnostic |
| Step 33 fictional extraction | 70 fixtures with 100 expected facts | Original 22/100 recall, V3 50/100; 80% gate failed | Component validation |
| Step 33 fictional reader | 30 fixtures | V2 27/30, V3 24/30; gate failed | Component validation |

Intervals are descriptive paired 95% family intervals. The [evidence audit](../../docs/research_evidence_audit.md) documents the units and known limitations.
