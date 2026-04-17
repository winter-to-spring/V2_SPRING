# Step 16 - Auto-Apply Hardening And Patch Repair Feedback

## Goal

Keep the bounded auto-apply lane fast for obvious safe edits while tightening
the trust boundary around central files, repeated slices, structural danger, and
non-converging repair loops.

## What Changed

- auto-apply now excludes central/protected files even when the patch is small
- repeated auto-apply against the same file or module within a bounded window
  falls back to founder review
- lightweight structural scan supplements the keyword filter
- structural findings are split into hard blocks and soft warnings
- patch validation failures now generate detailed planner-facing repair feedback
- repeated repair failure opens founder escalation instead of looping forever

## Policy Shape

### Hard blocks

- dangerous keyword hit
- sensitive path hit
- central/protected file hit
- repeated auto-apply burst hit
- structural danger hit

Hard blocks force founder review by making the patch ineligible for auto-apply.

### Soft warnings

- structural warning hit
- large patch warning
- multi-file warning

Soft warnings remain founder-visible and replay-visible, but they do not all map
to the same severity.

## Repair Feedback

When strict patch apply or bounded validation fails, the planner now receives a
structured failure view built from:

- typed rejection code
- changed files
- validation command
- base hash conflicts where present
- bounded stdout/stderr previews from strict apply or validation

This feedback is intended to improve repair success without leaking raw,
unbounded validation noise into the planner context.

## Repair Quota

Repeated rejected patch repairs against the same scope are counted over a
bounded window.

Once the repair quota is exhausted:

- the run remains replay-visible
- a founder escalation observation is recorded
- the system stops pretending the repair loop is still healthy

## Follow-up

- shadow centrality beyond the initial protected-file boundary remains open
- stronger structural analysis remains future hardening
- broader trust expansion should stay bounded and issue-driven

## Feedback Incorporated

- Auto-apply trust feedback forced this slice to add protected-file force
  review, anti-salami quotas, and stronger structural scan semantics.
- Repair-loop feedback also required bounded, detailed repair feedback rather
  than vague "try again" failure signals.
- The result is a harder trust boundary that still keeps narrow automation
  alive.
