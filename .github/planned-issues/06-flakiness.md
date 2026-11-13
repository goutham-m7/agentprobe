# Repeated-run flakiness analysis

## Problem

One pass or failure does not distinguish stable behavior from stochastic instability.

## Acceptance criteria

agentprobe repeat executes an identical suite 2..100 times, saves each run and per-scenario pass fraction, sample variance, criterion variability and errors; errors cannot become passes.

## Test plan

Deterministic and alternating agents, incomplete/mismatched evidence, repeat bounds and CLI end-to-end tests.

Milestone: v0.2.0. Local issue draft only; not filed on GitHub.
