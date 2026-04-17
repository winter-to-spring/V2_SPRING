# Risk ID: RISK-0029
Title: ~~Founder review may miss dangerous or over-broad patch changes without guided review signals~~
Class: Before Next Phase
Status: Resolved
Owner: Founder review surface / Intake gate
Observed In: Step 12-c patch intake planning

## Description

If founder review only shows a raw diff blob, dangerous or nonsensical changes
can slip through because the reviewer is overloaded.

Examples:

- shell execution or destructive API calls introduced in the patch
- unusually large patches that should probably be split
- edits touching sensitive paths without a clear warning signal

## Impact

- malicious or hallucinated patch content may be approved accidentally
- founder fatigue increases as every review becomes a full manual code audit
- trust in worker output decreases because the surface gives too little guidance

## Why This Matters

Step 12-c is the human trust boundary for worker-produced code changes.

If the review surface is too raw, the founder becomes the weakest safety link.

## Suggested Mitigation

- show compact review summaries before the raw diff
- run a bounded danger-keyword/path scan and display warnings
- show patch size and touched-file counts prominently
- keep a raw diff/receipt escape hatch for deeper inspection

Current resolution:

- founder review now exposes a compact patch summary before the raw diff
- warning signals include danger keywords, sensitive paths, file counts, and
  oversized patch hints
- raw diff and receipt data remain available through explicit review flags
- the review gate stays strict, so guided warnings complement rather than
  replace final founder approval

## Capability Gate
- Capability: founder review gate for patch intake
- Gate mode: Before Next Phase
- Blocked until: review surface provides guided warnings beyond raw diff output

## Issue Link
- GitHub Issue: #30

## Doc Links
- ADR:
- Design note: docs/issues/STEP_12C_PATCH_INTAKE_REVIEW_GATE.md

## Exit Criteria

- review surface presents patch risk cues before approval
- large or sensitive patches show explicit warnings
- raw diff remains accessible without being the only review tool

## Last Updated
- 2026-04-17
