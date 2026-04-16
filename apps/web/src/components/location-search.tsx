"use client";

import { useEffect, useRef, useState } from "react";
import { Input } from "@/components/ui/input";
import { useDebounce } from "@/hooks/use-debounce";

const MAPTILER_KEY = process.env.NEXT_PUBLIC_MAPTILER_API_KEY;

interface Location {
  lat: number;
  lng: number;
  name: string;
}

interface Props {
  onSelect: (location: Location) => void;
}

interface Feature {
  center: [number, number]; // [lng, lat]
  place_name: string;
}

export function LocationSearch({ onSelect }: Props) {
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<Feature[]>([]);
  const [open, setOpen] = useState(false);
  const debouncedQuery = useDebounce(query, 300);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!debouncedQuery || debouncedQuery.length < 2 || !MAPTILER_KEY) {
      setSuggestions([]);
      return;
    }

    let cancelled = false;

    async function fetchSuggestions() {
      try {
        const res = await fetch(
          `https://api.maptiler.com/geocoding/${encodeURIComponent(debouncedQuery)}.json?key=${MAPTILER_KEY}&country=us&limit=5`,
        );
        if (!res.ok || cancelled) return;
        const data = await res.json();
        if (!cancelled) {
          setSuggestions(data.features ?? []);
          setOpen(true);
        }
      } catch {
        // Silently fail — user can keep typing
      }
    }

    fetchSuggestions();
    return () => { cancelled = true; };
  }, [debouncedQuery]);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  function handleSelect(feature: Feature) {
    const [lng, lat] = feature.center;
    const name = feature.place_name;
    setQuery(name);
    setSuggestions([]);
    setOpen(false);
    onSelect({ lat, lng, name });
  }

  return (
    <div ref={containerRef} className="relative">
      <Input
        placeholder="Search for a location..."
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          if (!e.target.value) setOpen(false);
        }}
        onFocus={() => {
          if (suggestions.length > 0) setOpen(true);
        }}
      />
      {open && suggestions.length > 0 && (
        <ul className="absolute z-10 mt-1 w-full rounded-md border border-border bg-card shadow-lg">
          {suggestions.map((feature, i) => (
            <li key={i}>
              <button
                type="button"
                className="w-full px-3 py-2 text-left text-sm hover:bg-muted"
                onMouseDown={() => handleSelect(feature)}
              >
                {feature.place_name}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
