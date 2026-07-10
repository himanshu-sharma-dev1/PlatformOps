// @ts-nocheck
import { useAuthState } from "./state/useAuthState";
import { useInventoryState } from "./state/useInventoryState";
import { useConfigState } from "./state/useConfigState";
import { useDiagnosticsState } from "./state/useDiagnosticsState";
import { useMonitoringState } from "./state/useMonitoringState";
import { usePerformanceState } from "./state/usePerformanceState";
import { useSreState } from "./state/useSreState";
import { useObservabilityState } from "./state/useObservabilityState";
import { useUiState } from "./state/useUiState";

export function usePlatformState() {
  return {
    ...useUiState(),
    ...useAuthState(),
    ...useInventoryState(),
    ...useConfigState(),
    ...useDiagnosticsState(),
    ...useMonitoringState(),
    ...usePerformanceState(),
    ...useSreState(),
    ...useObservabilityState(),
  };
}
