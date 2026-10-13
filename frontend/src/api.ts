import type { Evaluation } from "./types";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  evaluation: Evaluation | null;

  constructor(status: number, detail: unknown) {
    super(readMessage(detail));
    this.status = status;
    this.detail = detail;
    this.evaluation = readEvaluation(detail);
  }
}

function readMessage(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => (item && typeof item === "object" && "msg" in item ? String(item.msg) : "Check the form")).join(" ");
  }
  if (detail && typeof detail === "object" && "message" in detail) return String((detail as { message: unknown }).message);
  return "The request could not be completed";
}

function readEvaluation(detail: unknown): Evaluation | null {
  if (detail && typeof detail === "object" && "evaluation" in detail) {
    return (detail as { evaluation: Evaluation }).evaluation;
  }
  return null;
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  const method = (options.method || "GET").toUpperCase();
  if (method !== "GET" && method !== "HEAD") headers.set("X-Requested-With", "placement");
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(path, { ...options, headers, credentials: "include" });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;
  if (response.status === 401 && !path.startsWith("/api/auth/login") && !path.startsWith("/api/auth/mfa")) {
    window.dispatchEvent(new Event("placement-unauthorized"));
  }
  if (!response.ok) throw new ApiError(response.status, payload?.detail ?? payload);
  return payload as T;
}

export async function download(path: string, filename: string) {
  const response = await fetch(path, { credentials: "include" });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new ApiError(response.status, payload?.detail ?? "Export failed");
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export function todayInput() {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
}

export function formatNumber(value: number | null | undefined, digits = 2) {
  if (value == null) return "—";
  return value.toLocaleString("en-IN", { maximumFractionDigits: digits, minimumFractionDigits: Number.isInteger(value) ? 0 : digits });
}
