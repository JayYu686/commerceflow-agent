import type { ReactNode } from "react";

type BadgeProps = {
  children: ReactNode;
  tone?: "neutral" | "success" | "warning" | "danger" | "critical" | "info";
};

const tones: Record<NonNullable<BadgeProps["tone"]>, string> = {
  neutral: "border-slate-200 bg-slate-100 text-slate-700",
  success: "border-emerald-200 bg-emerald-50 text-emerald-700",
  warning: "border-amber-200 bg-amber-50 text-amber-800",
  danger: "border-red-200 bg-red-50 text-red-700",
  critical: "border-red-300 bg-red-100 text-red-900",
  info: "border-sky-200 bg-sky-50 text-sky-700",
};

export function Badge({ children, tone = "neutral" }: BadgeProps) {
  return (
    <span className={`inline-flex items-center rounded border px-2 py-0.5 text-xs font-semibold ${tones[tone]}`}>
      {children}
    </span>
  );
}

export function toneForRisk(risk?: string): BadgeProps["tone"] {
  if (risk === "critical") {
    return "critical";
  }
  if (risk === "high") {
    return "danger";
  }
  if (risk === "medium") {
    return "warning";
  }
  if (risk === "low") {
    return "success";
  }
  return "neutral";
}

export function toneForStatus(status?: string): BadgeProps["tone"] {
  if (status === "completed" || status === "planned" || status === "approved") {
    return "success";
  }
  if (status === "pending_approval" || status === "preview_only" || status === "not_executed") {
    return "warning";
  }
  if (status === "blocked" || status === "critical" || status === "not_executable") {
    return "critical";
  }
  if (status === "not_found" || status === "no_policy_evidence") {
    return "danger";
  }
  return "neutral";
}
