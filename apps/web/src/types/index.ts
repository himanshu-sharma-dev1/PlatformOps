/* Shared lightweight types for extracted modules */

export type MetricPoint = {
  label: string;
  value: number;
};

export type MetricWindow = "1h" | "6h" | "24h" | "7d" | "1M" | "3M" | "1m" | "3m";

export const OPERATOR_PREFERENCES_KEY = "platformops.operator.preferences.v1";
