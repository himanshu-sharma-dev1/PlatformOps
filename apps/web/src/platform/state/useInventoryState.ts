// @ts-nocheck
import { useState } from "react";
export function useInventoryState() {
  const [catalog, setCatalog] = useState([] as any);
  const [clusters, setClusters] = useState([] as any);
  const [nodes, setNodes] = useState([] as any);
  const [services, setServices] = useState([] as any);
  const [selectedService, setSelectedService] = useState(null as any);
  const [serviceSummary, setServiceSummary] = useState(null as any);
  const [serviceReleaseTimeline, setServiceReleaseTimeline] = useState(null as any);
  const [dashboardSummary, setDashboardSummary] = useState(null as any);
  const [clusterOperations, setClusterOperations] = useState(null as any);
  const [job, setJob] = useState(null as any);
  const [gtSelectedServiceId, setGtSelectedServiceId] = useState(null as any);
  const [selectedCluster, setSelectedCluster] = useState(null as any);
  const [selectedNode, setSelectedNode] = useState(null as any);
  const [clusterEditor, setClusterEditor] = useState({
    visible: false,
    mode: "create",
    clusterId: null,
    step: 1,
    saving: false,
    replaceRepoSecret: false,
    replaceRegistrySecret: false,
    repoTest: { state: "idle", message: "" },
    registryTest: { state: "idle", message: "" },
    draft: {
      name: "",
      region: "local",
      environment: "development",
      description: "",
      repo_type: "github",
      repo_url: "",
      repo_branch: "main",
      repo_token: "",
      registry_type: "dockerhub",
      registry_url: "",
      registry_user: "",
      registry_password: "",
    },
    error: "",
  } as any);
  const [nodeEditor, setNodeEditor] = useState({
    visible: false,
    mode: "create",
    nodeId: null,
    draft: {
      cluster_id: 0,
      name: "",
      host: "",
      ssh_user: "ubuntu",
      ssh_key_path: "",
      ssh_private_key: "",
      environment: "local",
      volume_root: "/tmp/platformops",
      docker_network: "platformops_prod_network",
      status: "unknown",
      cpu_cores: 4,
      memory_gb: 16,
      storage_gb: 100,
      gpu: "none",
      os: "linux",
    },
    error: "",
  } as any);
  const [nodePreset, setNodePreset] = useState("local-default" as any);
  const [clusterSummary, setClusterSummary] = useState(null as any);
  const [nodeSummary, setNodeSummary] = useState(null as any);
  const [nodeJobHistory, setNodeJobHistory] = useState(null as any);
  const [nodeConnection, setNodeConnection] = useState(null as any);
  const [nodeOnboarding, setNodeOnboarding] = useState(null as any);
  const [onboardingActionBusy, setOnboardingActionBusy] = useState("" as any);
  const [onboardingJobId, setOnboardingJobId] = useState(null as any);
  const [onboardingOutput, setOnboardingOutput] = useState("" as any);
  const [onboardingError, setOnboardingError] = useState("" as any);
  const [onboardingStatus, setOnboardingStatus] = useState("running" as any);
  const [catalogOnboarding, setCatalogOnboarding] = useState({
    visible: false,
    mode: "create",
    card: null,
    editingService: null,
    installSchema: null,
    installFieldValues: {},
    nodeId: 0,
    customName: "",
    nextAction: "deploy",
    overridesText: "",
    creating: false,
    error: "",
    registeredService: null,
    validationConflict: null,
    validating: false,
  } as any);
  /** Live docker status by service id (Clusters poll). */
  const [serviceLiveById, setServiceLiveById] = useState({} as any);
  const [nodeLiveStatus, setNodeLiveStatus] = useState(null as any);
  return {
    catalog, setCatalog,
    clusters, setClusters,
    nodes, setNodes,
    services, setServices,
    selectedService, setSelectedService,
    serviceSummary, setServiceSummary,
    serviceReleaseTimeline, setServiceReleaseTimeline,
    dashboardSummary, setDashboardSummary,
    clusterOperations, setClusterOperations,
    job, setJob,
    gtSelectedServiceId, setGtSelectedServiceId,
    selectedCluster, setSelectedCluster,
    selectedNode, setSelectedNode,
    clusterEditor, setClusterEditor,
    nodeEditor, setNodeEditor,
    nodePreset, setNodePreset,
    clusterSummary, setClusterSummary,
    nodeSummary, setNodeSummary,
    nodeJobHistory, setNodeJobHistory,
    nodeConnection, setNodeConnection,
    nodeOnboarding, setNodeOnboarding,
    onboardingActionBusy, setOnboardingActionBusy,
    onboardingJobId, setOnboardingJobId,
    onboardingOutput, setOnboardingOutput,
    onboardingError, setOnboardingError,
    onboardingStatus, setOnboardingStatus,
    catalogOnboarding, setCatalogOnboarding,
    serviceLiveById, setServiceLiveById,
    nodeLiveStatus, setNodeLiveStatus,
  };
}
