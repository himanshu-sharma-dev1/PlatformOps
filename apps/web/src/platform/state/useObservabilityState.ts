// @ts-nocheck
import { useState } from "react";
export function useObservabilityState() {
  const [observabilityPipeline, setObservabilityPipeline] = useState(null as any);
  const [observabilityStatus, setObservabilityStatus] = useState(null as any);
  const [observabilityMarker, setObservabilityMarker] = useState("");
  const [observabilityLoading, setObservabilityLoading] = useState(false);
  const [observabilityError, setObservabilityError] = useState("");
  const [artifact, setArtifact] = useState(null as any);
  return {
    observabilityPipeline, setObservabilityPipeline,
    observabilityStatus, setObservabilityStatus,
    observabilityMarker, setObservabilityMarker,
    observabilityLoading, setObservabilityLoading,
    observabilityError, setObservabilityError,
    artifact, setArtifact,
  };
}
