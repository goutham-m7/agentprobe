# JUnit CI evidence

## Problem

CI systems cannot ingest the HTML or markdown evidence as native test results.

## Acceptance criteria

Every run writes JUnit XML with one case per scenario, rubric failures separate from execution errors, safe XML text and useful reasons.

## Test plan

Parse actual run artifacts and assert counts, duration, failure/error details and XML escaping.

Milestone: v0.2.0. Local issue draft only; not filed on GitHub.
