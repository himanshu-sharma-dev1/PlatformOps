/**
 * Domain seam: useDiagnostics
 * Related controller fields: diagnostics, loadDiagnostics, diagnosticsLive, diagTab
 *
 * Progressive extraction target — currently resolved via full controller.
 */
import { usePlatformController } from "../usePlatformController";

export function useDiagnostics() {
  return usePlatformController();
}
