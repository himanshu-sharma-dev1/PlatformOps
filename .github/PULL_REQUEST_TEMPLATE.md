## Describe your changes
Provide a detailed summary of the architectural or infrastructure modifications introduced by this pull request.

## Parity & Architectural Impact
- **Database / Schema Migration Required**: [Yes/No]
- **Ansible/Service Catalog Updates**: [Yes/No] (If yes, specify which catalog cards were updated)
- **Infrastructure Impact**: [VPC/EC2 changes, Helm version upgrades, Docker base image bumps, etc.]

## Verification checklist
Please confirm you have executed the following checks locally:
- [ ] `make lint` passes cleanly (no python formatting issues)
- [ ] `make check` executes compilation, seeds database, and passes the operational integration tests
- [ ] Docker image builds successfully (`make docker-build`)
- [ ] Frontend React bundle compiles successfully (`cd apps/web && npm run build`)

## Screenshots / CLI Outputs (if applicable)
Please attach any screenshots of UI changes or terminal outputs verifying the operational behavior.
