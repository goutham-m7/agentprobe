# Implementation and test strategy

Implement validated schemas and YAML rubric derivation; deterministic suite generation;
OpenAI-compatible provider and callable adapter; bounded conversation execution and strict
judge; calibration; paired bootstrap; escaped reports; CLI and synthetic demo; CI and docs.
Commit each coherent boundary with its tests. Run all tests, lint, offline demo, CLI gates,
build/package smoke and coverage before final evidence capture.

Tests own public boundaries: schema parsing (unit); provider/local HTTP protocol
(integration); runner with real callables (integration); judge malformed output (unit);
kappa and bootstrap against known data (unit); CLI/report artifacts (integration).
Only external model HTTP responses use a local test server. No internal logic mocking.
Timeout tests use short-lived test callables, not clock patches. Seeded standard-library
randomness makes statistical tests deterministic. No paid LLM quality claims, real network
provider benchmark or browser-engine rendering tests: credentials unavailable and output is
static semantic HTML. Evidence maps acceptance IDs to observed CLI artifacts and test names.
