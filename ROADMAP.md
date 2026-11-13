# Roadmap

## v0.2.0 — repeatable evaluation evidence

Local-only milestone. No paid model evaluation or remote publication is implied.

### 01. Resilient provider transport and accounting

- Status: complete
- Problem: Transient judge requests currently fail immediately; token cost and request latency are invisible.
- Acceptance: Retry opt-in 429/5xx and connection failures within a bound; never retry target agents by default. Persist attempts, elapsed time, token usage and optional explicit-price cost without keys.
- Test plan: Local HTTP/transport tests cover retries, exhaustion, malformed usage, price validation, authentication failures and accounting.
- Delivery commits: `4cafaf6..1d22b89`; connection retry coverage in `34e399f..40bf43e`

### 02. Reply-dependent conversation plans

- Status: complete
- Problem: Fixed prompts cannot follow up differently on a refusal and a disclosure.
- Acceptance: Support ordered literal reply branches after a numbered user turn, validate destinations and preserve bounded execution. Existing fixed suites still load.
- Test plan: Runner tests prove matched, unmatched, case-insensitive and invalid branch paths; tool calls still end execution.
- Delivery commits: `1d22b89..f39b5f2`; generated schema in `cd94be3..df52520`; comparison warning in `34e399f..40bf43e`

### 03. Interactive human annotation

- Status: complete
- Problem: Hand editing calibration JSON is error prone and exposes judge predictions to labelers.
- Acceptance: agentprobe label reads run evidence, shows transcripts without predictions, accepts pass/fail for all criteria and writes a validated human LabelSet; interruption never writes partial output.
- Test plan: CLI subprocess tests exercise input retry, complete labels, EOF and overwrite refusal.
- Delivery commits: `f39b5f2..b3046a4`

### 04. Transcript-bootstrap calibration intervals

- Status: complete
- Problem: Point kappa hides uncertainty, especially for small or single-class samples.
- Acceptance: Report seeded 95% percentile kappa intervals per criterion and overall; pool by transcript, count undefined replicates, and never fabricate undefined estimates.
- Test plan: Known agreement cases, reproducibility, degenerate labels, sample limits and CLI JSON/markdown tests.
- Delivery commits: `b3046a4..e732dfa`; transcript-count warning in `34e399f..40bf43e`

### 05. JUnit CI evidence

- Status: complete
- Problem: CI systems cannot ingest the HTML or markdown evidence as native test results.
- Acceptance: Every run writes JUnit XML with one case per scenario, rubric failures separate from execution errors, safe XML text and useful reasons.
- Test plan: Parse actual run artifacts and assert counts, duration, failure/error details and XML escaping.
- Delivery commits: `e732dfa..cd94be3`

### 06. Repeated-run flakiness analysis

- Status: complete
- Problem: One pass or failure does not distinguish stable behavior from stochastic instability.
- Acceptance: agentprobe repeat executes an identical suite 2..100 times, saves each run and per-scenario pass fraction, sample variance, criterion variability and errors; errors cannot become passes.
- Test plan: Deterministic and alternating agents, incomplete/mismatched evidence, repeat bounds and CLI end-to-end tests.
- Delivery commits: `cd94be3..df52520`; CLI flip/error gates in `34e399f..40bf43e`

### 07. Build and verify distributable v0.2.0

- Status: complete
- Problem: Source checkout success does not prove an installed wheel contains the bundled demo and entry point.
- Acceptance: Bump metadata and module version; build wheel/sdist locally and verify fresh-clone install, tests, lint and demo plus wheel install outside checkout. Never publish.
- Test plan: Build artifacts, inspect wheel data and run installed CLI/demo from a clean directory.
- Delivery commits: `df52520..34e399f`; fresh-clone verification at `d753aa1` recorded in [evidence.md](evidence.md)

## Future work (not implemented)

- Sandboxed fake-tool execution: define state and JSON-schema enforcement before promising a tool-result loop. Current calls remain observed only.
- Composite PR-comment action: defer network side effects and token-permission surface; JUnit and markdown remain available to existing CI.
