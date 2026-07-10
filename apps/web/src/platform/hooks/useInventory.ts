/**
 * Domain seam: useInventory
 * Related controller fields: clusters, nodes, services, refresh, selectCluster, selectNode
 *
 * Progressive extraction target — currently resolved via full controller.
 */
import { usePlatformController } from "../usePlatformController";

export function useInventory() {
  return usePlatformController();
}
