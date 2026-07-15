# ADR 0005: Adopted Service Port Preservation on Redeployment

## Status
Accepted (2026-07-15)

## Context
When a service instance is adopted via node infrastructure discovery, the host port mapping is extracted from the running docker container and stored in the database's `ServiceInstance.config_json` payload. 

If the operator subsequently redeploys this adopted service using the Ansible orchestrator, we must decide whether to reset the container to standard catalog defaults or preserve its discovered/custom host port mappings.

## Decision
We will **honor discovered overrides on redeploy**. The Ansible deployment variables will default to the host port configurations recorded during adoption rather than resetting to catalog defaults.

## Consequences
- **Pros**: Prevents host port collisions during redeploys, avoids breaking external clients already bound to the discovered ports, and respects the existing configuration of the target machine.
- **Cons**: Discovered/non-standard port overrides are carried forward indefinitely, potentially diverging from the standard catalog layout guidelines.
