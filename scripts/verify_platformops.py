from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from platformops.catalog import dependency_catalog, service_catalog  # noqa: E402
from platformops.db import SessionLocal, init_db  # noqa: E402
from platformops.main import (  # noqa: E402
    create_cluster as api_create_cluster,
)
from platformops.main import (  # noqa: E402
    create_node as api_create_node,
)
from platformops.main import (  # noqa: E402
    get_topology,
    list_catalog,
    list_nodes,
    list_services,
    monitoring_sweep,
)
from platformops.main import (  # noqa: E402
    update_cluster as api_update_cluster,
)
from platformops.main import (  # noqa: E402
    update_node as api_update_node,
)
from platformops.models import ServiceInstance  # noqa: E402
from platformops.orchestrator import (  # noqa: E402
    RUNNING_STATUSES,
    bootstrap_observability_plane,
    capability_coverage_report,
    complete_maintenance,
    compare_config_snapshots,
    create_audit_export,
    create_config_snapshot,
    create_force_delete_approval,
    create_incident,
    create_release,
    create_release_approval,
    create_secret_record,
    create_service_instance,
    decide_force_delete_approval,
    dependency_preflight,
    deployment_plan,
    detect_drift,
    diagnostics_targets_for_service,
    decide_release_approval,
    assess_release_safety,
    evaluate_force_delete_policy,
    evaluate_slos,
    execute_runbook,
    execute_deployment_plan,
    generate_capacity_report,
    generate_compose,
    generate_inventory,
    get_config_timeline_page,
    get_cluster_operations_view,
    get_dtrain_overview,
    get_dashboard_summary,
    get_node_connection_report,
    get_node_job_history,
    get_node_metrics,
    get_node_onboarding_report,
    service_diagnostics_analysis,
    get_service_metrics,
    get_service_release_timeline,
    get_service_summary,
    get_service_capabilities,
    get_subsystem_rollout_plan,
    index_log_archives,
    install_missing_dependencies,
    latest_audit_exports,
    latest_force_delete_approvals,
    latest_maintenance_windows,
    latest_policy_findings,
    latest_secrets,
    lifecycle_audit_report,
    lifecycle_impact,
    list_config_snapshots_page,
    list_events,
    mark_force_delete_approval_used,
    observability_pipeline_report,
    placement_auto_deploy,
    placement_recommendations,
    record_event,
    remediate_node_onboarding,
    rename_config_snapshot,
    resolve_incident,
    restore_config_snapshot,
    revoke_force_delete_approval,
    rollback_release,
    rotate_secret_record,
    run_backup,
    run_policy_scan,
    schedule_maintenance,
    apply_config_direct,
    apply_config_migration,
    backfill_service_logs,
    config_workspace,
    prepare_config_migration,
    restore_config_migration,
    service_install_schema,
    service_diagnostics,
    service_live_logs,
    update_service_instance,
    validate_force_delete_approval,
    validate_node,
)
from platformops.schemas import ClusterCreate, ClusterUpdate, NodeCreate, NodeUpdate  # noqa: E402


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    init_db()
    services = service_catalog()
    dependencies = dependency_catalog()
    assert_true(len(services) >= 40, "Expected at least 40 service catalog entries")
    assert_true(set(dependencies) == set(services), "Dependency map must cover every service")
    assert_true("alloy-core" in services, "Alloy core service card should exist")

    missing_targets = sorted(
        {target for values in dependencies.values() for target in values if target not in services}
    )
    assert_true(not missing_targets, f"Dependency targets missing from service catalog: {missing_targets}")

    db = SessionLocal()
    try:
        cards = list_catalog()
        instances = list_services(db=db)
        topology = get_topology(db)
        checks = monitoring_sweep(db)
        nodes = list_nodes(db=db)

        assert_true(len(cards) == len(services), "Catalog endpoint count mismatch")
        rag_card = next((card for card in cards if card["service_key"] == "rag"), None)
        assert_true(rag_card is not None, "Catalog should include the RAG service card")
        assert_true(
            "ports" in rag_card and "volumes" in rag_card and "command" in rag_card and "env" in rag_card,
            "Catalog cards should expose install review metadata",
        )
        assert_true(len(instances) >= len(services), "Seeded service instances missing")
        assert_true(len(nodes) >= 3, "Expected at least three seeded nodes for placement simulation")
        assert_true(len(topology["subsystems"]) >= 10, "Subsystem topology is too small")
        assert_true(len(topology["edges"]) >= 50, "Dependency topology edge count is too small")
        assert_true(len(checks) >= len(services), "Monitoring sweep did not cover all services")

        stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
        created_cluster = api_create_cluster(
            ClusterCreate(name=f"verify-cluster-{stamp}", region="local", environment="verify"),
            db=db,
        )
        assert_true(
            created_cluster.name.startswith("verify-cluster-"), "Cluster create endpoint should persist new cluster"
        )
        updated_cluster = api_update_cluster(
            created_cluster.id,
            ClusterUpdate(region="aws-ap-south-1", environment="verify-updated"),
            db=db,
        )
        assert_true(
            updated_cluster.environment == "verify-updated", "Cluster update endpoint should persist environment"
        )
        created_node = api_create_node(
            NodeCreate(
                cluster_id=created_cluster.id,
                name=f"verify-node-{stamp}",
                host="127.0.0.1",
                ssh_user="ubuntu",
                environment="local",
                volume_root="/tmp/platformops-verify",
                docker_network="platformops-net-verify",
            ),
            db=db,
        )
        assert_true(
            created_node.cluster_id == created_cluster.id, "Node create endpoint should attach node to target cluster"
        )
        updated_node = api_update_node(
            created_node.id,
            NodeUpdate(host="localhost", docker_network="platformops-net-verify-updated", status="healthy"),
            db=db,
        )
        assert_true(
            updated_node.docker_network.endswith("updated"), "Node update endpoint should persist mutable node fields"
        )
        validate_job = validate_node(db, updated_node)
        assert_true(validate_job.status == "success", "Node validate action should succeed in local mode")
        db.refresh(updated_node)
        assert_true(
            "checked_at" in (updated_node.facts_json or ""), "Node validation should persist facts_json payload"
        )
        connection_report = get_node_connection_report(db, updated_node.id)
        assert_true(
            connection_report["connection_state"] == "validated",
            "Node connection report should reflect successful validation",
        )
        assert_true(
            connection_report["facts_available"], "Node connection report should include node facts after validation"
        )
        assert_true(
            connection_report["validation_job"] is not None,
            "Node connection report should include latest validation job details",
        )
        onboarding_report = get_node_onboarding_report(db, updated_node.id)
        assert_true(
            onboarding_report["overall_status"] in {"pass", "warn", "fail"},
            "Node onboarding report should expose normalized status",
        )
        assert_true(len(onboarding_report["checks"]) >= 6, "Node onboarding report should include readiness checks")
        assert_true(onboarding_report["pass_count"] >= 1, "Node onboarding report should include passing checks")
        assert_true(
            len(onboarding_report["suggested_actions"]) >= 1,
            "Node onboarding report should suggest at least one remediation action",
        )
        aws_preset = remediate_node_onboarding(db, updated_node.id, action="apply-aws-general-preset")
        assert_true(aws_preset["ok"], "AWS general preset remediation should succeed")
        assert_true(
            aws_preset["updated_fields"].get("environment") == "aws", "AWS general preset should set environment=aws"
        )
        local_preset = remediate_node_onboarding(db, updated_node.id, action="apply-local-preset")
        assert_true(local_preset["ok"], "Local preset remediation should succeed")
        assert_true(
            local_preset["updated_fields"].get("environment") == "local", "Local preset should set environment=local"
        )
        remediation_validation = remediate_node_onboarding(db, updated_node.id, action="run-validation")
        assert_true(remediation_validation["ok"], "Run-validation remediation should succeed in local mode")
        assert_true(
            remediation_validation["validation_job"] is not None,
            "Run-validation remediation should return validation job details",
        )
        post_validation_onboarding = get_node_onboarding_report(db, updated_node.id)
        assert_true(
            "run-validation" in post_validation_onboarding["suggested_actions"],
            "Validated nodes should still expose validation refresh guidance",
        )
        observability_bootstrap = bootstrap_observability_plane(db, updated_node.id)
        assert_true(
            observability_bootstrap["subsystem"] == "observability-plane",
            "Observability bootstrap should report the observability-plane subsystem",
        )
        assert_true(observability_bootstrap["ok"], "Observability bootstrap should succeed for a validated local node")
        assert_true(
            isinstance(observability_bootstrap["jobs"], list) and len(observability_bootstrap["jobs"]) >= 1,
            "Observability bootstrap should return at least one deployment job",
        )
        assert_true(
            observability_bootstrap["ingestion_state"] in {"healthy", "degraded", "not-initialized", "unknown"},
            "Observability bootstrap should expose a normalized ingestion state",
        )

        rag = db.query(ServiceInstance).filter(ServiceInstance.service_key == "rag").one()
        rag_preflight = dependency_preflight(db, rag)
        assert_true(rag_preflight["ok"], f"RAG should pass seeded preflight: {rag_preflight}")
        assert_true("alloy-core" in rag_preflight["required"], "RAG should include alloy-core dependency")

        edge_node = next((node for node in nodes if node.name == "edge-node"), None)
        assert_true(edge_node is not None, "Edge node should be present in seeded topology")
        option_on_edge = create_service_instance(
            db,
            node=edge_node,
            service_key="option-copilot",
            contract_overrides={"ports": ["19091:8080"]},
        )
        option_on_edge.status = "created"
        db.commit()
        option_contract = json.loads(option_on_edge.config_json or "{}")
        assert_true(option_contract.get("ports") == ["19091:8080"], "Service creation should persist contract overrides")
        edge_preflight_before = dependency_preflight(db, option_on_edge)
        assert_true(not edge_preflight_before["ok"], "Option Copilot should initially miss dependencies on edge node")
        install_result = install_missing_dependencies(db, option_on_edge)
        assert_true(
            install_result["preflight"]["ok"],
            f"Dependency installer should recover edge service dependencies: {install_result['preflight']}",
        )
        assert_true(
            len(install_result["dependency_actions"]) >= 1,
            "Dependency installer should execute at least one dependency deployment action",
        )

        dtrain = db.query(ServiceInstance).filter(ServiceInstance.service_key == "dtrain-controller").one()
        plan = deployment_plan(db, dtrain.node, "dtrain-controller")
        assert_true(plan["service_key"] == "dtrain-controller", "Deployment plan target mismatch")
        assert_true(len(plan["steps"]) >= 4, "DTrain plan should include dependencies and target")
        assert_true(
            "ansible_command" in plan["steps"][0] and "docker_service.yml" in plan["steps"][0]["ansible_command"],
            "Deployment plan steps should expose Ansible command previews",
        )
        execute_result = execute_deployment_plan(db, dtrain, auto_install_dependencies=True)
        assert_true(execute_result["plan"]["service_key"] == dtrain.service_key, "Executed deployment plan should reference target service")
        assert_true(execute_result["target_job"] is not None, "Executed deployment plan should return target deployment job")
        assert_true(
            "docker_service.yml" in execute_result["target_job"].command,
            "Executed deployment plan should expose target Ansible command",
        )
        assert_true(
            execute_result["preflight_after"]["ok"],
            "Executed deployment plan should leave the target in a preflight-ready state",
        )
        node_jobs = get_node_job_history(db, dtrain.node_id, limit=5)
        assert_true(node_jobs["node_id"] == dtrain.node_id, "Node job history should resolve the selected node")
        assert_true(node_jobs["total_jobs"] >= 1, "Node job history should include recorded jobs")
        assert_true(
            any("docker_service.yml" in item["command"] or "validate_node.yml" in item["command"] for item in node_jobs["items"]),
            "Node job history should surface Ansible command traces",
        )

        placement = placement_recommendations(db, service_key="dtrain-controller")
        assert_true(len(placement["candidates"]) >= 3, "Placement advisor should return all seeded node candidates")
        assert_true(
            any(candidate["node_id"] == dtrain.node_id for candidate in placement["candidates"]),
            "Placement advisor should include the seeded primary node as a candidate",
        )
        assert_true(
            placement["candidates"][0]["score"] >= placement["candidates"][-1]["score"],
            "Placement advisor candidates should be ranked by score",
        )
        constrained_placement = placement_recommendations(
            db,
            service_key="dtrain-controller",
            prefer_node_id=dtrain.node_id,
            avoid_node_ids=[placement["candidates"][-1]["node_id"]],
            anti_affinity_service_key="dtrain-controller",
            require_healthy=True,
            spread_subsystem=True,
        )
        assert_true(
            constrained_placement["prefer_node_id"] == dtrain.node_id,
            "Placement constraints should include prefer_node_id",
        )
        assert_true(
            len(constrained_placement["avoid_node_ids"]) == 1, "Placement constraints should include avoid_node_ids"
        )
        avoid_for_edge = [node.id for node in nodes if edge_node and node.id != edge_node.id]
        placement_exec = placement_auto_deploy(
            db,
            service_key="option-copilot",
            prefer_node_id=edge_node.id if edge_node else None,
            avoid_node_ids=avoid_for_edge,
            auto_install_dependencies=True,
            allow_capacity_risk=True,
        )
        assert_true(placement_exec["node_id"] == edge_node.id, "Auto placement deploy should target forced edge node")
        assert_true(
            placement_exec["target_job_status"] == "success",
            "Placement auto-deploy target job should succeed in local mode",
        )
        assert_true(
            placement_exec["preflight"]["ok"], "Placement auto-deploy should end with dependency-clean preflight"
        )

        observability = observability_pipeline_report(db)
        assert_true(
            observability["summary"]["total_nodes"] >= 3, "Observability report should include every seeded node"
        )
        assert_true(
            any(node["pipeline_ready"] for node in observability["nodes"]),
            "At least one node should have healthy observability pipeline",
        )

        inventory = generate_inventory(dtrain.node)
        assert_true("[platformops]" in inventory, "Generated inventory missing group")
        compose = generate_compose(db, dtrain.node)
        assert_true(
            "services:" in compose and "dtrain-controller:" in compose, "Generated compose missing DTrain service"
        )

        archives = index_log_archives(db, dtrain)
        assert_true(len(archives) >= 1, "Log archive indexing should include DTrain logs")

        backup = run_backup(db, dtrain)
        assert_true(backup.status == "success", "Backup run should succeed in local simulation")

        snapshot_name = f"verify-dtrain-snapshot-{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}"
        snapshot = create_config_snapshot(db, dtrain, name=snapshot_name, source="verify")
        renamed = rename_config_snapshot(db, snapshot, name=f"verify-dtrain-snapshot-{snapshot.id}")
        assert_true(renamed.name.endswith(str(snapshot.id)), "Snapshot rename did not persist")
        duplicated_named_snapshot = f"release-2.0.0-{datetime.now(UTC).strftime('%H%M%S%f')}"
        duplicate_a = create_config_snapshot(db, dtrain, name=duplicated_named_snapshot, source="verify")
        duplicate_b = create_config_snapshot(db, dtrain, name=duplicated_named_snapshot, source="verify")
        assert_true(
            duplicate_b.name == f"{duplicated_named_snapshot}-v1",
            "Duplicate snapshot names should receive deterministic -vN suffixes",
        )
        install_schema = service_install_schema(db, service_key=dtrain.service_key, node=dtrain.node, service=dtrain)
        assert_true(install_schema["service_key"] == dtrain.service_key, "Install schema should resolve service key")
        assert_true(
            any(field["key"] == "config_files" for field in install_schema["fields"]),
            "Install schema should expose config file fields",
        )
        updated_dtrain = update_service_instance(
            db,
            dtrain,
            name=dtrain.name,
            contract_overrides={"environment": {"DTRAIN_LOG_LEVEL": "DEBUG"}},
        )
        assert_true(
            json.loads(updated_dtrain.config_json)["environment"]["DTRAIN_LOG_LEVEL"] == "DEBUG",
            "Service update should persist typed contract overrides",
        )
        workspace = config_workspace(db, updated_dtrain)
        assert_true(workspace["snapshot_count"] >= 3, "Config workspace should expose snapshot count")
        assert_true("runtime_target" in workspace, "Config workspace should expose runtime target metadata")
        direct_apply = apply_config_direct(
            db,
            updated_dtrain,
            content=workspace["content"],
            apply_mode="reload",
            requested_by="verify-user",
        )
        assert_true(direct_apply["job"].status == "success", "Direct config apply should succeed")
        assert_true(direct_apply["before_snapshot"].id != direct_apply["after_snapshot"].id, "Direct apply should create before/after checkpoints")
        snapshot_compare = compare_config_snapshots(db, dtrain, left_snapshot=duplicate_a, right_snapshot=duplicate_b)
        assert_true(snapshot_compare["service_id"] == dtrain.id, "Snapshot compare should resolve target service")
        assert_true("difference_count" in snapshot_compare, "Snapshot compare should report difference count")
        migration = prepare_config_migration(db, dtrain, left_snapshot=duplicate_a, right_snapshot=duplicate_b)
        assert_true(migration["validation"]["ok"], "Prepared config migration should validate")
        migration_apply = apply_config_migration(db, dtrain, artifact_id=migration["artifact_id"])
        assert_true(migration_apply["job"].status == "success", "Prepared config migration should apply")
        migration_restore = restore_config_migration(db, dtrain, artifact_id=migration["artifact_id"])
        assert_true(migration_restore["job"].status == "success", "Prepared config migration backup should restore")
        page_first = list_config_snapshots_page(db, dtrain, limit=1, offset=0, source_filter="all", search="")
        page_second = list_config_snapshots_page(db, dtrain, limit=1, offset=1, source_filter="all", search="")
        assert_true(page_first["total"] >= 3, "Config snapshots page should report total snapshots")
        assert_true(page_first["has_more"], "Config snapshots pagination should indicate more pages when truncated")
        assert_true(
            page_first["items"][0].id != page_second["items"][0].id,
            "Config snapshots pagination should move offset window",
        )
        filtered = list_config_snapshots_page(
            db, dtrain, limit=10, offset=0, source_filter="verify", search="release-2.0.0"
        )
        assert_true(
            all(item.source == "verify" for item in filtered["items"]),
            "Config snapshot source filter should constrain returned snapshots",
        )
        rename_duplicate_failed = False
        try:
            rename_config_snapshot(db, duplicate_b, name=duplicate_a.name)
        except ValueError:
            rename_duplicate_failed = True
        assert_true(rename_duplicate_failed, "Renaming snapshot to existing name should be rejected")
        restore_job = restore_config_snapshot(db, dtrain, renamed)
        assert_true(restore_job.status == "success", "Snapshot restore should succeed in local simulation")
        timeline_page = get_config_timeline_page(
            db,
            dtrain,
            limit=5,
            offset=0,
            action_filter="all",
            actor_filter="platform-operator",
            search="snapshot",
        )
        assert_true(timeline_page["total"] >= 3, "Config timeline should include capture/rename/restore events")
        assert_true(
            any(item["action"] == "renamed" for item in timeline_page["items"]) or timeline_page["has_more"],
            "Config timeline should expose rename activity",
        )
        restored_only = get_config_timeline_page(
            db,
            dtrain,
            limit=10,
            offset=0,
            action_filter="restored",
            actor_filter="all",
            search="",
        )
        assert_true(
            all(item["action"] == "restored" for item in restored_only["items"]),
            "Config timeline action filter should constrain results",
        )

        risky_service = db.query(ServiceInstance).filter(ServiceInstance.kind == "infrastructure").first()
        assert_true(risky_service is not None, "Seeded topology should include at least one infrastructure service")
        risky_version = f"infra-{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}"
        risky_safety = assess_release_safety(db, risky_service, version=risky_version, image=risky_service.image)
        assert_true(risky_safety["risky"], "Infrastructure service release should require approval")
        risky_release_blocked = False
        try:
            create_release(
                db,
                risky_service,
                version=risky_version,
                image=risky_service.image,
                strategy="rolling",
                notes="verification infra release without approval",
            )
        except PermissionError:
            risky_release_blocked = True
        assert_true(risky_release_blocked, "Risky release should be blocked without approval")
        release_approval = create_release_approval(
            db,
            service=risky_service,
            target_version=risky_version,
            target_image=risky_service.image,
            reason="Planned maintenance window for infrastructure rollout verification",
            requested_by="platform-operator",
            ttl_hours=4,
        )
        approved_release_approval = decide_release_approval(
            db,
            release_approval,
            approver="platform-admin",
            status="approved",
            decision_note="Verified for controlled rollout",
        )
        governed_release = create_release(
            db,
            risky_service,
            version=risky_version,
            image=risky_service.image,
            strategy="rolling",
            notes="verification infra release with approval",
            approval_id=approved_release_approval.id,
        )
        assert_true(governed_release.status == "success", "Approved risky release should succeed")

        release = create_release(
            db,
            dtrain,
            version=f"verify-{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}",
            image=dtrain.image,
            strategy="rolling",
            notes="verification release",
        )
        assert_true(release.status == "success", "Release should succeed in local simulation")
        rollback = rollback_release(db, release)
        assert_true(rollback.status == "success", "Release rollback should succeed in local simulation")

        drift = detect_drift(db, dtrain)
        assert_true(drift.status in {"in-sync", "drifted"}, "Drift report status is invalid")

        findings = run_policy_scan(db)
        persisted_findings = latest_policy_findings(db)
        assert_true(len(persisted_findings) == len(findings), "Policy findings should persist as open findings")

        incident = create_incident(
            db,
            title="Verify DTrain recovery workflow",
            severity="sev3",
            summary="verification incident",
            service=dtrain,
        )
        assert_true(incident.status == "open", "Incident should open")
        runbook = execute_runbook(db, runbook_key="restart-service", incident=incident)
        assert_true(runbook.status == "success", "Runbook should complete successfully")
        resolved = resolve_incident(db, incident)
        assert_true(resolved.status == "resolved", "Incident should resolve")

        service_summary = get_service_summary(db, dtrain.id)
        assert_true(service_summary["service_id"] == dtrain.id, "Service summary should resolve the requested service")
        assert_true(
            service_summary["capabilities"]["container_name"] == dtrain.container_name,
            "Service summary should include service capabilities",
        )
        assert_true(
            service_summary["latest_release"] is not None,
            "Service summary should surface latest release activity",
        )
        assert_true(
            service_summary["latest_runbook"] is not None,
            "Service summary should surface latest runbook activity",
        )
        assert_true(
            isinstance(service_summary["recent_events"], list) and len(service_summary["recent_events"]) >= 1,
            "Service summary should include recent operational events",
        )
        release_timeline = get_service_release_timeline(db, dtrain.id, limit=5)
        assert_true(
            release_timeline["service_id"] == dtrain.id,
            "Release timeline should resolve the requested service",
        )
        assert_true(
            len(release_timeline["items"]) >= 1,
            "Release timeline should include release history entries",
        )
        assert_true(
            isinstance(release_timeline["recent_change_events"], list) and len(release_timeline["recent_change_events"]) >= 1,
            "Release timeline should include correlated change events",
        )
        assert_true(
            release_timeline["latest_rollback_job"] is not None,
            "Release timeline should surface latest rollback job after rollback execution",
        )
        dashboard_summary = get_dashboard_summary(db)
        assert_true(dashboard_summary["clusters"] >= 1, "Dashboard summary should count clusters")
        assert_true(dashboard_summary["nodes"] >= 3, "Dashboard summary should count seeded nodes")
        assert_true(dashboard_summary["services"] >= len(services), "Dashboard summary should count services")
        assert_true(
            isinstance(dashboard_summary["attention_services"], list),
            "Dashboard summary should include attention services list",
        )
        assert_true(
            dashboard_summary["healthy_observability_nodes"] + dashboard_summary["degraded_observability_nodes"] >= 1,
            "Dashboard summary should include observability node status totals",
        )
        node_metrics = get_node_metrics(db, dtrain.node_id, window="24h")
        assert_true(node_metrics["node_id"] == dtrain.node_id, "Node metrics should resolve the requested node")
        assert_true(node_metrics["window"] == "24h", "Node metrics should echo the requested window")
        assert_true(len(node_metrics["cpu_series"]) == 12, "24h node metrics should expose a longer CPU trend series")
        assert_true(any("h" in point["label"] for point in node_metrics["cpu_series"]), "24h node metrics should use hour labels")
        assert_true(node_metrics["network_rx_mbps"] > 0, "Node metrics should include RX throughput")
        service_metrics = get_service_metrics(db, dtrain.id, window="15m")
        assert_true(service_metrics["service_id"] == dtrain.id, "Service metrics should resolve the requested service")
        assert_true(service_metrics["window"] == "15m", "Service metrics should echo the requested window")
        assert_true(len(service_metrics["error_rate_series"]) == 6, "15m service metrics should expose a shorter error-rate trend series")
        assert_true(all("m" in point["label"] for point in service_metrics["error_rate_series"]), "15m service metrics should use minute labels")
        assert_true(service_metrics["latency_ms_p95"] > 0, "Service metrics should include a latency estimate")
        diagnostics_analysis = service_diagnostics_analysis(db, dtrain, source_service=dtrain)
        assert_true(diagnostics_analysis["service_id"] == dtrain.id, "Diagnostics analysis should resolve target service")
        assert_true(len(diagnostics_analysis["insights"]) >= 1, "Diagnostics analysis should produce at least one operator insight")
        assert_true(diagnostics_analysis["overall_severity"] in {"info", "warning", "error"}, "Diagnostics analysis should produce a valid severity")
        assert_true("confidence" in diagnostics_analysis["insights"][0], "Diagnostics insights should expose confidence scores")
        assert_true("evidence_refs" in diagnostics_analysis["insights"][0], "Diagnostics insights should cite evidence references")
        assert_true("supporting_evidence" in diagnostics_analysis["insights"][0], "Diagnostics insights should expose structured supporting evidence")
        assert_true(isinstance(diagnostics_analysis["recent_incidents"], list), "Diagnostics analysis should surface recent incident context")
        assert_true(isinstance(diagnostics_analysis["historical_correlation"], list), "Diagnostics analysis should surface historical correlation hints")
        assert_true(isinstance(diagnostics_analysis["change_evidence"], list), "Diagnostics analysis should surface change evidence")
        if diagnostics_analysis["recent_incidents"]:
            assert_true(
                "suggested_runbook_key" in diagnostics_analysis["recent_incidents"][0],
                "Diagnostics analysis should suggest a runbook key for recent incidents",
            )
        if diagnostics_analysis["change_evidence"]:
            assert_true(
                "confidence" in diagnostics_analysis["change_evidence"][0] and "target_view" in diagnostics_analysis["change_evidence"][0],
                "Diagnostics change evidence should include confidence and navigation target",
            )
            assert_true(
                "compare_left_snapshot_id" in diagnostics_analysis["change_evidence"][0] or "baseline_snapshot_id" in diagnostics_analysis["change_evidence"][0] or diagnostics_analysis["change_evidence"][0]["target_view"] == "release",
                "Diagnostics change evidence should include compare metadata when relevant",
            )
        cluster_ops = get_cluster_operations_view(db, dtrain.node.cluster_id, limit=20)
        assert_true(cluster_ops["cluster_id"] == dtrain.node.cluster_id, "Cluster operations should resolve target cluster")
        assert_true(cluster_ops["total_events"] >= 1, "Cluster operations should include recent events")
        assert_true(
            isinstance(cluster_ops["items"], list) and len(cluster_ops["items"]) >= 1,
            "Cluster operations should provide operation items",
        )

        slo_reports = evaluate_slos(db)
        assert_true(len(slo_reports) >= len(services), "SLO evaluation should cover all services")
        assert_true({report.status for report in slo_reports}.issubset({"passing", "burning"}), "Unexpected SLO status")

        capacity = generate_capacity_report(db, dtrain.node)
        assert_true(capacity.status in {"ok", "risk"}, "Capacity report status is invalid")
        assert_true(capacity.memory_reserved_mb > 0, "Capacity report should reserve memory for seeded services")

        secret = create_secret_record(
            db,
            key=f"VERIFY_DTRAIN_TOKEN_{datetime.now(UTC).strftime('%H%M%S%f')}",
            service=dtrain,
            scope="service",
            rotation_interval_days=30,
        )
        assert_true("VERIFY_DTRAIN_TOKEN" not in secret.masked_value, "Secret value should be masked")
        rotated_secret = rotate_secret_record(db, secret)
        assert_true(rotated_secret.status == "rotated", "Secret rotation should persist")
        assert_true(len(latest_secrets(db)) >= 1, "Secret registry should list records")

        maintenance_start = datetime.now(UTC)
        maintenance = schedule_maintenance(
            db,
            title=f"Verify DTrain maintenance {maintenance_start.strftime('%H%M%S%f')}",
            starts_at=maintenance_start.isoformat(),
            ends_at=(maintenance_start + timedelta(hours=1)).isoformat(),
            impact="verification maintenance window",
            service=dtrain,
        )
        assert_true(maintenance.status == "scheduled", "Maintenance window should be scheduled")
        completed_maintenance = complete_maintenance(db, maintenance)
        assert_true(completed_maintenance.status == "completed", "Maintenance window should complete")
        assert_true(len(latest_maintenance_windows(db)) >= 1, "Maintenance registry should list windows")

        audit = create_audit_export(db, export_type="verify")
        assert_true(audit.status == "ready", "Audit export should be ready")
        assert_true('"services"' in audit.content_json, "Audit export should include service summary")
        assert_true(len(latest_audit_exports(db)) >= 1, "Audit exports should be listed")

        # 1. Capability Metadata Tests
        postgres = db.query(ServiceInstance).filter(ServiceInstance.service_key == "postgres-core").first()
        assert_true(postgres is not None, "PostgreSQL Core instance should be seeded")
        caps = get_service_capabilities(db, postgres.id)
        assert_true(caps["diagnostics"], "PostgreSQL Core should have diagnostics capability")
        assert_true(caps["backup"], "PostgreSQL Core should have backup capability")
        assert_true(caps["config"], "PostgreSQL Core should have config capability")
        assert_true(caps["requires_sudo_for_file_logs"], "PostgreSQL Core should require sudo for file logs")
        option_copilot = db.query(ServiceInstance).filter(ServiceInstance.service_key == "option-copilot").first()
        assert_true(option_copilot is not None, "option-copilot instance should be seeded")
        diagnostics = service_diagnostics(db, option_copilot)
        readiness = diagnostics["readiness"]
        assert_true(
            diagnostics["source_service_key"] == option_copilot.service_key,
            "Diagnostics response should preserve source service context",
        )
        assert_true(
            diagnostics["target_service_key"] == option_copilot.service_key,
            "Diagnostics response should expose target service key",
        )
        assert_true(readiness.get("target_type") == "Main", "App diagnostics should classify target type as Main")
        dependency_targets = readiness.get("dependency_targets", [])
        assert_true(len(dependency_targets) >= 4, "option-copilot diagnostics should include dependency targets")
        assert_true(
            any(target.get("target_type") == "Infrastructure Card" for target in dependency_targets),
            "Dependency targets should label infrastructure cards explicitly",
        )
        backfill = readiness.get("backfill_requirements", {})
        assert_true(backfill.get("ready") is True, "Seeded diagnostics backfill requirements should be ready")
        backfill_result = backfill_service_logs(db, option_copilot)
        assert_true(backfill_result["ready"] is True, "Diagnostics backfill action should run when requirements are ready")
        assert_true(backfill_result["job"].status == "success", "Diagnostics backfill job should succeed in local mode")
        live_logs = service_live_logs(db, option_copilot, tail_lines=120, page_size=60, cursor=0)
        assert_true(live_logs["tail_lines"] == 120, "Live diagnostics should respect tail_lines controls")
        assert_true(live_logs["page_size"] == 60, "Live diagnostics should respect page_size controls")
        assert_true(len(live_logs["lines"]) >= 1, "Live diagnostics should return at least one line")
        history_logs = service_live_logs(db, option_copilot, tail_lines=120, page_size=60, cursor=1)
        assert_true(history_logs["cursor"] == 1, "Live diagnostics history cursor should be preserved")
        assert_true(
            history_logs["next_cursor"] >= history_logs["cursor"],
            "Live diagnostics cursor progression should be monotonic",
        )
        target_catalog = diagnostics_targets_for_service(db, option_copilot)
        assert_true(
            target_catalog[0]["service_key"] == option_copilot.service_key,
            "Diagnostics target catalog should start with source service",
        )
        assert_true(
            any(item["service_key"] == "postgres-core" for item in target_catalog),
            "Diagnostics target catalog should include dependency cards",
        )

        # 2. Lifecycle Impact & Deletion Protection Tests
        # Deleting postgres-core without force must be blocked
        postgres_impact = lifecycle_impact(db, "service", postgres.id)
        assert_true(
            not postgres_impact["can_delete_without_force"], "PostgreSQL Core deletion should be blocked without force"
        )
        assert_true(len(postgres_impact["dependents"]) > 0, "PostgreSQL Core should have dependents on this node")

        # Verify node deletion protection
        node_id = postgres.node_id
        node_impact = lifecycle_impact(db, "node", node_id)
        assert_true(
            not node_impact["can_delete_without_force"], "Node deletion should be blocked due to active services"
        )

        # Verify cluster deletion protection
        cluster_id = postgres.node.cluster_id
        cluster_impact = lifecycle_impact(db, "cluster", cluster_id)
        assert_true(
            not cluster_impact["can_delete_without_force"], "Cluster deletion should be blocked due to active nodes"
        )

        # Test app deletion does not delete infrastructure cards
        rag = db.query(ServiceInstance).filter(ServiceInstance.service_key == "rag").first()
        assert_true(rag is not None, "RAG app should be seeded")
        rag_impact = lifecycle_impact(db, "service", rag.id)
        assert_true(
            rag_impact["can_delete_without_force"], "RAG app should be safe to delete without force if no dependents"
        )

        # Force-delete governance policy checks.
        blocked_policy = evaluate_force_delete_policy(
            db,
            target_type="service",
            target_id=postgres.id,
            impact=postgres_impact,
            force_reason="too short",
        )
        assert_true(
            not blocked_policy["allowed"], "Force delete policy should block weak reason and no maintenance window"
        )
        assert_true(
            any("12 characters" in item for item in blocked_policy["violations"]), "Policy should enforce reason length"
        )
        assert_true(
            any("maintenance window" in item for item in blocked_policy["violations"]),
            "Policy should enforce maintenance window",
        )

        active_start = datetime.now(UTC) - timedelta(minutes=30)
        active_end = datetime.now(UTC) + timedelta(minutes=30)
        active_window = schedule_maintenance(
            db,
            title="Verify active maintenance for force delete policy",
            starts_at=active_start.isoformat(),
            ends_at=active_end.isoformat(),
            impact="policy verification window",
            service=postgres,
        )
        allowed_policy = evaluate_force_delete_policy(
            db,
            target_type="service",
            target_id=postgres.id,
            impact=postgres_impact,
            force_reason="Emergency maintenance for database migration rollback",
        )
        assert_true(
            allowed_policy["allowed"], "Force delete policy should allow with strong reason and active maintenance"
        )
        assert_true(
            active_window.id in allowed_policy["active_window_ids"], "Policy should report active maintenance window id"
        )

        approval = create_force_delete_approval(
            db,
            target_type="service",
            target_id=postgres.id,
            reason="Emergency maintenance for database migration rollback",
            requested_by="verify-user",
            ttl_hours=4,
        )
        assert_true(approval.status == "pending", "Approval should start pending")
        approval_check_pending = validate_force_delete_approval(
            db,
            target_type="service",
            target_id=postgres.id,
            approval_id=approval.id,
        )
        assert_true(not approval_check_pending["allowed"], "Pending approval must not allow force delete")

        decided = decide_force_delete_approval(
            db,
            approval,
            approver="verify-admin",
            status="approved",
            decision_note="approved for controlled verification",
        )
        assert_true(decided.status == "approved", "Approval should be approved")

        self_approval = create_force_delete_approval(
            db,
            target_type="service",
            target_id=postgres.id,
            reason="Second approval request for two-person rule validation",
            requested_by="verify-user",
            ttl_hours=4,
        )
        self_approve_failed = False
        try:
            decide_force_delete_approval(
                db,
                self_approval,
                approver="verify-user",
                status="approved",
                decision_note="self-approval should fail",
            )
        except ValueError:
            self_approve_failed = True
        assert_true(self_approve_failed, "Two-person rule should block self-approval")

        rejected = decide_force_delete_approval(
            db,
            self_approval,
            approver="verify-admin",
            status="rejected",
            decision_note="rejected for governance policy",
        )
        assert_true(rejected.status == "rejected", "Approval should be rejectable")

        revokable = create_force_delete_approval(
            db,
            target_type="service",
            target_id=postgres.id,
            reason="Revocation scenario approval request for governance verification",
            requested_by="verify-user",
            ttl_hours=4,
        )
        revoked = revoke_force_delete_approval(
            db,
            revokable,
            actor="verify-admin",
            note="revoked by governance check",
        )
        assert_true(revoked.status == "revoked", "Approval should be revocable")

        approval_check_approved = validate_force_delete_approval(
            db,
            target_type="service",
            target_id=postgres.id,
            approval_id=decided.id,
        )
        assert_true(approval_check_approved["allowed"], "Approved matching approval should allow force delete")
        mark_force_delete_approval_used(db, decided)
        approval_check_used = validate_force_delete_approval(
            db,
            target_type="service",
            target_id=postgres.id,
            approval_id=decided.id,
        )
        assert_true(not approval_check_used["allowed"], "Consumed approval should no longer allow force delete")
        assert_true(len(latest_force_delete_approvals(db, limit=10)) >= 1, "Approvals should be listable")

        # 3. Subsystem Rollout & Recovery Plan Tests
        # DTrain rollout plan
        dtrain_plan = get_subsystem_rollout_plan(db, node_id, "distributed-training-plane")
        step_keys = [step["service_key"] for step in dtrain_plan["steps"]]
        assert_true("rabbitmq-core" in step_keys, "DTrain plan must include rabbitmq-core")
        assert_true("redis-core" in step_keys, "DTrain plan must include redis-core")
        assert_true("dtrain-tracker" in step_keys, "DTrain plan must include dtrain-tracker")
        assert_true("dtrain-controller" in step_keys, "DTrain plan must include dtrain-controller")
        assert_true("dtrain-worker" in step_keys, "DTrain plan must include dtrain-worker")
        # Assert topological order: tracker before controller, controller before worker
        assert_true(
            step_keys.index("dtrain-tracker") < step_keys.index("dtrain-controller"), "tracker before controller"
        )
        assert_true(step_keys.index("dtrain-controller") < step_keys.index("dtrain-worker"), "controller before worker")

        # Vector plane rollout plan
        vector_plan = get_subsystem_rollout_plan(db, node_id, "vector-plane")
        v_keys = [step["service_key"] for step in vector_plan["steps"]]
        assert_true(v_keys.index("etcd-core") < v_keys.index("milvus-core"), "etcd before milvus")
        assert_true(v_keys.index("minio-core") < v_keys.index("milvus-core"), "minio before milvus")

        # Airflow rollout plan using airflow-postgres and airflow-redis
        airflow_plan = get_subsystem_rollout_plan(db, node_id, "workflow-plane")
        af_keys = [step["service_key"] for step in airflow_plan["steps"]]
        assert_true("airflow-postgres" in af_keys, "Airflow plan must include airflow-postgres")
        assert_true("airflow-redis" in af_keys, "Airflow plan must include airflow-redis")
        assert_true("postgres-core" not in af_keys, "Airflow plan must NOT include global postgres-core")
        assert_true("redis-core" not in af_keys, "Airflow plan must NOT include global redis-core")

        # 4. DTrain Overview Tests
        dtrain_overview = get_dtrain_overview(db)
        assert_true("tracker" in dtrain_overview, "DTrain overview must contain tracker data")
        assert_true("controller" in dtrain_overview, "DTrain overview must contain controller data")
        assert_true("workers" in dtrain_overview, "DTrain overview must contain workers list")
        assert_true(dtrain_overview["metrics"]["active_jobs"] == 2, "DTrain overview must show 2 active jobs")
        assert_true(
            dtrain_overview["dependencies"]["rabbitmq"] in RUNNING_STATUSES, "RabbitMQ dependency must be running"
        )

        # 5. Capability Coverage and Lifecycle Audit Report Tests
        coverage = capability_coverage_report(db)
        assert_true(coverage["total_services"] >= 39, "Coverage must include full catalog")
        assert_true(coverage["diagnostics_ready"] > 0, "Coverage should report diagnostics-ready services")
        assert_true(coverage["backup_ready"] > 0, "Coverage should report backup-ready services")
        postgres_coverage = next((item for item in coverage["items"] if item["service_key"] == "postgres-core"), None)
        assert_true(postgres_coverage is not None, "Coverage must include postgres-core")
        assert_true(postgres_coverage["diagnostics_ready"], "postgres-core diagnostics coverage should be true")
        assert_true(postgres_coverage["backup_ready"], "postgres-core backup coverage should be true")

        record_event(
            db,
            category="lifecycle",
            level="warning",
            message="Delete service 'postgres-core' blocked: contains dependents",
            metadata={"force": False},
        )
        record_event(
            db,
            category="lifecycle",
            level="warning",
            message="Force deleted service 'redis-core' despite warnings",
            metadata={"force": True},
        )
        record_event(
            db,
            category="lifecycle",
            level="info",
            message="Deleted empty node 'verify-node'",
            metadata={"force": False},
        )
        audit_report = lifecycle_audit_report(db, hours=168)
        assert_true(audit_report["blocked_deletions"] >= 1, "Lifecycle audit should count blocked deletions")
        assert_true(audit_report["forced_deletions"] >= 1, "Lifecycle audit should count forced deletions")
        assert_true(audit_report["safe_deletions"] >= 1, "Lifecycle audit should count safe deletions")

        lifecycle_events = list_events(db, limit=50, category="lifecycle")
        assert_true(len(lifecycle_events) >= 3, "Filtered lifecycle events should be returned")
        warning_events = list_events(db, limit=50, category="lifecycle", level="warning")
        assert_true(
            all(event.level == "warning" for event in warning_events), "Level-filtered events must match warning level"
        )
    finally:
        db.close()

    print("PlatformOps verification passed")


if __name__ == "__main__":
    main()
