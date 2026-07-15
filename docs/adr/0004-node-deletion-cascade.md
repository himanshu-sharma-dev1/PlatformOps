# ADR 0004: Cascading Node Deletion Safeguards

## Status
Accepted (2026-07-15)

## Context
The `AIOrchestrator` service contains a strict delete guard blocking direct removal while other services exist in the cluster. However, during node decommissioning, the operator is deleting the host compute resource (`Node`). 

We need to decide if the node-level deletion should respect the individual service guards or cascade through them when forced.

## Decision
We will keep the current behavior: a **cascaded force-delete of the Node always cleans up all hosted services on that node, including `AIOrchestrator`**, without forcing the operator to migrate the orchestrator first.

This aligns with physical reality: if the compute node is destroyed or decommissioned, its hosted containers are gone regardless. The control plane relies on the operator's force-delete authorization to perform this total host teardown.

## Consequences
- **Pros**: Clean, non-blocking node decommissioning workflows.
- **Cons**: If the operator force-deletes a node containing the cluster's sole `AIOrchestrator`, the cluster will be left without a control plane service. It is the operator's responsibility to re-bootstrap it on a surviving node.
