"use client";

import { useEffect, useState } from "react";
import { Background } from "@/components/Background";
import Navbar from "@/components/Navbar";
import { PageHeader } from "@/components/PageHeader";
import { getComplaints, getDashboardStats } from "@/lib/api";
import { ComplaintRecord, DashboardStats } from "@/lib/types";

const TOP_ROUTES_LIMIT = 5;

function formatRoute(complaint: ComplaintRecord): string {
  if (complaint.pickup_location && complaint.drop_location) {
    return `${complaint.pickup_location} → ${complaint.drop_location}`;
  }
  return complaint.pickup_location || complaint.drop_location || "—";
}

function formatDate(value: string): string {
  try {
    return new Date(value).toLocaleString("en-IN", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return value;
  }
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [complaints, setComplaints] = useState<ComplaintRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [statsData, complaintsData] = await Promise.all([
          getDashboardStats(),
          getComplaints(),
        ]);
        if (!cancelled) {
          setStats(statsData);
          setComplaints(complaintsData);
        }
      } catch (e: unknown) {
        if (!cancelled) {
          const message =
            e instanceof Error ? e.message : "Failed to load dashboard data.";
          setError(message);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const topRoutes = stats?.top_patterns.slice(0, TOP_ROUTES_LIMIT) ?? [];

  return (
    <div className="relative flex min-h-screen flex-col bg-neutral-50">
      <Background />
      <Navbar />

      <section className="relative mx-auto w-full max-w-6xl flex-1 px-6 py-10">
        <div className="space-y-8">
          <PageHeader title="Dashboard" />

          {loading && (
            <div className="surface-card p-12 text-center">
              <div className="relative mx-auto mb-4 flex h-16 w-16 items-center justify-center">
                <div className="absolute inset-0 animate-spin rounded-full border-4 border-neutral-100 border-t-emerald-500" />
              </div>
              <p className="text-sm italic text-neutral-500">Loading dashboard data...</p>
            </div>
          )}

          {error && (
            <div className="rounded-3xl border border-red-200 bg-red-50 p-6 text-sm text-red-700 shadow-[0_4px_24px_rgba(0,0,0,0.06)]">
              {error}. Ensure the backend is running and CORS allows this origin.
            </div>
          )}

          {!loading && !error && stats && (
            <>
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="surface-card p-6">
                  <p className="text-xs font-semibold uppercase tracking-wide text-neutral-400">
                    Total complaints
                  </p>
                  <p className="mt-2 text-4xl font-bold tabular-nums text-neutral-900">
                    {stats.total_complaints}
                  </p>
                </div>
                <div className="surface-card p-6">
                  <p className="text-xs font-semibold uppercase tracking-wide text-neutral-400">
                    Pattern clusters
                  </p>
                  <p className="mt-2 text-4xl font-bold tabular-nums text-neutral-900">
                    {stats.pattern_clusters}
                  </p>
                </div>
                <div className="surface-card-dark p-6">
                  <p className="text-xs font-semibold uppercase tracking-wide text-neutral-400">
                    Top patterns
                  </p>
                  <p className="mt-2 text-4xl font-bold tabular-nums">{stats.top_patterns.length}</p>
                </div>
              </div>

              <div className="space-y-4">
                <h2 className="font-semibold text-neutral-900">Top route patterns</h2>

                {topRoutes.length === 0 ? (
                  <div className="surface-card p-8 text-sm text-neutral-500">
                    No recurring patterns yet.
                  </div>
                ) : (
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
                    {topRoutes.map((pattern, idx) => (
                      <div key={pattern.cluster_id} className="surface-card p-5">
                        <div className="mb-3">
                          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-neutral-900 text-xs font-bold text-white">
                            {idx + 1}
                          </span>
                        </div>
                        <p className="text-sm font-medium leading-snug text-neutral-900">{pattern.route}</p>
                        <p className="mt-2 text-xs text-neutral-500">
                          <span className="font-semibold tabular-nums">{pattern.count}</span> complaint
                          {pattern.count === 1 ? "" : "s"}
                          {pattern.time_window ? ` · ${pattern.time_window}` : ""}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="space-y-4">
                <h2 className="font-semibold text-neutral-900">All complaints</h2>

                <div className="surface-card overflow-hidden">
                  {complaints.length === 0 ? (
                    <div className="p-8 text-sm text-neutral-500">No complaints registered yet.</div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full min-w-[960px] text-left text-sm">
                        <thead>
                          <tr className="border-b border-neutral-100 bg-neutral-50/80">
                            {[
                              "Platform",
                              "Route",
                              "Trip time",
                              "Quoted",
                              "Paid",
                              "Discrepancy",
                              "Cluster",
                              "Registered",
                            ].map((heading) => (
                              <th
                                key={heading}
                                className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-neutral-400"
                              >
                                {heading}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {complaints.map((complaint) => (
                            <tr
                              key={complaint.complaint_id}
                              className="border-b border-neutral-100 transition-colors last:border-0 hover:bg-neutral-50/60"
                            >
                              <td className="px-4 py-4 font-medium text-neutral-900">
                                {complaint.platform}
                              </td>
                              <td className="max-w-[220px] px-4 py-4 text-neutral-700">
                                {formatRoute(complaint)}
                              </td>
                              <td className="whitespace-nowrap px-4 py-4 text-neutral-600">
                                {complaint.trip_timestamp || "—"}
                              </td>
                              <td className="px-4 py-4 font-medium tabular-nums text-neutral-700">
                                {complaint.quoted_amount != null ? `₹${complaint.quoted_amount}` : "—"}
                              </td>
                              <td className="px-4 py-4 font-medium tabular-nums text-neutral-700">
                                {complaint.paid_amount != null ? `₹${complaint.paid_amount}` : "—"}
                              </td>
                              <td className="px-4 py-4 font-medium tabular-nums">
                                {complaint.discrepancy != null ? (
                                  <span
                                    className={
                                      complaint.discrepancy !== 0 ? "font-semibold text-red-700" : "text-neutral-500"
                                    }
                                  >
                                    ₹{complaint.discrepancy}
                                  </span>
                                ) : (
                                  "—"
                                )}
                              </td>
                              <td className="px-4 py-4 text-xs text-neutral-500">
                                {complaint.cluster_id ? (
                                  <span
                                    className="rounded-full border border-neutral-200 bg-neutral-50 px-2.5 py-1 font-semibold tabular-nums"
                                    title={complaint.cluster_id}
                                  >
                                    {complaint.cluster_size >= 1
                                      ? complaint.cluster_size
                                      : "1"}
                                  </span>
                                ) : (
                                  "—"
                                )}
                              </td>
                              <td className="whitespace-nowrap px-4 py-4 text-xs text-neutral-500">
                                {formatDate(complaint.created_at)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      </section>
    </div>
  );
}
