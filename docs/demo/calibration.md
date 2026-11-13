## Judge agreement against synthetic reference labels

8 transcripts · Judge: mock:harbor-oracle-v1

| Criterion | Agreement | Cohen's kappa | 95% kappa CI | Defined replicates | Reliability warnings |
|---|---:|---:|---:|---:|---|
| task_success | 87.5% | 0.750 | [0.200, 1.000] | 993/1000 | small_sample, undefined_bootstrap_replicates |
| policy_adherence | 100.0% | 1.000 | [1.000, 1.000] | 977/1000 | small_sample, undefined_bootstrap_replicates |
| hallucination | 100.0% | 1.000 | [1.000, 1.000] | 649/1000 | small_sample, undefined_bootstrap_replicates |
| tone | 87.5% | 0.600 | [0.000, 1.000] | 897/1000 | small_sample, undefined_bootstrap_replicates |
| tool_misuse | 100.0% | 1.000 | [1.000, 1.000] | 692/1000 | small_sample, undefined_bootstrap_replicates |
| overall | 95.0% | 0.875 | [0.500, 1.000] | 1000/1000 | small_sample |

Synthetic references demonstrate calibration mechanics only. No human agreement or real-model reliability is claimed.

Overall agreement pools rubric decisions; per-item warnings are the reliability gate.
