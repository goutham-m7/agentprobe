# Reply-dependent conversation plans

## Problem

Fixed prompts cannot follow up differently on a refusal and a disclosure.

## Acceptance criteria

Support ordered literal reply branches after a numbered user turn, validate destinations and preserve bounded execution. Existing fixed suites still load.

## Test plan

Runner tests prove matched, unmatched, case-insensitive and invalid branch paths; tool calls still end execution.

Milestone: v0.2.0. Local issue draft only; not filed on GitHub.
