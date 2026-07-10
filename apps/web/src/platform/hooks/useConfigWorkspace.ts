/**
 * Domain seam: useConfigWorkspace
 * Related controller fields: config, loadConfig, applyCurrentConfig, configTab
 *
 * Progressive extraction target — currently resolved via full controller.
 */
import { usePlatformController } from "../usePlatformController";

export function useConfigWorkspace() {
  return usePlatformController();
}
