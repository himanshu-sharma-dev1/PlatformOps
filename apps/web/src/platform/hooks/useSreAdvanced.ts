/**
 * Domain seam: useSreAdvanced
 * Related controller fields: topology, findings, slos, incidents, maintenance
 *
 * Progressive extraction target — currently resolved via full controller.
 */
import { usePlatformController } from "../usePlatformController";

export function useSreAdvanced() {
  return usePlatformController();
}
