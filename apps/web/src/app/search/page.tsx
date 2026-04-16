"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import type { User } from "@supabase/supabase-js";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { AlertDialogWatch } from "@/components/alert-dialog-watch";
import { LocationSearch } from "@/components/location-search";
import { SearchMap } from "@/components/search-map";
import { createClient } from "@/lib/supabase/client";
import { apiClient } from "@/lib/api";
import type { FacilityResult, SearchResponse, SoldOutFacility } from "@/lib/types";

interface Location {
  lat: number;
  lng: number;
  name: string;
}

export default function SearchPage() {
  const [location, setLocation] = useState<Location | null>(null);
  const [radius, setRadius] = useState(50);
  const [dateStart, setDateStart] = useState("");
  const [dateEnd, setDateEnd] = useState("");
  const [nightsStr, setNightsStr] = useState("1");
  const [results, setResults] = useState<FacilityResult[]>([]);
  const [soldOut, setSoldOut] = useState<SoldOutFacility[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);
  const [hoveredId, setHoveredId] = useState<number | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [alertFacility, setAlertFacility] = useState<FacilityResult | null>(null);
  const [watchedIds, setWatchedIds] = useState<Set<number>>(new Set());
  const [showAuthExpired, setShowAuthExpired] = useState(false);
  const cardRefs = useRef<Map<number, HTMLDivElement>>(new Map());
  const supabase = createClient();

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => setUser(data.user));
    supabase.auth.getSession().then(({ data }) => {
      setToken(data.session?.access_token ?? null);
    });
  }, []);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!location) return;

    const nights = parseInt(nightsStr, 10);
    if (!nights || nights < 1) {
      setError("Minimum consecutive nights must be at least 1");
      return;
    }

    setLoading(true);
    setError(null);
    setResults([]);
    setSoldOut([]);
    setSearched(false);

    try {
      const data = await apiClient<SearchResponse>("/api/search", {
        method: "POST",
        body: JSON.stringify({
          center: { lat: location.lat, lng: location.lng },
          radius_miles: radius,
          date_start: dateStart,
          date_end: dateEnd,
          nights,
        }),
      });
      setResults(data.results);
      setSoldOut(data.sold_out ?? []);
      setSearched(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }

  const handleMarkerClick = useCallback((id: number) => {
    const el = cardRefs.current.get(id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      setHoveredId(id);
      setTimeout(() => setHoveredId(null), 2000);
    }
  }, []);

  return (
    <div className="flex h-[calc(100vh-3.5rem)] flex-col lg:flex-row">
      {/* Left panel: form + results */}
      <div className="w-full overflow-y-auto border-r border-border bg-card p-4 lg:w-2/5">
        <h1 className="font-heading text-2xl font-bold">Search Campgrounds</h1>

        <form onSubmit={handleSearch} className="mt-4 space-y-4">
          <div className="space-y-2">
            <Label>Location</Label>
            <LocationSearch onSelect={setLocation} />
          </div>

          <div className="space-y-2">
            <Label htmlFor="radius">Radius: {radius} miles</Label>
            <input
              id="radius"
              type="range"
              min={10}
              max={200}
              step={5}
              value={radius}
              onChange={(e) => setRadius(Number(e.target.value))}
              className="w-full accent-primary"
            />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>10 mi</span>
              <span>200 mi</span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="date-start">Check in</Label>
              <Input
                id="date-start"
                type="date"
                value={dateStart}
                onChange={(e) => setDateStart(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="date-end">Check out</Label>
              <Input
                id="date-end"
                type="date"
                value={dateEnd}
                onChange={(e) => setDateEnd(e.target.value)}
                required
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="nights">Minimum consecutive nights</Label>
            <Input
              id="nights"
              type="number"
              min={1}
              max={14}
              value={nightsStr}
              onChange={(e) => setNightsStr(e.target.value)}
            />
          </div>

          <Button
            type="submit"
            disabled={loading || !location || !dateStart || !dateEnd}
            className={`w-full transition-colors ${
              location && dateStart && dateEnd && !loading
                ? "bg-primary text-primary-foreground hover:bg-primary/90"
                : "bg-muted text-muted-foreground"
            }`}
          >
            {loading ? "Searching..." : "Search"}
          </Button>
        </form>

        {/* Results list */}
        <div className="mt-6">
          {error && (
            <p className="text-center text-sm text-destructive">{error}</p>
          )}

          {searched && results.length === 0 && !loading && (
            <div className="rounded-lg border border-dashed p-8 text-center">
              <p className="font-medium">No campgrounds found</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Try expanding your radius or adjusting your dates.
              </p>
            </div>
          )}

          {results.length > 0 && (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">
                {results.length} campground{results.length !== 1 ? "s" : ""} with
                availability within {radius}mi of {location?.name}
              </p>
              {results.map((facility) => (
                <div
                  key={facility.id}
                  ref={(el) => {
                    if (el) cardRefs.current.set(facility.id, el);
                  }}
                  onMouseEnter={() => setHoveredId(facility.id)}
                  onMouseLeave={() => setHoveredId(null)}
                >
                  <ResultCard
                    facility={facility}
                    highlighted={hoveredId === facility.id}
                    showAlert={!!user}
                    watching={watchedIds.has(facility.id)}
                    onAlertClick={() => setAlertFacility(facility)}
                  />
                </div>
              ))}
            </div>
          )}

          {soldOut.length > 0 && (
            <div className="mt-6 space-y-3">
              <div className="flex items-center gap-3">
                <div className="h-px flex-1 bg-border" />
                <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Sold out for these dates
                </span>
                <div className="h-px flex-1 bg-border" />
              </div>
              {soldOut.map((facility) => (
                <div
                  key={facility.id}
                  ref={(el) => {
                    if (el) cardRefs.current.set(facility.id, el);
                  }}
                  onMouseEnter={() => setHoveredId(facility.id)}
                  onMouseLeave={() => setHoveredId(null)}
                >
                  <SoldOutCard
                    facility={facility}
                    highlighted={hoveredId === facility.id}
                    showAlert={!!user}
                    watching={watchedIds.has(facility.id)}
                    onAlertClick={() => {
                      // Convert to FacilityResult shape for the dialog
                      setAlertFacility({
                        ...facility,
                        available_dates: [],
                        last_updated: new Date().toISOString(),
                      });
                    }}
                  />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Right panel: map */}
      <div className="h-[400px] w-full lg:h-auto lg:w-3/5">
        <SearchMap
          center={location}
          radius={radius}
          results={results}
          soldOut={soldOut}
          hoveredId={hoveredId}
          onMarkerHover={setHoveredId}
          onMarkerClick={handleMarkerClick}
        />
      </div>

      {/* Alert dialog */}
      {alertFacility && token && (
        <AlertDialogWatch
          facility={alertFacility}
          dateStart={dateStart}
          dateEnd={dateEnd}
          nights={parseInt(nightsStr, 10) || 1}
          token={token}
          open={!!alertFacility}
          onOpenChange={(open) => { if (!open) setAlertFacility(null); }}
          onSuccess={() => {
            setWatchedIds((prev) => new Set([...prev, alertFacility.id]));
          }}
          onAuthExpired={() => {
            setUser(null);
            setToken(null);
            setShowAuthExpired(true);
          }}
        />
      )}

      {/* Session expired dialog */}
      {showAuthExpired && (
        <Dialog open={showAuthExpired} onOpenChange={setShowAuthExpired}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Session expired</DialogTitle>
              <DialogDescription>
                Your login session has expired. Please log in again to create alerts.
              </DialogDescription>
            </DialogHeader>
            <Link href="/login">
              <Button className="w-full">Log in</Button>
            </Link>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}

function ResultCard({
  facility,
  highlighted,
  showAlert,
  watching,
  onAlertClick,
}: {
  facility: FacilityResult;
  highlighted: boolean;
  showAlert: boolean;
  watching: boolean;
  onAlertClick: () => void;
}) {
  const dateCount = facility.available_dates.length;
  const updatedAt = new Date(facility.last_updated);

  return (
    <Card className={`border-border ${highlighted ? "ring-2 ring-blue-500" : ""}`}>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div>
            <CardTitle className="text-base text-foreground">{facility.name}</CardTitle>
            {facility.parent_name && (
              <p className="text-sm text-muted-foreground">{facility.parent_name}</p>
            )}
          </div>
          {showAlert && (
            <Button
              variant={watching ? "secondary" : "outline"}
              size="sm"
              disabled={watching}
              onClick={onAlertClick}
            >
              {watching ? "Watching" : "Alert me"}
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <p className="text-sm text-primary font-medium">
              {dateCount} date{dateCount !== 1 ? "s" : ""} available
            </p>
            <p className="text-xs text-muted-foreground">
              Updated {updatedAt.toLocaleDateString()} {updatedAt.toLocaleTimeString()}
            </p>
          </div>
          <a
            href={facility.booking_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm font-semibold text-primary hover:underline"
          >
            {facility.booking_url.includes("reservecalifornia") ? "Book on ReserveCalifornia" : "Book on Recreation.gov"}
          </a>
        </div>
      </CardContent>
    </Card>
  );
}

function SoldOutCard({
  facility,
  highlighted,
  showAlert,
  watching,
  onAlertClick,
}: {
  facility: SoldOutFacility;
  highlighted: boolean;
  showAlert: boolean;
  watching: boolean;
  onAlertClick: () => void;
}) {
  return (
    <Card className={`border-border opacity-60 ${highlighted ? "ring-2 ring-blue-500 opacity-100" : ""}`}>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div>
            <CardTitle className="text-base">{facility.name}</CardTitle>
            {facility.parent_name && (
              <p className="text-sm text-muted-foreground">{facility.parent_name}</p>
            )}
          </div>
          {showAlert && (
            <Button
              variant={watching ? "secondary" : "outline"}
              size="sm"
              disabled={watching}
              onClick={onAlertClick}
            >
              {watching ? "Watching" : "Alert me"}
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">No availability for these dates</p>
          <a
            href={facility.booking_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm font-medium text-primary hover:underline"
          >
            {facility.booking_url.includes("reservecalifornia") ? "View on ReserveCalifornia" : "View on Recreation.gov"}
          </a>
        </div>
      </CardContent>
    </Card>
  );
}
