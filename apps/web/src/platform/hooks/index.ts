/**
 * Phase 2 domain hooks.
 * Today the controller is still composed in usePlatformController for call-site stability.
 * These modules document seams and re-export slices for progressive extraction.
 */
export { usePlatformController as useOpsController } from "../usePlatformController";
