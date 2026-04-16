"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { createClient } from "@/lib/supabase/client";
import { apiClient } from "@/lib/api";
import type { NotificationResponse, WatchResponse } from "@/lib/types";

export default function DashboardPage() {
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [watches, setWatches] = useState<WatchResponse[]>([]);
  const [notifications, setNotifications] = useState<NotificationResponse[]>([]);
  const router = useRouter();
  const supabase = createClient();

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      if (!data.session) {
        router.push("/login");
        return;
      }
      setToken(data.session.access_token);
    });
  }, []);

  useEffect(() => {
    if (!token) return;
    loadData();
  }, [token]);

  async function loadData() {
    setLoading(true);
    try {
      const [w, n] = await Promise.all([
        apiClient<WatchResponse[]>("/api/watches", { token: token! }),
        apiClient<NotificationResponse[]>("/api/notifications?limit=20", { token: token! }),
      ]);
      setWatches(w);
      setNotifications(n);
    } catch {
      // If auth fails, redirect to login
      router.push("/login");
    } finally {
      setLoading(false);
    }
  }

  async function toggleWatch(id: number, isActive: boolean) {
    await apiClient(`/api/watches/${id}`, {
      method: "PATCH",
      token: token!,
      body: JSON.stringify({ is_active: !isActive }),
    });
    setWatches((prev) =>
      prev.map((w) => (w.id === id ? { ...w, is_active: !isActive } : w)),
    );
  }

  async function deleteWatch(id: number) {
    await apiClient(`/api/watches/${id}`, {
      method: "DELETE",
      token: token!,
    });
    setWatches((prev) => prev.filter((w) => w.id !== id));
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8">
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <h1 className="font-heading text-2xl font-bold">Dashboard</h1>

      {/* My Watches */}
      <section className="mt-8">
        <h2 className="text-lg font-medium">My watches</h2>

        {watches.length === 0 ? (
          <div className="mt-4 rounded-lg border border-dashed p-8 text-center">
            <p className="font-medium">No watches yet</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Search for campgrounds to set up availability alerts.
            </p>
            <Link href="/search">
              <Button variant="outline" className="mt-4">
                Search campgrounds
              </Button>
            </Link>
          </div>
        ) : (
          <div className="mt-4 space-y-3">
            {watches.map((watch) => (
              <Card key={watch.id}>
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle className="text-base">
                        {watch.name || "Unnamed watch"}
                      </CardTitle>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {watch.date_start} to {watch.date_end} &middot; {watch.nights} night
                        {watch.nights !== 1 ? "s" : ""}
                      </p>
                    </div>
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        watch.is_active
                          ? "bg-green-100 text-green-700"
                          : "bg-gray-100 text-gray-500"
                      }`}
                    >
                      {watch.is_active ? "Active" : "Paused"}
                    </span>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => toggleWatch(watch.id, watch.is_active)}
                    >
                      {watch.is_active ? "Pause" : "Resume"}
                    </Button>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => deleteWatch(watch.id)}
                    >
                      Delete
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </section>

      {/* Recent Alerts */}
      <section className="mt-10">
        <h2 className="text-lg font-medium">Recent alerts</h2>

        {notifications.length === 0 ? (
          <div className="mt-4 rounded-lg border border-dashed p-8 text-center">
            <p className="font-medium">No alerts sent yet</p>
            <p className="mt-1 text-sm text-muted-foreground">
              When availability opens up for your watches, alerts will appear here.
            </p>
          </div>
        ) : (
          <div className="mt-4 space-y-3">
            {notifications.map((notif) => (
              <Card key={notif.id}>
                <CardContent className="py-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium">{notif.facility_name}</p>
                      <p className="text-sm text-muted-foreground">
                        {notif.available_dates.length} date
                        {notif.available_dates.length !== 1 ? "s" : ""} available &middot;{" "}
                        {new Date(notif.sent_at).toLocaleDateString()}{" "}
                        {new Date(notif.sent_at).toLocaleTimeString()}
                      </p>
                    </div>
                    <a
                      href={notif.booking_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm font-medium text-primary hover:underline"
                    >
                      Book now
                    </a>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
