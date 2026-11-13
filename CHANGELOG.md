# Changelog

All notable changes are documented here using [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/).

## [0.2.0] - 2026-11-13

### Added

- Opt-in bounded OpenAI-compatible retries, aggregate request latency, token usage and explicit-price cost estimates; CLI judge/generator defaults to two retries while targets remain non-retrying.
- Ordered, forward-only literal reply branches in saved/generated conversation plans, with adaptive-comparison warnings.
- Blind `agentprobe label` annotation producing validated calibration JSON without exposing judge predictions or saving incomplete labels.
- Seeded transcript-bootstrap kappa intervals for every rubric and the pooled metric, with undefined replicate counts and transcript-level small-sample warnings.
- JUnit XML for every saved run, distinguishing rubric failures from execution errors.
- `agentprobe repeat` with per-scenario/per-rubric score variance, preserved trial evidence and optional flakiness exit gate.
- Versioned roadmap and local issue drafts, distributable metadata and installation checks for the bundled offline data.

### Fixed

- Sized the test HTTP listener backlog for the runner's supported concurrency. The stdlib backlog of five reset a sixth simultaneous connection on macOS (`ConnectionResetError: [Errno 54]`), intermittently failing CLI HTTP integration tests. A deterministic delayed-accept regression reproduces the cause; the fix preserves zero target retries and the full six-conversation assertion.

### Changed

- Default CLI provider is now `mock`; real endpoints require explicit `--provider openai`.
- Run JSON remains format version 1: branches and interval metadata are additive with defaults, so older saved fixed suites/runs remain readable. Newly generated IDs can differ from v0.1 because plan serialization includes branch metadata; persist suites for comparisons.

### Limits

- Costs are estimates from reported usage and supplied rates, not invoices. No paid model or real-human calibration study was run.
- Tools remain observed, not executed. Composite GitHub PR commenting and fake-tool sandbox execution are deferred.
- Built locally only; no package published, remote updated or release/tag created.

## [0.1.0]

### Added

- Strict agent contracts, six synthetic persona families and a bounded async multi-turn runner.
- Offline synthetic shop regression demo, OpenAI-compatible HTTP adapter and trusted Python callables.
- Evidence-checked rubric judgments, paired regression intervals, calibration point estimates and static JSON/HTML/markdown reports.
