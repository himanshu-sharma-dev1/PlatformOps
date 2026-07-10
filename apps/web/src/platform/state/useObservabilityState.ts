// @ts-nocheck
import { useState } from "react";
export function useObservabilityState() {
  const [observabilityPipeline, setObservabilityPipeline] = useState(null as any);
  const [observabilityBusyNodeId, setObservabilityBusyNodeId] = useState(null as any);
  const [obsStackBusy, setObsStackBusy] = useState("" as any);
  const [obsStackContainers, setObsStackContainers] = useState([] as any);
  const [obsStackOutput, setObsStackOutput] = useState("" as any);
  const [artifact, setArtifact] = useState(null as any);
  return {
    observabilityPipeline, setObservabilityPipeline,
    observabilityBusyNodeId, setObservabilityBusyNodeId,
    obsStackBusy, setObsStackBusy,
    obsStackContainers, setObsStackContainers,
    obsStackOutput, setObsStackOutput,
    artifact, setArtifact,
  };
}
