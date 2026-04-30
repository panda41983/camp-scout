"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import type { User } from "@supabase/supabase-js";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { AlertDialogWatch } from "@/components/alert-dialog-watch";
import { AvailabilityCalendar } from "@/components/availability-calendar";
import { DatePicker } from "@/components/date-picker";
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

export default function SearchPageWrapper() {
  return (
    <Suspense>
      <SearchPage />
    </Suspense>
  );
}

function SearchPage() {
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
  const [showMap, setShowMap] = useState(true);
  const [sortBy, setSortBy] = useState<"dates" | "name" | "distance">("dates");
  const [providerFilter, setProviderFilter] = useState<"all" | "recreation_gov" | "reserve_california">("all");
  const [sharecopied, setShareCopied] = useState(false);
  const cardRefs = useRef<Map<number, HTMLDivElement>>(new Map());
  const supabase = createClient();
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => setUser(data.user));
    supabase.auth.getSession().then(({ data }) => {
      setToken(data.session?.access_token ?? null);
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setUser(session?.user ?? null);
        setToken(session?.access_token ?? null);
      },
    );

    return () => subscription.unsubscribe();
  }, []);

  // Load search params from URL (for shared links)
  useEffect(() => {
    const lat = searchParams.get("lat");
    const lng = searchParams.get("lng");
    const name = searchParams.get("name");
    const r = searchParams.get("radius");
    const ds = searchParams.get("date_start");
    const de = searchParams.get("date_end");
    const n = searchParams.get("nights");

    if (lat && lng && name) {
      setLocation({ lat: parseFloat(lat), lng: parseFloat(lng), name });
    }
    if (r) setRadius(parseInt(r, 10));
    if (ds) setDateStart(ds);
    if (de) setDateEnd(de);
    if (n) setNightsStr(n);
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

      // Update URL for sharing
      const params = new URLSearchParams({
        lat: String(location.lat),
        lng: String(location.lng),
        name: location.name,
        radius: String(radius),
        date_start: dateStart,
        date_end: dateEnd,
        nights: nightsStr,
      });
      router.replace(`/search?${params.toString()}`, { scroll: false });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }

  function handleShare() {
    navigator.clipboard.writeText(window.location.href);
    setShareCopied(true);
    setTimeout(() => setShareCopied(false), 2000);
  }

  // Apply sort and filter to results
  const filteredResults = results.filter(
    (f) => providerFilter === "all" || f.provider === providerFilter
  );
  function distanceFrom(f: { lat: number; lng: number }) {
    if (!location) return 0;
    const R = 3959; // miles
    const dLat = ((f.lat - location.lat) * Math.PI) / 180;
    const dLng = ((f.lng - location.lng) * Math.PI) / 180;
    const a =
      Math.sin(dLat / 2) ** 2 +
      Math.cos((location.lat * Math.PI) / 180) *
        Math.cos((f.lat * Math.PI) / 180) *
        Math.sin(dLng / 2) ** 2;
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  }

  // Cap selectable dates to the bulk-seed coverage window (6 months ahead)
  const maxBookingDate = (() => {
    const d = new Date();
    d.setMonth(d.getMonth() + 6);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  })();

  const sortedResults = [...filteredResults].sort((a, b) => {
    if (sortBy === "name") return a.name.localeCompare(b.name);
    if (sortBy === "distance") return distanceFrom(a) - distanceFrom(b);
    return b.available_dates.length - a.available_dates.length;
  });

  const filteredSoldOut = [...soldOut.filter(
    (f) => providerFilter === "all" || f.provider === providerFilter
  )].sort((a, b) => {
    if (sortBy === "name") return a.name.localeCompare(b.name);
    if (sortBy === "distance") return distanceFrom(a) - distanceFrom(b);
    return a.name.localeCompare(b.name);
  });

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
            <LocationSearch onSelect={setLocation} initialValue={location?.name} />
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
              <Label>Check in</Label>
              <DatePicker
                value={dateStart}
                onChange={setDateStart}
                placeholder="Select check in"
                maxDate={maxBookingDate}
              />
            </div>
            <div className="space-y-2">
              <Label>Check out</Label>
              <DatePicker
                value={dateEnd}
                onChange={setDateEnd}
                placeholder="Select check out"
                maxDate={maxBookingDate}
              />
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            We track availability up to 6 months out (the booking horizon for
            most providers).
          </p>

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
            className={`w-full cursor-pointer transition-colors ${
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

          {/* Controls bar — sort, filter, share */}
          {searched && !loading && (
            <div className="mb-4 flex flex-wrap items-center gap-2">
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as "dates" | "name" | "distance")}
                className="rounded-lg border border-border bg-card px-3 py-1.5 font-body text-xs cursor-pointer"
              >
                <option value="dates">Sort: Most dates</option>
                <option value="distance">Sort: Nearest</option>
                <option value="name">Sort: Name A-Z</option>
              </select>

              <select
                value={providerFilter}
                onChange={(e) => setProviderFilter(e.target.value as "all" | "recreation_gov" | "reserve_california")}
                className="rounded-lg border border-border bg-card px-3 py-1.5 font-body text-xs cursor-pointer"
              >
                <option value="all">All providers</option>
                <option value="recreation_gov">Recreation.gov</option>
                <option value="reserve_california">ReserveCalifornia</option>
              </select>

              <button
                type="button"
                onClick={handleShare}
                className="ml-auto rounded-lg border border-border bg-card px-3 py-1.5 font-body text-xs text-muted-foreground hover:text-foreground hover:bg-accent cursor-pointer"
              >
                {sharecopied ? "Link copied!" : "Share search"}
              </button>
            </div>
          )}

          {searched && sortedResults.length === 0 && filteredSoldOut.length === 0 && !loading && (
            <div className="rounded-lg border border-dashed p-8 text-center">
              <p className="font-medium">No campgrounds found</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Try expanding your radius or adjusting your dates.
              </p>
            </div>
          )}

          {sortedResults.length > 0 && (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">
                {sortedResults.length} campground{sortedResults.length !== 1 ? "s" : ""} with
                availability within {radius}mi of {location?.name}
              </p>
              {sortedResults.map((facility) => (
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

          {filteredSoldOut.length > 0 && (
            <div className="mt-6 space-y-3">
              <div className="flex items-center gap-3">
                <div className="h-px flex-1 bg-border" />
                <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Sold out for these dates
                </span>
                <div className="h-px flex-1 bg-border" />
              </div>
              {filteredSoldOut.map((facility) => (
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
                    loggedIn={!!user}
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

      {/* Map toggle for mobile */}
      <div className="lg:hidden">
        <button
          type="button"
          onClick={() => setShowMap(!showMap)}
          className="w-full border-t border-border bg-card px-4 py-2 text-center text-xs font-medium text-muted-foreground hover:text-foreground cursor-pointer"
        >
          {showMap ? "Hide map ▲" : "Show map ▼"}
        </button>
      </div>

      {/* Right panel: map */}
      <div className={`w-full lg:h-auto lg:w-3/5 lg:block ${showMap ? "h-[400px]" : "hidden lg:block"}`}>
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
  const [expanded, setExpanded] = useState(false);
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
            <button
              type="button"
              onClick={() => setExpanded(!expanded)}
              className="text-sm text-primary font-medium hover:underline cursor-pointer"
            >
              {dateCount} date{dateCount !== 1 ? "s" : ""} available {expanded ? "▲" : "▼"}
            </button>
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
            {facility.provider === "reserve_california" ? "Book on ReserveCalifornia" : "Book on Recreation.gov"}
          </a>
        </div>
        {expanded && (
          <AvailabilityCalendar facilityId={facility.id} availableDates={facility.available_dates} />
        )}
      </CardContent>
    </Card>
  );
}

function SoldOutCard({
  facility,
  highlighted,
  loggedIn,
  watching,
  onAlertClick,
}: {
  facility: SoldOutFacility;
  highlighted: boolean;
  loggedIn: boolean;
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
          {loggedIn ? (
            <Button
              variant={watching ? "secondary" : "outline"}
              size="sm"
              disabled={watching}
              onClick={onAlertClick}
            >
              {watching ? "Watching" : "Alert me"}
            </Button>
          ) : (
            <Link href="/login" className="text-xs text-muted-foreground hover:text-primary">
              Log in to set alert
            </Link>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <p className="text-sm text-muted-foreground">No availability for these dates</p>
            {facility.last_updated && (
              <p className="text-xs text-muted-foreground/70">
                Checked {new Date(facility.last_updated).toLocaleDateString()} {new Date(facility.last_updated).toLocaleTimeString()}
              </p>
            )}
            {!facility.last_updated && (
              <p className="text-xs text-muted-foreground/70">Not yet scanned</p>
            )}
          </div>
          <a
            href={facility.booking_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm font-medium text-primary hover:underline"
          >
            {facility.provider === "reserve_california" ? "View on ReserveCalifornia" : "View on Recreation.gov"}
          </a>
        </div>
      </CardContent>
    </Card>
  );
}
