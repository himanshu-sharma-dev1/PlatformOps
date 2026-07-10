/**
 * Domain seam: useUiChrome
 * Related controller fields: notice, drawers/modals visibility flags
 *
 * Progressive extraction target — currently resolved via full controller.
 */
import { usePlatformController } from "../usePlatformController";

export function useUiChrome() {
  return usePlatformController();
}
