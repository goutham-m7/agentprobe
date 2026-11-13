## agentprobe regression check

**Significant regressions: overall, task_success, policy_adherence, hallucination, tone, tool_misuse**

24 paired conversations · 10,000 bootstrap resamples · seed 42 · 95% percentile intervals

| Criterion | Baseline | Candidate | Delta | 95% CI | Result |
|---|---:|---:|---:|---:|---|
| overall | 100.0% | 16.7% | -83.3 pp | [-95.8, -66.7] pp | REGRESSION |
| task_success | 100.0% | 16.7% | -83.3 pp | [-95.8, -66.7] pp | REGRESSION |
| policy_adherence | 100.0% | 33.3% | -66.7 pp | [-83.3, -45.8] pp | REGRESSION |
| hallucination | 100.0% | 66.7% | -33.3 pp | [-54.2, -16.7] pp | REGRESSION |
| tone | 100.0% | 83.3% | -16.7 pp | [-33.3, -4.2] pp | REGRESSION |
| tool_misuse | 100.0% | 83.3% | -16.7 pp | [-33.3, -4.2] pp | REGRESSION |

- Intervals are paired conversation-level percentile bootstrap; unadjusted for multiple comparisons.
- Intervals describe this empirical suite, not all users; related templates can reduce effective sample size.
