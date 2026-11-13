# Resilient provider transport and accounting

## Problem

Transient judge requests currently fail immediately; token cost and request latency are invisible.

## Acceptance criteria

Retry opt-in 429/5xx and connection failures within a bound; never retry target agents by default. Persist attempts, elapsed time, token usage and optional explicit-price cost without keys.

## Test plan

Local HTTP/transport tests cover retries, exhaustion, malformed usage, price validation, authentication failures and accounting.

Milestone: v0.2.0. Local issue draft only; not filed on GitHub.
