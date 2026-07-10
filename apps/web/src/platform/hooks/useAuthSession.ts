/**
 * Domain seam: useAuthSession
 * Related controller fields: authUser, loginForm, handleLogin, handleLogout, authReady
 *
 * Progressive extraction target — currently resolved via full controller.
 */
import { usePlatformController } from "../usePlatformController";

export function useAuthSession() {
  return usePlatformController();
}
