# Interactive human annotation

## Problem

Hand editing calibration JSON is error prone and exposes judge predictions to labelers.

## Acceptance criteria

agentprobe label reads run evidence, shows transcripts without predictions, accepts pass/fail for all criteria and writes a validated human LabelSet; interruption never writes partial output.

## Test plan

CLI subprocess tests exercise input retry, complete labels, EOF and overwrite refusal.

Milestone: v0.2.0. Local issue draft only; not filed on GitHub.
