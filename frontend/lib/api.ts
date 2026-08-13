import {
  ComplaintRecord,
  DashboardStats,
  VoiceComplaintResponse,
} from "./types";

/** Same-origin proxy fallback; prefer direct backend URL in the browser to avoid proxy timeouts. */
function apiBase(): string {
  const direct = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "");
  if (typeof window !== "undefined") {
    return direct || "/backend";
  }
  return direct || "http://localhost:8080";
}

export function feedbackAudioSrc(
  audioBase64: string,
  mime = "audio/mpeg",
): string {
  return `data:${mime};base64,${audioBase64}`;
}

export async function submitTextComplaint(
  transcript: string
): Promise<VoiceComplaintResponse> {
  let res: Response;
  try {
    res = await fetch(`${apiBase()}/api/complaints/voice`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ transcript: transcript.trim() }),
    });
  } catch {
    throw new Error(
      "Could not reach the server. If processing took too long, check the dashboard — your complaint may still have been saved."
    );
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Submission failed" }));
    const msg =
      typeof err.detail === "string"
        ? err.detail
        : Array.isArray(err.detail)
          ? err.detail[0]?.msg
          : "Submission failed";
    throw new Error(msg);
  }
  return res.json();
}

export async function getComplaints(): Promise<ComplaintRecord[]> {
  const res = await fetch(`${apiBase()}/api/complaints`);
  if (!res.ok) {
    throw new Error("Failed to fetch complaints");
  }
  return res.json();
}

export async function getDashboardStats(): Promise<DashboardStats> {
  const res = await fetch(`${apiBase()}/api/dashboard/stats`);
  if (!res.ok) {
    throw new Error("Failed to fetch dashboard stats");
  }
  return res.json();
}
