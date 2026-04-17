"use client";

import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api";

const WEEKDAYS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];

function getDaysInMonth(year: number, month: number): number {
  return new Date(year, month + 1, 0).getDate();
}

function getFirstDayOfWeek(year: number, month: number): number {
  return new Date(year, month, 1).getDay();
}

type SiteGrid = Record<string, Record<string, string>>;

interface AvailabilityData {
  facility_id: number;
  sites: SiteGrid;
  site_names: Record<string, string>;
  last_updated: string | null;
}

interface Props {
  facilityId: number;
  availableDates: string[];
}

export function AvailabilityCalendar({ facilityId, availableDates }: Props) {
  const [siteGrid, setSiteGrid] = useState<SiteGrid | null>(null);
  const [siteNames, setSiteNames] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    apiClient<AvailabilityData>(`/api/facilities/${facilityId}/availability`)
      .then((data) => {
        setSiteGrid(data.sites);
        setSiteNames(data.site_names || {});
      })
      .catch(() => setSiteGrid(null))
      .finally(() => setLoading(false));
  }, [facilityId]);

  if (availableDates.length === 0) return null;

  // Count available sites per date
  const sitesPerDate: Record<string, number> = {};
  if (siteGrid) {
    for (const dates of Object.values(siteGrid)) {
      for (const [dateStr, status] of Object.entries(dates)) {
        if (status === "available" || status === "locked") {
          sitesPerDate[dateStr] = (sitesPerDate[dateStr] || 0) + 1;
        }
      }
    }
  }

  const dateSet = new Set(availableDates);
  const months = new Map<string, { year: number; month: number }>();

  for (const ds of availableDates) {
    const d = new Date(ds + "T00:00:00");
    const key = `${d.getFullYear()}-${d.getMonth()}`;
    if (!months.has(key)) {
      months.set(key, { year: d.getFullYear(), month: d.getMonth() });
    }
  }

  // Get sites available on the selected date
  const selectedSites: { id: string; status: string }[] = [];
  if (selectedDate && siteGrid) {
    for (const [siteId, dates] of Object.entries(siteGrid)) {
      const status = dates[selectedDate];
      if (status === "available" || status === "locked") {
        selectedSites.push({ id: siteId, status });
      }
    }
    selectedSites.sort((a, b) => a.id.localeCompare(b.id, undefined, { numeric: true }));
  }

  const maxSites = Math.max(1, ...Object.values(sitesPerDate), 1);

  return (
    <div className="mt-3 space-y-4">
      {loading && <p className="text-xs text-muted-foreground">Loading site details...</p>}

      {[...months.values()].map(({ year, month }) => (
        <MiniMonth
          key={`${year}-${month}`}
          year={year}
          month={month}
          availableDates={dateSet}
          sitesPerDate={sitesPerDate}
          maxSites={maxSites}
          selectedDate={selectedDate}
          onDateClick={setSelectedDate}
          hasSiteData={!!siteGrid}
        />
      ))}

      {/* Site detail panel */}
      {selectedDate && selectedSites.length > 0 && (
        <div className="rounded-lg border border-border bg-card p-3">
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold">
              {new Date(selectedDate + "T00:00:00").toLocaleDateString("en-US", {
                weekday: "long",
                month: "short",
                day: "numeric",
              })}
              {" — "}
              {selectedSites.length} site{selectedSites.length !== 1 ? "s" : ""}
            </p>
            <button
              type="button"
              onClick={() => setSelectedDate(null)}
              className="text-xs text-muted-foreground hover:text-foreground cursor-pointer"
            >
              close
            </button>
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {selectedSites.map((site) => (
              <span
                key={site.id}
                className={`rounded px-2 py-0.5 text-xs font-medium ${
                  site.status === "locked"
                    ? "bg-amber-100 text-amber-800"
                    : "bg-primary/10 text-primary"
                }`}
              >
                {siteNames[site.id] || (/^\d+$/.test(site.id) ? `Site ${site.id}` : site.id)}
                {site.status === "locked" && " (unlocking soon)"}
              </span>
            ))}
          </div>
        </div>
      )}

      {selectedDate && selectedSites.length === 0 && siteGrid && (
        <p className="text-xs text-muted-foreground">No site detail available for this date.</p>
      )}
    </div>
  );
}

function MiniMonth({
  year,
  month,
  availableDates,
  sitesPerDate,
  maxSites,
  selectedDate,
  onDateClick,
  hasSiteData,
}: {
  year: number;
  month: number;
  availableDates: Set<string>;
  sitesPerDate: Record<string, number>;
  maxSites: number;
  selectedDate: string | null;
  onDateClick: (date: string) => void;
  hasSiteData: boolean;
}) {
  const daysInMonth = getDaysInMonth(year, month);
  const firstDay = getFirstDayOfWeek(year, month);
  const monthName = new Date(year, month).toLocaleDateString("en-US", {
    month: "long",
    year: "numeric",
  });

  const cells: (number | null)[] = [];
  for (let i = 0; i < firstDay; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);
  while (cells.length % 7 !== 0) cells.push(null);

  const rows: (number | null)[][] = [];
  for (let i = 0; i < cells.length; i += 7) {
    rows.push(cells.slice(i, i + 7));
  }

  return (
    <div>
      <p className="mb-1 text-xs font-semibold text-muted-foreground">{monthName}</p>
      <table className="border-collapse">
        <thead>
          <tr>
            {WEEKDAYS.map((wd) => (
              <th
                key={wd}
                className="h-6 w-8 text-center text-[10px] font-medium text-muted-foreground"
              >
                {wd}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr key={ri}>
              {row.map((day, ci) => {
                if (day === null) {
                  return <td key={ci} className="h-8 w-8" />;
                }

                const dateStr = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
                const isAvailable = availableDates.has(dateStr);
                const isSelected = dateStr === selectedDate;
                const siteCount = sitesPerDate[dateStr] || 0;

                let bgClass = "text-muted-foreground/30";
                if (isSelected) {
                  bgClass = "bg-blue-500 text-white font-semibold ring-2 ring-blue-300";
                } else if (isAvailable) {
                  if (hasSiteData && maxSites > 1) {
                    const ratio = siteCount / maxSites;
                    if (ratio > 0.5) {
                      bgClass = "bg-primary text-primary-foreground font-semibold";
                    } else {
                      bgClass = "bg-primary/40 text-foreground font-medium";
                    }
                  } else {
                    bgClass = "bg-primary text-primary-foreground font-semibold";
                  }
                }

                return (
                  <td
                    key={ci}
                    onClick={() => isAvailable && onDateClick(dateStr)}
                    className={`h-8 w-8 text-center text-xs rounded-sm transition-colors
                      ${bgClass}
                      ${isAvailable ? "cursor-pointer hover:ring-1 hover:ring-primary" : ""}
                    `}
                    title={isAvailable && hasSiteData ? `${siteCount} site${siteCount !== 1 ? "s" : ""}` : undefined}
                  >
                    {day}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      {hasSiteData && (
        <div className="mt-1 flex items-center gap-2 text-[10px] text-muted-foreground">
          <span className="inline-block h-2.5 w-2.5 rounded-sm bg-primary/40" /> few sites
          <span className="inline-block h-2.5 w-2.5 rounded-sm bg-primary" /> many sites
        </div>
      )}
    </div>
  );
}
