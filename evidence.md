# Verification evidence

All data and labels below are synthetic. No paid LLM was called. No human-labelled judge
study was performed. The human annotation template is deliberately incomplete until a
human fills it; synthetic reference labels never claim human provenance.

## Acceptance traceability

| ID | Delivered evidence | Observable result |
|---|---|---|
| EC-1 | `tests/test_scenarios.py::test_seeded_suite_covers_all_six_personas`; [saved suite](docs/demo/suite.json) | All six families, stable seeded IDs and multi-turn plans |
| EC-2 | `tests/test_providers.py::test_http_chat_uses_real_wire_contract`; `tests/test_cli_integration.py::test_run_cli_with_real_local_http_target`; `tests/test_runner.py::test_runner_bounds_concurrency_and_preserves_full_history` | Actual local HTTP requests, full message histories and bounded async overlap |
| EC-3 | `tests/test_runner.py::test_judge_rejects_fabricated_evidence`; `tests/test_cli_integration.py::test_judge_rejects_duplicate_rubric_keys`; [candidate transcript evidence](docs/demo/broken/report.html) | Schema/evidence failures reject judgments; broken target produces actual violating replies/tool attempts |
| EC-4 | `tests/test_statistics.py::test_cohens_kappa_matches_hand_computed_table`; `tests/test_calibration.py::test_calibration_scores_labels_and_keeps_provenance`; [synthetic reference report](docs/demo/calibration.md) | Hand-calculated kappa matches; missing/null labels reject; every output preserves label source |
| EC-5 | `tests/test_comparison.py`; [captured diff](docs/demo/diff.json) | Reproducible paired intervals; incomplete runs, changed suites and changed judges reject |
| EC-6 | [captured output](docs/demo/output.txt), [HTML report](docs/demo/index.html), [PR summary](docs/demo/summary.md), [raw baseline JSON](docs/demo/good/run.json) | Offline demo: baseline 24/24, candidate 4/24, no execution errors |
| EC-7 | `tests/test_cli.py::test_demo_end_to_end_and_ci_gate`; [GitHub Action example](examples/github-action.yml) | Broken-candidate gate exits 1; identical-run gate exits 0 |

## Quality gates observed

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest --cov=agentprobe --cov-report=term-missing --cov-fail-under=90
uv build
```

Observed: Ruff checks passed; all files formatted; **87 tests passed**, **96.39% combined
statement/branch coverage**. Wheel and source distribution built successfully. Coverage
includes CLI subprocesses through coverage.py's subprocess patch; this is not an exclusion
of CLI code. Core runner, rubric judge, comparison and estimators each reached full
reported coverage in this run.

## Fresh-clone and wheel checks

A new local `git clone --no-hardlinks` was created in an empty temporary directory, without
copying the development virtualenv. Its automatically created local origin was removed.
From that clone:

```bash
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run pytest -q --cov=agentprobe --cov-report=term-missing --cov-fail-under=90
uv run agentprobe demo --out .agentprobe/clean-demo --seed 42 --per-persona 4 --samples 10000
uv build
```

Observed again: **87 passed**, **96.39% coverage**. The fresh demo reproduced every pass
count, calibration number and bootstrap endpoint from the captured README run. IDs,
timestamps and durations are intentionally not fixed.

The built wheel then replaced the editable package in that clone, reusing the already
installed frozen dependencies:

```bash
uv pip install --no-deps --python .venv/bin/python ./dist/agentprobe-0.1.0-py3-none-any.whl
uv run --no-sync --offline agentprobe demo --out .agentprobe/wheel-demo --seed 42 --samples 10000
uv run --no-sync agentprobe diff .agentprobe/clean-demo/good .agentprobe/clean-demo/good --samples 10000 --fail-on-regression
uv run --no-sync agentprobe diff .agentprobe/clean-demo/good .agentprobe/clean-demo/broken --samples 10000 --fail-on-regression
```

Observed: packaged YAML/reference data loaded; wheel demo reproduced the results;
identical-run gate exited **0**; broken-candidate gate exited **1**.
An earlier attempt to resolve a brand-new isolated wheel environment with `uv --offline`
failed because the registry cache lacked a required dependency artifact. No source change
or weakened check was used: wheel installation reused the frozen environment with
`--no-deps`. Offline demo execution is verified; offline first-time dependency installation
is not promised.

## Report inspection

Opened the captured comparison in a real browser, followed the candidate-evidence link,
and expanded a trial. Observed the criterion table, persona coverage, Spanish response,
verbatim failure evidence, and working disclosure sections. The browser tab was closed.
All static reports escape model/user content; automated tests exercise HTML and markdown
injection payloads. No external fonts, scripts or analytics are loaded by these reports.

## Measured scope, not inferred quality

- Overall paired delta: **−83.3 pp**, percentile interval **[−95.8, −66.7] pp** using the
  exact seeded command in [captured output](docs/demo/output.txt).
- Agreement **against synthetic reference labels**: **95.0%, κ=0.875**, across the bundled
  reference transcripts. Every criterion is small-sample flagged; this does not establish
  real-model or human judge reliability.
- Synthetic scheduling benchmark: **6.69×** median speedup at concurrency eight. The exact
  command and all raw timing observations are in [benchmark.json](docs/benchmark.json).
- Real HTTP compatibility is tested with local socket servers. Paid-model quality,
  hard cancellation of synchronous threads, real tool execution, multiplicity correction,
  and cluster-aware population inference are not claimed.

No remote was created for this project, no code was pushed, and no package was published.
All HTTP test servers shut down through their fixture cleanup. No application server is
needed for the demo or report.
