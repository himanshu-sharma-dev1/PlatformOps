// @ts-nocheck
import { api } from "../../api/client";
export function createObservabilityActions(s: any) {
  let statusRequest = 0;
  return {
  async refreshObservabilityStackStatus(serviceId?: number, marker?: string) {
    const redis = (s.services || []).find((item: any) => item.id === serviceId)
      || (s.services || []).find((item: any) => item.id === s.selectedService?.id)
      || (s.services || []).find((item: any) => item.service_key === "redis-core");
    if (!redis?.id) {
      s.setObservabilityStatus(null);
      s.setObservabilityError("Select a Redis service to probe direct observability evidence.");
      return;
    }
    const requestId = ++statusRequest;
    s.setObservabilityLoading(true);
    s.setObservabilityError("");
    try {
      const runMarker = marker ?? s.observabilityMarker ?? "";
      const data = await api(`/api/observability/status?service_id=${redis.id}&marker=${encodeURIComponent(runMarker)}`);
      if (requestId !== statusRequest) return;
      s.setObservabilityStatus(data);
    } catch (e) {
      if (requestId !== statusRequest) return;
      s.setObservabilityStatus(null);
      s.setObservabilityError(e?.message || "Direct observability probes failed");
    } finally {
      if (requestId === statusRequest) s.setObservabilityLoading(false);
    }
  }
  };
}
