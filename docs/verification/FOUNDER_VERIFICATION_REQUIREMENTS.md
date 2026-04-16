# V2_SPRING Founder Verification Requirements

## Why This Exists

The previous system could sometimes "run", but a human could not verify what
actually happened without trusting the agent's summary. That is not acceptable
for V2.

Founder verification is a core architecture requirement, not a late UI task.

## A Founder Must Be Able To See

### 1. Input
- what request was submitted
- what urgency or risk was declared
- what files or references were attached

### 2. Process
- which phase the run is in
- who is actively working
- who is idle
- what module is being worked on
- whether the run is blocked or waiting

### 3. Decisions
- what plan was chosen
- what alternatives were considered
- why the current path was selected
- what was escalated to a human

### 4. Artifacts
- what documents were produced
- what code changes were generated
- what test or evaluation outputs were recorded
- where each artifact is stored

### 5. Approvals
- what is waiting for human approval
- why approval is needed
- what happens if it is approved
- what happens if it is rejected

### 6. Outcome
- what was completed
- what remains unfinished
- what risks remain
- what next actions are recommended

## Required Surfaces

### Request Surface
- request composer
- urgency and risk input
- attachments or references

### Live Run Surface
- current phase
- active workers
- blocked state
- process trail
- module status

### Approval Surface
- pending approvals
- reason and tradeoff summary
- approve or reject actions

### Artifact Surface
- produced documents
- build outputs
- evaluation outputs
- result package

### History Surface
- prior runs
- replayable event timeline
- past approvals and decisions

## Architectural Implication

These requirements force V2 to have:
- structured event ledger
- structured decision storage
- structured artifact registry
- structured approval lifecycle

If a process step cannot be shown clearly in these surfaces, it is not truly
part of the system yet.
