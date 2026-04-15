"use client";

import { useCallback, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LocationSearch } from "@/components/location-search";
import { SearchMap } from "@/components/search-map";
import { apiClient } from "@/lib/api";
import type { FacilityResult, SearchResponse } from "@/lib/types";

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
  const [nights, setNights] = useState(1);
  const [results, setResults] = useState<FacilityResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);
  const [hoveredId, setHoveredId] = useState<number | null>(null);
  const cardRefs = useRef<Map<number, HTMLDivElement>>(new Map());

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!location) return;

    setLoading(true);
    setError(null);
    setResults([]);
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
      <div className="w-full overflow-y-auto border-r p-4 lg:w-2/5">
        <h1 className="text-2xl font-semibold">Search Campgrounds</h1>

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
              value={nights}
              onChange={(e) => setNights(Number(e.target.value))}
            />
          </div>

          <Button type="submit" disabled={loading || !location} className="w-full">
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
                {results.length} campground{results.length !== 1 ? "s" : ""} within{" "}
                {radius}mi of {location?.name}
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
          hoveredId={hoveredId}
          onMarkerClick={handleMarkerClick}
        />
      </div>
    </div>
  );
}

function ResultCard({
  facility,
  highlighted,
}: {
  facility: FacilityResult;
  highlighted: boolean;
}) {
  const dateCount = facility.available_dates.length;
  const updatedAt = new Date(facility.last_updated);

  return (
    <Card className={highlighted ? "ring-2 ring-primary" : ""}>
      <CardHeader>
        <CardTitle className="text-base">{facility.name}</CardTitle>
        {facility.parent_name && (
          <p className="text-sm text-muted-foreground">{facility.parent_name}</p>
        )}
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <p className="text-sm">
              <span className="font-medium">{dateCount}</span>{" "}
              date{dateCount !== 1 ? "s" : ""} available
            </p>
            <p className="text-xs text-muted-foreground">
              Updated {updatedAt.toLocaleDateString()} {updatedAt.toLocaleTimeString()}
            </p>
          </div>
          <a
            href={facility.booking_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm font-medium text-primary hover:underline"
          >
            Book on Recreation.gov
          </a>
        </div>
      </CardContent>
    </Card>
  );
}
