import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const SEVERITY_TONE: Record<string, "danger" | "warning" | "success" | "accent" | "neutral" | "critical"> = {
  CRITICAL: "critical", HIGH: "danger", MEDIUM: "warning", LOW: "success", INFO: "accent", UNDETERMINED: "neutral",
};

export const STATUS_TONE: Record<string, "neutral" | "primary" | "warning" | "success" | "danger" | "accent"> = {
  DRAFT: "neutral", SUBMITTED: "primary", DOCUMENT_PROCESSING: "accent", AI_ANALYSIS: "accent", PENDING_HUMAN_REVIEW: "warning",
  ADDITIONAL_INFORMATION_REQUIRED: "danger", APPROVED_FOR_NEXT_REVIEW_STAGE: "success", CLOSED: "neutral",
  PENDING_REVIEW: "warning", RETURNED: "danger", APPROVED_FOR_NEXT_STAGE: "success", REJECTED: "danger", SUPERSEDED: "neutral",
  AWAITING_REVIEW: "warning", RUNNING: "accent", QUEUED: "neutral", FAILED: "danger", SUCCEEDED: "success",
};

export function bytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}
