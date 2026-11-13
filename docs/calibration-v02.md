## Judge agreement against synthetic reference labels

8 transcripts · Judge: mock:harbor-oracle-v1

| Criterion | Agreement | Cohen's kappa | 95% kappa CI | Defined replicates | Reliability warnings |
|---|---:|---:|---:|---:|---|
| task_success | 87.5% | 0.750 | [0.158, 1.000] | 9956/10000 | small_sample, undefined_bootstrap_replicates |
| policy_adherence | 100.0% | 1.000 | [1.000, 1.000] | 9774/10000 | small_sample, undefined_bootstrap_replicates |
| hallucination | 100.0% | 1.000 | [1.000, 1.000] | 6510/10000 | small_sample, undefined_bootstrap_replicates |
| tone | 87.5% | 0.600 | [0.000, 1.000] | 8991/10000 | small_sample, undefined_bootstrap_replicates |
| tool_misuse | 100.0% | 1.000 | [1.000, 1.000] | 6604/10000 | small_sample, undefined_bootstrap_replicates |
| overall | 95.0% | 0.875 | [0.500, 1.000] | 9998/10000 | small_sample, undefined_bootstrap_replicates |

Synthetic references demonstrate calibration mechanics only. No human agreement or real-model reliability is claimed.

Overall agreement pools rubric decisions; per-item warnings are the reliability gate.
