# v0.2.0 verification evidence

All bundled conversations, targets and reference labels are synthetic. No paid model was
called, no genuine human calibration study was performed and no GitHub action was run.
The annotation CLI's subprocess tests use a labeler explicitly named synthetic stdin;
writing `label_source: human` exercises the operator interface, not a human-study claim.

## Acceptance traceability

| ROADMAP item | Test/artifact | Observed assertion |
|---|---|---|
| 01 Provider resilience/accounting | `tests/test_provider_accounting.py`; `tests/test_cli_integration.py` | HTTP-boundary fakes prove transient retry, no authentication/read-timeout replay, exhaustion, token/explicit-cost accounting and unknown cost. Real local socket tests exercise CLI HTTP requests. |
| 02 Branch plans | `tests/test_branching.py`; `tests/test_cli_integration.py::test_generate_cli_with_real_local_model_endpoint` | Refusal match skips a prompt; unmatched route continues; invalid destinations reject; adaptive diff warns that realized prompts can differ; generated schema accepts branches. |
| 03 Blind annotation | `tests/test_labelling.py` | Actual subprocess stdin writes a validated LabelSet, retries invalid answers, hides a sentinel judge reason, refuses overwrite and leaves no file after EOF. |
| 04 Kappa intervals | `tests/test_kappa_intervals.py`; [captured 10,000-resample summary](docs/calibration-v02.md); [JSON](docs/calibration-v02.json) | Seeded per-item/pooled intervals, transcript clustering, undefined replicate counts and small-transcript warnings. Overall κ=0.875, interval [0.500, 1.000], 9,998 defined replicates. |
| 05 JUnit | `tests/test_junit.py`; [baseline XML](docs/demo/good/junit.xml); [candidate XML](docs/demo/broken/junit.xml) | Parsed XML distinguishes rubric failures from execution errors, strips invalid controls and preserves escaped reasons/evidence. |
| 06 Flakiness | `tests/test_flakiness.py`; [five-repeat summary](docs/flakiness-v02.md); [JSON](docs/flakiness-v02.json) | Stable target: 0/6 varied, all sample variances zero. Alternating test target: 2/3 passing, sample variance 1/3. Real CLI gate exits 1 for flips, 2 for execution errors, 0 for stable evidence. |
| 07 Distribution | `tests/test_packaging.py`; clean-clone and wheel commands below | Version, MIT metadata, entry point and bundled data verified; wheel/sdist built; standalone installed wheel demo worked outside checkout. |

Tests use real local callables, subprocesses, filesystem artifacts and local HTTP socket
servers. Only the paid HTTP boundary is simulated for transport edge cases; internal
scoring/routing/statistics are not mocked.

## Fresh local clone

Verified clean-clone checkout: `d753aa1`. A later test-fixture-only fix and its regression
are verified separately below; runtime code is unchanged from that clone.
Cloned from the local repository, not GitHub:

```bash
git clone --no-hardlinks /Users/gouthammadineni/Documents/personal/agentprobe \
  /tmp/agentprobe-v02-FlagshipAgentprobe
# In that fresh clone, with no copied virtualenv:
uv sync --frozen
make lint
uv run pytest --cov=agentprobe --cov-report=term-missing --cov-fail-under=90 -q --tb=short
uv run agentprobe demo --out .agentprobe/fresh-demo --seed 42 --per-persona 4 --samples 10000
uv run agentprobe repeat src/agentprobe/data/harbor.yaml \
  --callable agentprobe.demo_agents:good_agent --per-persona 1 --repeats 5 \
  --fail-on-flaky --out .agentprobe/fresh-repeat
uv build
```

Observed with Python 3.12.15:

- Frozen installation succeeded; Ruff lint passed and 61 files passed format check.
- **130 tests passed in 13.39s; 96.21% combined statement/branch coverage**, above the 90% coverage gate.
- Offline demo: baseline **24/24**, candidate **4/24**, zero execution errors.
- Delta **−83.3 percentage points**, 95% paired interval **[−95.8, −66.7]**.
- Synthetic reference agreement **95.0%, κ=0.875**, eight transcripts.
- Five repeats of the six-scenario synthetic good target: **0/6 varied**, zero errors,
  all binary sample variances **0.0000**.
- Built `agentprobe-0.2.0.tar.gz` and `agentprobe-0.2.0-py3-none-any.whl` successfully.

## HTTP fixture flake: diagnosed and fixed

The intermittent target error was reproduced with temporary exception-chain instrumentation.
The actual chain was `ProviderError` → `httpx.ConnectError` → `httpcore.ConnectError` →
`OSError: All connection attempts failed` → **`ConnectionResetError: [Errno 54] Connect call failed ('127.0.0.1', 58498)`**.
This failed during TCP connection establishment, before a request reached its handler.

Root cause: Python 3.12's `ThreadingHTTPServer` inherits a listen backlog of **five**, but
the CLI runner starts **six** conversations. On macOS the sixth connection can be reset
while the server's accept thread is waiting to run. A controlled experiment paused all
accepts: backlog five accepted five connections and reset the sixth with errno 54;
backlog 256 accepted all six. Port allocation/readiness was not the problem: the listener
was already bound/listening before the thread started.

`tests/test_http_fixture.py::test_listener_queues_six_connections_before_accept_thread_runs`
freezes accept-thread scheduling with an event while opening six actual TCP connections.
It failed before the fix with five successes and one `ConnectionResetError(54)`, then
passed after the fixture switched to a local server subclass with `request_queue_size=256`,
matching the runner's supported maximum concurrency. No runtime transport changes,
retries, assertion weakening or extra sleeps were added.

Post-fix commands:

```bash
uv run pytest -q tests/test_http_fixture.py
for i in $(seq 20); do
  uv run pytest -q tests/test_cli_integration.py::test_run_cli_with_real_local_http_target || exit 1
done
uv run pytest --cov=agentprobe --cov-report=term-missing --cov-fail-under=90 -q --tb=short
uv run ruff check .
uv run ruff format --check .
```

Observed: deterministic regression passed; **20/20 consecutive independent pytest runs**
passed; the subsequent full suite passed **131 tests in 12.93s, 96.21% coverage**.
Ruff lint and all **62** format checks passed. Temporary exception instrumentation was
outside the repository and removed; production error redaction remains unchanged.

## Installed wheel, outside source tree

Commands ran from `/tmp`, not either source checkout:

```bash
uv venv /tmp/agentprobe-v02-wheel-env
uv pip install --python /tmp/agentprobe-v02-wheel-env/bin/python \
  /tmp/agentprobe-v02-FlagshipAgentprobe/dist/agentprobe-0.2.0-py3-none-any.whl
/tmp/agentprobe-v02-wheel-env/bin/python -c \
  'import agentprobe; from importlib.metadata import version; print(version("agentprobe")); print(agentprobe.__file__)'
/tmp/agentprobe-v02-wheel-env/bin/agentprobe demo \
  --out /tmp/agentprobe-v02-wheel-demo --seed 42 --per-persona 4 --samples 10000
/tmp/agentprobe-v02-wheel-env/bin/agentprobe diff \
  /tmp/agentprobe-v02-wheel-demo/good /tmp/agentprobe-v02-wheel-demo/good \
  --samples 10000 --fail-on-regression
```

Observed: the new environment selected **Python 3.13.17**, installed the wheel and its
runtime dependencies, printed version **0.2.0** and a `site-packages/agentprobe/__init__.py`
path (not an editable checkout). The installed CLI loaded bundled contract/reference data
and reproduced **24/24 → 4/24**, **−83.3 pp**, **[−95.8, −66.7]**, **95.0%, κ=0.875**.
The identical-run regression gate exited **0**. The full test suite was run on 3.12, not
3.13; only this installed CLI/demo was exercised on 3.13.

## Measured scope and limitations

- [Captured demo output](docs/demo/output.txt), [HTML](docs/demo/index.html),
  [raw candidate evidence](docs/demo/broken/run.json) and [paired diff](docs/demo/diff.json)
  were refreshed from a real v0.2 command. IDs/timings vary; scores/statistics are seeded.
- Kappa interval endpoints are conditional on defined replicates. The small synthetic
  sample and perfect empirical matches are not evidence of population reliability.
- Timing/accounting tests do not validate a vendor invoice or claim real-model throughput.
- No actual human annotation, paid-model run, tool execution, GitHub PR comment, package
  publication, remote push, release or tag was performed. Fake-tool execution and a
  composite comment action remain explicitly deferred, with no stub modules.
- The older synthetic scheduling benchmark in README/docs/benchmark.json is retained as
  a separately labelled prior measurement, not rerun or claimed as a new v0.2 speedup.
