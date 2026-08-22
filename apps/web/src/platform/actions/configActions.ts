// @ts-nocheck
import { api, getAuthToken, setAuthToken } from "../../api/client";
export function createConfigActions(s: any) {
  let configLoadGeneration = 0;
  const isCurrentConfigRequest = (serviceId: number, generation?: number) => (
    s.selectedService?.id === serviceId
    && (generation === undefined || generation === configLoadGeneration)
  );
  const errorMessage = (error: any) => error instanceof Error ? error.message : String(error);
  return {
  async loadConfigTimeline(serviceId, options) {
    const nextOffset = options?.offset ?? 0;
    const params = new URLSearchParams({
      limit: String(s.configTimelineLimit),
      offset: String(nextOffset),
      action: s.configTimelineAction,
      actor: s.configTimelineActor,
      search: s.configTimelineSearch.trim(),
      created_after: s.configTimelineCreatedAfter.trim(),
      created_before: s.configTimelineCreatedBefore.trim()
    });
    const next = await api(`/api/services/${serviceId}/config/timeline?${params.toString()}`);
    if (!isCurrentConfigRequest(serviceId, options?.generation)) return;
    if (options?.append && s.configTimelinePage) {
      s.setConfigTimelinePage({
        ...next,
        items: [...s.configTimelinePage.items, ...next.items]
      });
      if (!options?.silent) {
        s.setNotice(`Loaded ${next.items.length} more config timeline events.`);
      }
      return;
    }
    s.setConfigTimelinePage(next);
    if (!options?.silent) {
      s.setNotice(`Loaded ${next.items.length} config timeline events (${next.total} total).`);
    }
  },

  async loadConfigSnapshots(service, options) {
    const nextOffset = options?.offset ?? 0;
    const nextSource = options?.source ?? s.snapshotSourceFilter;
    const nextSearch = options?.search ?? s.snapshotSearch;
    const nextLimit = options?.limit ?? s.snapshotLimit;
    const params = new URLSearchParams({
      offset: String(nextOffset),
      limit: String(nextLimit),
      source: nextSource,
      search: nextSearch
    });
    const next = await api(`/api/services/${service.id}/config/snapshots?${params.toString()}`);
    if (!isCurrentConfigRequest(service.id, options?.generation)) return;
    if (options?.append && s.snapshotPage) {
      s.setSnapshotPage({
        ...next,
        items: [...s.snapshotPage.items, ...next.items]
      });
      return;
    }
    s.setSnapshotPage(next);
  },

  async loadConfig(service, source = s.configSource) {
    const generation = ++configLoadGeneration;
    s.setSelectedService(service);
    s.setConfigLoading?.(true);
    s.setConfigError?.("");
    // Clear target-scoped state immediately; an older request must not leave
    // another service's editor/checkpoints visible during a slow load.
    s.setConfig?.(null);
    s.setSnapshotPage?.(null);
    s.setConfigTimelinePage?.(null);
    s.setSelectedSnapshotPreview?.(null);
    s.setSnapshotCompare?.(null);
    try {
      await s.loadServiceCapabilities(service.id);
      await s.loadServiceSummary(service.id);
      await s.loadServiceReleaseTimeline(service.id);
      await s.loadServiceMetrics(service.id);
      if (!isCurrentConfigRequest(service.id, generation)) return;
      const [next] = await Promise.all([
        api(`/api/services/${service.id}/config?source=${encodeURIComponent(source)}`),
        s.loadConfigTimeline(service.id, { offset: 0, silent: true, generation })
      ]);
      if (!isCurrentConfigRequest(service.id, generation)) return;
      s.setConfig(next);
      s.setConfigSource(source);
      await s.loadConfigSnapshots(service, { offset: 0, generation });
      if (!isCurrentConfigRequest(service.id, generation)) return;
      s.setSnapshotCompare(null);
      s.setNotice(next.message || `Loaded ${source} config for ${service.name}`);
    } catch (error) {
      if (!isCurrentConfigRequest(service.id, generation)) return;
      const message = errorMessage(error);
      s.setConfigError?.(message);
      s.setNotice(`Config load failed: ${message}`);
    } finally {
      if (isCurrentConfigRequest(service.id, generation)) s.setConfigLoading?.(false);
    }
  },

  async viewSnapshot(snapshotId) {
    const serviceId = s.selectedService?.id;
    if (!serviceId) return;
    try {
      const snapDetail = await api(`/api/services/${serviceId}/config/snapshots/${snapshotId}`);
      if (!isCurrentConfigRequest(serviceId)) return;
      s.setSelectedSnapshotPreview(snapDetail);
      s.setNotice(`Loaded snapshot v${snapDetail.version}`);
    } catch (err) {
      console.error(err);
      if (isCurrentConfigRequest(serviceId)) s.setNotice(`Failed to load snapshot preview: ${errorMessage(err)}`);
    }
  },

  async syncPeerConfig(peerServiceId, peerName) {
    const serviceId = s.selectedService?.id;
    if (!serviceId) return;
    try {
      s.setNotice(`Syncing validated config to peer ${peerName}...`);
      const result = await api(`/api/services/${serviceId}/config/sync-peer`, {
        method: "POST",
        body: JSON.stringify({
          peer_id: peerServiceId,
          apply_mode: s.configApplyMode,
          requested_by: "platform-operator"
        })
      });
      if (!isCurrentConfigRequest(serviceId)) return;
      s.setJob(result.job);
      const checkpoint = result.after_snapshot
        ? `checkpoint v${result.before_snapshot.version} -> v${result.after_snapshot.version}`
        : `pre-apply checkpoint v${result.before_snapshot.version}; no post-apply checkpoint was created`;
      s.setNotice(`Peer sync to ${peerName} ${result.job.status}: ${checkpoint}${result.job.error ? ` (${result.job.error})` : ""}`);
      await s.refresh();
    } catch (err) {
      console.error(err);
      s.setNotice(`Peer sync failed: ${err instanceof Error ? err.message : String(err)}`);
    }
  },

  async compareSelectedSnapshots() {
    const serviceId = s.selectedService?.id;
    if (!serviceId || !s.compareSnapshotLeft || !s.compareSnapshotRight) return;
    const next = await api(
      `/api/services/${serviceId}/config/compare?left_snapshot_id=${s.compareSnapshotLeft}&right_snapshot_id=${s.compareSnapshotRight}`
    );
    if (!isCurrentConfigRequest(serviceId)) return;
    s.setSnapshotCompare(next);
    s.setNotice(next.summary);
  },

  async compareSpecificSnapshots(service, leftSnapshotId, rightSnapshotId) {
    if (!leftSnapshotId || !rightSnapshotId) {
      s.setNotice("Snapshot compare needs both baseline and target snapshot ids.");
      return;
    }
    s.setCompareSnapshotLeft(leftSnapshotId);
    s.setCompareSnapshotRight(rightSnapshotId);
    const next = await api(
      `/api/services/${service.id}/config/compare?left_snapshot_id=${leftSnapshotId}&right_snapshot_id=${rightSnapshotId}`
    );
    if (!isCurrentConfigRequest(service.id)) return;
    s.setSnapshotCompare(next);
    s.setNotice(next.summary);
  },

  async detectConfigDrift() {
    const serviceId = s.selectedService?.id;
    if (!serviceId) return;
    const report = await api(`/api/services/${serviceId}/config/drift`, {
      method: "POST"
    }).catch((error) => {
      if (isCurrentConfigRequest(serviceId)) s.setNotice(`Drift check failed: ${errorMessage(error)}`);
      return null;
    });
    if (!report) return;
    if (!isCurrentConfigRequest(serviceId)) return;
    s.setDrift(report);
    s.setNotice(`Drift status: ${report.status}`);
    await s.refresh();
  },

  async captureSnapshot() {
    const service = s.selectedService;
    if (!service) return;
    const captured = await api(`/api/services/${service.id}/config/snapshots`, {
      method: "POST",
      body: JSON.stringify({ source: "ui-capture", requested_by: "platform-operator" })
    }).catch((error) => {
      if (isCurrentConfigRequest(service.id)) s.setNotice(`Snapshot capture failed: ${errorMessage(error)}`);
      return null;
    });
    if (!captured) return;
    if (!isCurrentConfigRequest(service.id)) return;
    await s.loadConfig(service, s.configSource);
    s.setNotice("Captured configuration snapshot");
  },

  async applyCurrentConfig() {
    const service = s.selectedService;
    const workspace = s.config;
    if (!service || !workspace) return;
    const result = await api(`/api/services/${service.id}/config/direct-apply`, {
      method: "POST",
      body: JSON.stringify({
        content: workspace.content,
        apply_mode: s.configApplyMode,
        expected_content_hash: workspace.live_content_hash || workspace.content_hash || "",
        requested_by: "platform-operator",
      })
    }).catch((error) => {
      if (isCurrentConfigRequest(service.id)) s.setNotice(`Config apply failed: ${errorMessage(error)}`);
      return null;
    });
    if (!result) return;
    if (!isCurrentConfigRequest(service.id)) return;
    s.setJob(result.job);
    const checkpoint = result.after_snapshot
      ? `checkpoint v${result.before_snapshot.version} -> v${result.after_snapshot.version}`
      : `pre-apply checkpoint v${result.before_snapshot.version}; no post-apply checkpoint was created`;
    s.setNotice(`Config apply (${s.configApplyMode}) ${result.job.status}: ${checkpoint}${result.job.error ? ` (${result.job.error})` : ""}`);
    await s.loadConfig(service, s.configSource);
    await s.refresh();
  },

  async prepareConfigMigration() {
    const service = s.selectedService;
    if (!service || !s.compareSnapshotLeft || !s.compareSnapshotRight) {
      s.setNotice("Choose baseline and target snapshots before preparing migration.");
      return;
    }
    const prepared = await api(`/api/services/${service.id}/config/migration/prepare`, {
      method: "POST",
      body: JSON.stringify({
        left_snapshot_id: s.compareSnapshotLeft,
        right_snapshot_id: s.compareSnapshotRight
      })
    }).catch((error) => {
      if (isCurrentConfigRequest(service.id)) s.setNotice(`Migration preparation failed: ${errorMessage(error)}`);
      return null;
    });
    if (!prepared) return;
    if (!isCurrentConfigRequest(service.id)) return;
    s.setMigrationArtifactId(prepared.artifact_id);
    s.setMigrationContent(prepared.final_content);
    s.setMigrationValidation(prepared.validation.message);
    s.setMigrationApplyResult(null);
    s.setNotice(`Prepared migration artifact ${prepared.artifact_id}`);
  },

  async validateMigrationYaml() {
    const serviceId = s.selectedService?.id;
    if (!serviceId || !s.migrationContent.trim()) {
      s.setMigrationValidation("Prepare or paste migration config first.");
      return;
    }
    try {
      const validation = await api(`/api/services/${serviceId}/config/validate`, {
        method: "POST",
        body: JSON.stringify({ content: s.migrationContent })
      });
      if (!isCurrentConfigRequest(serviceId)) return;
      s.setMigrationValidation(validation.message);
      s.setNotice(validation.message);
    } catch (error) {
      if (isCurrentConfigRequest(serviceId)) {
        const message = `Validation failed: ${errorMessage(error)}`;
        s.setMigrationValidation(message);
        s.setNotice(message);
      }
    }
  },

  async applyPreparedMigration() {
    const service = s.selectedService;
    if (!service || !s.migrationArtifactId) {
      s.setNotice("Prepare a migration artifact first.");
      return;
    }
    const result = await api(`/api/services/${service.id}/config/migration/apply`, {
      method: "POST",
      body: JSON.stringify({
        artifact_id: s.migrationArtifactId,
        edited_yaml: s.migrationContent,
        apply_mode: s.configApplyMode,
        expected_content_hash: s.config?.live_content_hash || s.config?.content_hash || "",
      })
    }).catch((error) => {
      if (isCurrentConfigRequest(service.id)) s.setNotice(`Migration apply failed: ${errorMessage(error)}`);
      return null;
    });
    if (!result) return;
    if (!isCurrentConfigRequest(service.id)) return;
    s.setMigrationApplyResult(result);
    s.setJob(result.job);
    s.setNotice(`Migration apply ${result.job.status}`);
    await s.loadConfig(service, s.configSource);
    await s.refresh();
  },

  async restorePreparedMigration() {
    const service = s.selectedService;
    if (!service || !s.migrationArtifactId) {
      s.setNotice("No migration artifact has a backup checkpoint yet.");
      return;
    }
    const result = await api(`/api/services/${service.id}/config/migration/restore`, {
      method: "POST",
      body: JSON.stringify({ artifact_id: s.migrationArtifactId, apply_mode: s.configApplyMode, expected_content_hash: s.config?.live_content_hash || s.config?.content_hash || "" })
    }).catch((error) => {
      if (isCurrentConfigRequest(service.id)) s.setNotice(`Migration restore failed: ${errorMessage(error)}`);
      return null;
    });
    if (!result) return;
    if (!isCurrentConfigRequest(service.id)) return;
    s.setMigrationApplyResult(result);
    s.setJob(result.job);
    s.setNotice(`Migration restore ${result.job.status}`);
    await s.loadConfig(service, s.configSource);
    await s.refresh();
  },

  openRenameSnapshot(snapshotId, currentName) {
    s.setRenameModal({
      visible: true,
      snapshotId,
      value: currentName,
      error: ""
    });
  },

  async renameSnapshot() {
    if (!s.selectedService) return;
    const trimmed = s.renameModal.value.trim();
    if (!trimmed) {
      s.setRenameModal((current) => ({ ...current, error: "Snapshot name cannot be empty." }));
      return;
    }
    const conflicts = (s.snapshotPage?.items ?? []).some(
      (snapshot) => snapshot.id !== s.renameModal.snapshotId && snapshot.name.trim().toLowerCase() === trimmed.toLowerCase()
    );
    if (conflicts) {
      s.setRenameModal((current) => ({ ...current, error: "Snapshot name already exists. Choose a unique name." }));
      return;
    }
    try {
      await api(`/api/services/${s.selectedService.id}/config/snapshots/${s.renameModal.snapshotId}/rename`, {
        method: "POST",
        body: JSON.stringify({
          name: trimmed,
          requested_by: "platform-operator",
          expected_version: (s.snapshotPage?.items ?? []).find((item) => item.id === s.renameModal.snapshotId)?.version ?? null,
        })
      });
      if (!isCurrentConfigRequest(s.selectedService.id)) return;
      s.setRenameModal({ visible: false, snapshotId: 0, value: "", error: "" });
      await s.loadConfig(s.selectedService, s.configSource);
      s.setNotice(`Renamed snapshot to ${trimmed}`);
    } catch (error) {
      s.setRenameModal((current) => ({
        ...current,
        error: error.message || "Rename failed. Snapshot names must be unique."
      }));
    }
  },

  async restoreSnapshot(snapshotId) {
    const service = s.selectedService;
    if (!service) return;
    const nextJob = await api(`/api/services/${service.id}/config/snapshots/${snapshotId}/restore`, {
      method: "POST",
      body: JSON.stringify({
        requested_by: "platform-operator",
        expected_content_hash: s.config?.live_content_hash || s.config?.content_hash || "",
      })
    }).catch((error) => {
      if (isCurrentConfigRequest(service.id)) s.setNotice(`Snapshot restore failed: ${errorMessage(error)}`);
      return null;
    });
    if (!nextJob) return;
    if (!isCurrentConfigRequest(service.id)) return;
    s.setJob(nextJob);
    s.setNotice(`Snapshot restore ${nextJob.status}`);
    await s.loadConfigTimeline(service.id, { offset: 0, silent: true });
    await s.loadConfigSnapshots(service, { offset: 0 });
    await s.refresh();
  },

  getConfigStrategy(caps, service) {
    if (!caps || !service) return "Loading...";
    if (caps.config) return "Live config file";
    if (service.kind === "helper") return "No external config";
    return "Catalog-generated config";
  },

  getBackupStrategy(caps, service) {
    if (!caps || !service) return "Loading...";
    if (!caps.backup) return "no backup required";
    const key = service.service_key;
    if (["postgres-core", "airflow-postgres", "clickhouse-core", "milvus-core"].includes(key)) {
      return "database dumps";
    }
    if (["redis-core", "airflow-redis", "rabbitmq-core", "etcd-core"].includes(key)) {
      return "volume archives";
    }
    if (["minio-core"].includes(key)) {
      return "object-store archives";
    }
    return "config-only backups";
  },

  formatLocalTimestamp(value) {
    if (!value) return "--";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return value;
    return parsed.toLocaleString();
  }
  };
}
