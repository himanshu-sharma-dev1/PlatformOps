# Project Structure

## Directory Layout

```text
/root/PlatformOps/
├── Dockerfile                         # Standalone Python 3.11-slim + Terraform 1.8.5 + OpenSSH image
├── entrypoint.sh                      # Production startup (pg_isready, migrate, superuser check, gunicorn)
├── docker-compose.yml                 # 14-service compose stack (platformops/*:1.0.0 images)
├── requirements.txt                   # Curated lean production dependencies
├── apps/
│   └── platformops/                   # Core Django application (label: cPlatformIO)
│       ├── admin.py                   # 9 core models registered
│       ├── apps.py                    # App configuration & startup hook
│       ├── models.py                  # 9 essential database models
│       ├── urls.py                    # Core page routing
│       ├── views.py                   # Core view controllers
│       ├── forms/                     # Dynamic form schemas (dFormService.json, etc.)
│       ├── lib/                       # Inlined utilities (CommonUtils)
│       ├── src/                       # Orchestration engines
│       │   ├── ClusterConfig.py       # Cluster topology management
│       │   ├── NodeConfig.py          # Node discovery & SSH connection
│       │   ├── ServiceConfig.py       # Service catalog & config management
│       │   ├── serviceInstall.py      # Ansible playbook execution & container adoption
│       │   ├── ServiceDiagnostics.py  # Live log streaming & Loki queries
│       │   ├── UserMgmnt.py           # Users, invitations, RBAC
│       │   └── PlatformSetting.py     # Resilient configuration loader
│       └── tests/                     # Permanent Django contract & unit test suite
│           ├── test_contracts.py      # 6 core page contract tests
│           └── test_services.py       # Service-layer unit tests
├── config/
│   ├── settings.py                    # Django settings & dynamic module resolution
│   ├── urls.py                        # Root URL routing
│   ├── local.env                      # Runtime environment variables
│   ├── service_install.yaml           # Infrastructure service deployment specifications
│   └── observability/                 # Prometheus, Loki, Alloy, and GlitchTip configurations
├── platform/
│   └── ansible/                       # Ansible playbooks, inventories, and discovery scripts
├── scripts/
│   ├── test_platformops_stack.py      # HTTP 200 smoke test runner
│   ├── test_platformops_acceptance.py # Comprehensive 6-page acceptance suite
│   └── test_live_service_flow.py      # Live end-to-end service and volume test
├── templates_new/                     # Jinja/HTML templates for 6 core pages
└── static/                            # CSS, JS, favicons, logos, and cutil assets
```

## Core Service Catalog Additions

- **`PlatformOpsTest`** / **`InfraPlatformOpsTest`**:
  - Registered in [`apps/platformops/forms/dFormService.json`](file:///root/PlatformOps/apps/platformops/forms/dFormService.json)
  - Registered in [`config/service_install.yaml`](file:///root/PlatformOps/config/service_install.yaml)
  - Registered in [`apps/platformops/src/ServiceConfig.py`](file:///root/PlatformOps/apps/platformops/src/ServiceConfig.py)
  - Backed by local image `platformops/test-service:1.0.0` on port `9030` and volume `/home/ubuntu/Backup_Platform`.
