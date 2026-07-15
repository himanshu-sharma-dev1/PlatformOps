# Context Glossary

## Terms

### Cluster
A logical grouping of computer nodes that share the same code repository (e.g., GitHub) and container image registry (e.g., DockerHub) settings.

### Node
A physical or virtual host compute instance (IP address, SSH user, and credentials) that belongs to a Cluster and runs containerized services.

### ServiceInstance
A specific catalog-defined containerized application or infrastructure service mapped to a Node. Represented by a database record and a running container.

### Adopted
A ServiceInstance that was already running on a Node and was discovered and registered in the database via the Discovery scan rather than being deployed from scratch.

### install_mode
The deployment strategy for a service.
- **MANUAL**: The operator manages container updates outside the orchestrator, and the platform only tracks its lifecycle and configurations.
- **ANSIBLE**: The orchestrator is fully responsible for provisioning, configuring, and updating the container using playbooks.

### AIOrchestrator
The central platform governance control service (using the key `ai-orchestrator`). It is bootstrapped automatically on the first node of a cluster and has protective delete rules to ensure the cluster control plane stays alive.

### patching
A transient state of a ServiceInstance during which an asynchronous script is actively injecting telemetry hooks (like Sentry/GlitchTip keys) and restarting the container.

