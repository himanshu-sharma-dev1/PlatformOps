# Long-Running Agent Goal Prompt: PlatformOps Capability Distillation & Polish

You can copy and run the following prompt in a new agent session (preferably using the `/goal` command) to execute a comprehensive, long-running improvement cycle for this project.

---

## Agent Goal Prompt

```markdown
Goal: Fully distill the remaining DevOps/MLOps capabilities from cPlatform into PlatformOps, resolve all template placeholders, and upgrade the entire UI/UX to a premium, production-grade SRE console.

Follow the workflow protocol: Read tasks/todo.md, create a detailed implementation plan, obtain user approval, execute step-by-step (updating task.md), and verify all changes.

Key Deliverables:

1. Premium UI/UX Polish (Phase 2 Alignment)
- Restyle the CSS system in `apps/web/src/styles.css` using HSL-tailored colors, smooth gradients, and glassmorphism.
- Fix all grid alignment, padding, and layout spacing issues.
- Add micro-animations (e.g., subtle neon glows on active sidebar tabs, smooth hover transitions on host node cards).
- Clean up any unused template sections, dummy metrics, or cluttered mock elements in `main.tsx`.

2. Activate the Dataflow (Batch & Stream I/O) Subsystem
- Backend:
  * Create SQLAlchemy models in `models.py` for `DataflowBatchConfig`, `DataflowStreamConfig`, and `DataFlowLogs` (mirroring cPlatform's columns for schedules, source/destination types, timezones, and connectivity details).
  * Build FastAPI endpoints in `main.py` for Dataflow CRUD operations, logs fetching, and status toggles.
- Frontend:
  * Implement active screens in `main.tsx` for "Batch I/O" and "Stream I/O" (removing the opacity: 0.6 limitation).
  * Add configuration forms for setting up connection protocols (FTP, SFTP, S3, Google Drive) and scheduling periodic ingestion intervals.
  * Connect the "Pipeline logs" tab to a list/detail view displaying ingestion history.

3. Build the MLOps Model Registry (Train, Infer, Compare) Subsystem
- Backend:
  * Create SQLAlchemy models in `models.py` for `ModelInfo`, `AlgoInfo`, `ModelInfer`, `AlgoInfer`, and `ModelCompare` (mirroring cPlatform's tables).
  * Implement API endpoints to register models, define algorithms, allocate CPU/GPU resources, and fetch side-by-side performance matrices.
- Frontend:
  * Implement full dashboard panels in `main.tsx` for "Train", "Infer", and "Compare" tabs.
  * Create a model comparison grid displaying evaluation metrics (accuracies, losses, inference latencies) and resource footprints.
  * Add interactive charts or sparklines comparing base models vs challenger models.

4. Implement User Management & Invitations
- Backend:
  * Add FastAPI endpoints to manage `UserInfo` roles (System_Admin, Operational, Management) and create/accept `InviteToken` requests.
- Frontend:
  * Activate the "Users" sidebar panel to display registered users, login activities, and allow admins to invite new operators.

5. Node Onboarding Credentials & Visual Playbooks
- Backend:
  * Secure Node authentication registry mounting private SSH keys/passwords.
  * Integrate simulated dry-run playbook output so operators can view the exact Ansible execution logs during node validation.
- Frontend:
  * Create an "Onboard Node" credentials drawer inside the cluster detail view.

6. Integration Testing & Verification
- Run local health checks (`make check` and `npm run build` inside `apps/web`) at the end of each phase.
- Expand `scripts/verify_platformops.py` with integration tests for all newly implemented endpoints to ensure everything compiles and passes with zero warnings.
```
