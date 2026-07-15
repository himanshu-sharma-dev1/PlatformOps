# ADR 0001: SSH Private Key Storage Simplicity

## Status
Accepted (2026-07-15)

## Context
When provisioning a new `Node` on the Cluster page, the API needs access to the private SSH key to execute Ansible playbooks and establish SSH/Docker connection probes. 

In `cPlatform`, keys were handled via an enterprise Vault registry. For `PlatformOps`, we need to balance security with ease of deployment and local execution.

## Decision
We will keep the current **file-persist path** (unencrypted on disk at `data/runtime/ssh_keys/node_{id}.pem`) for simplicity. We will not integrate an external Vault or database-level encryption at this stage.

## Consequences
- **Pros**: Zero external dependencies (no Vault server to configure), simplified debugging, and straightforward Ansible inventory generation.
- **Cons**: Private keys are stored in plaintext on the host filesystem. Access must be secured using OS-level file permissions (e.g., `chmod 600` on the directories and files).
