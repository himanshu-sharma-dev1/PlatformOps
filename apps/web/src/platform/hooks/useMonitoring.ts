/**
 * Domain seam: useMonitoring
 * Related controller fields: gtIssues, loadGlitchTipDataForService, gtActiveMonitorTab
 *
 * Progressive extraction target — currently resolved via full controller.
 */
import { usePlatformController } from "../usePlatformController";

export function useMonitoring() {
  return usePlatformController();
}
