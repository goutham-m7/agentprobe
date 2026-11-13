# Build and verify distributable v0.2.0

## Problem

Source checkout success does not prove an installed wheel contains the bundled demo and entry point.

## Acceptance criteria

Bump metadata and module version; build wheel/sdist locally and verify fresh-clone install, tests, lint and demo plus wheel install outside checkout. Never publish.

## Test plan

Build artifacts, inspect wheel data and run installed CLI/demo from a clean directory.

Milestone: v0.2.0. Local issue draft only; not filed on GitHub.
