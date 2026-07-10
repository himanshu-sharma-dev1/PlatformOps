// @ts-nocheck
import { useState } from "react";
export function useConfigState() {
  const [configTimelinePage, setConfigTimelinePage] = useState(null as any);
  const [configTimelineAction, setConfigTimelineAction] = useState("all" as any);
  const [configTimelineActor, setConfigTimelineActor] = useState("all" as any);
  const [configTimelineSearch, setConfigTimelineSearch] = useState("" as any);
  const [configTimelineCreatedAfter, setConfigTimelineCreatedAfter] = useState("" as any);
  const [configTimelineCreatedBefore, setConfigTimelineCreatedBefore] = useState("" as any);
  const [configTimelineLimit, setConfigTimelineLimit] = useState(10 as any);
  const [config, setConfig] = useState(null as any);
  const [snapshotPage, setSnapshotPage] = useState(null as any);
  const [snapshotCompare, setSnapshotCompare] = useState(null as any);
  const [snapshotSourceFilter, setSnapshotSourceFilter] = useState("all" as any);
  const [checkpointFilter, setCheckpointFilter] = useState("all" as any);
  const [checkpointSearch, setCheckpointSearch] = useState("" as any);
  const [selectedSnapshotPreview, setSelectedSnapshotPreview] = useState(null as any);
  const [snapshotSearch, setSnapshotSearch] = useState("" as any);
  const [snapshotLimit, setSnapshotLimit] = useState(20 as any);
  const [migrationArtifactId, setMigrationArtifactId] = useState("" as any);
  const [migrationContent, setMigrationContent] = useState("" as any);
  const [migrationValidation, setMigrationValidation] = useState("" as any);
  const [migrationApplyResult, setMigrationApplyResult] = useState(null as any);
  const [configEditMode, setConfigEditMode] = useState(false as any);
  const [configApplyMode, setConfigApplyMode] = useState("reload" as any);
  const [configSource, setConfigSource] = useState("live" as any);
  const [capabilities, setCapabilities] = useState(null as any);
  const [configTab, setConfigTab] = useState("current" as any);
  const [compareSnapshotLeft, setCompareSnapshotLeft] = useState(null as any);
  const [compareSnapshotRight, setCompareSnapshotRight] = useState(null as any);
  return {
    configTimelinePage, setConfigTimelinePage,
    configTimelineAction, setConfigTimelineAction,
    configTimelineActor, setConfigTimelineActor,
    configTimelineSearch, setConfigTimelineSearch,
    configTimelineCreatedAfter, setConfigTimelineCreatedAfter,
    configTimelineCreatedBefore, setConfigTimelineCreatedBefore,
    configTimelineLimit, setConfigTimelineLimit,
    config, setConfig,
    snapshotPage, setSnapshotPage,
    snapshotCompare, setSnapshotCompare,
    snapshotSourceFilter, setSnapshotSourceFilter,
    checkpointFilter, setCheckpointFilter,
    checkpointSearch, setCheckpointSearch,
    selectedSnapshotPreview, setSelectedSnapshotPreview,
    snapshotSearch, setSnapshotSearch,
    snapshotLimit, setSnapshotLimit,
    migrationArtifactId, setMigrationArtifactId,
    migrationContent, setMigrationContent,
    migrationValidation, setMigrationValidation,
    migrationApplyResult, setMigrationApplyResult,
    configEditMode, setConfigEditMode,
    configApplyMode, setConfigApplyMode,
    configSource, setConfigSource,
    capabilities, setCapabilities,
    configTab, setConfigTab,
    compareSnapshotLeft, setCompareSnapshotLeft,
    compareSnapshotRight, setCompareSnapshotRight,
  };
}
