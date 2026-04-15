"use client";

import { useEffect, useRef } from "react";
import maplibregl, { LngLatBounds } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { FacilityResult } from "@/lib/types";

const MAPTILER_KEY = process.env.NEXT_PUBLIC_MAPTILER_API_KEY;
const STYLE_URL = `https://api.maptiler.com/maps/streets-v2/style.json?key=${MAPTILER_KEY}`;

// Generate a GeoJSON polygon approximating a circle
function createCirclePolygon(
  center: [number, number], // [lng, lat]
  radiusMiles: number,
  points = 64,
): GeoJSON.Feature<GeoJSON.Polygon> {
  const radiusKm = radiusMiles * 1.60934;
  const coords: [number, number][] = [];
  for (let i = 0; i <= points; i++) {
    const angle = (i / points) * 2 * Math.PI;
    const dx = radiusKm * Math.cos(angle);
    const dy = radiusKm * Math.sin(angle);
    const lat = center[1] + (dy / 111.32);
    const lng = center[0] + (dx / (111.32 * Math.cos((center[1] * Math.PI) / 180)));
    coords.push([lng, lat]);
  }
  return {
    type: "Feature",
    properties: {},
    geometry: { type: "Polygon", coordinates: [coords] },
  };
}

interface Props {
  center: { lat: number; lng: number } | null;
  radius: number;
  results: FacilityResult[];
  hoveredId: number | null;
  onMarkerClick: (id: number) => void;
}

export function SearchMap({ center, radius, results, hoveredId, onMarkerClick }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<Map<number, maplibregl.Marker>>(new Map());

  // Initialize map
  useEffect(() => {
    if (!containerRef.current || !MAPTILER_KEY) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: STYLE_URL,
      center: center ? [center.lng, center.lat] : [-119.5, 37.8],
      zoom: 7,
    });

    map.addControl(new maplibregl.NavigationControl(), "top-right");
    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Update radius circle
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !center) return;

    function addCircle() {
      const circleGeoJSON = createCirclePolygon([center!.lng, center!.lat], radius);

      if (map!.getSource("radius-circle")) {
        (map!.getSource("radius-circle") as maplibregl.GeoJSONSource).setData(circleGeoJSON);
      } else {
        map!.addSource("radius-circle", { type: "geojson", data: circleGeoJSON });
        map!.addLayer({
          id: "radius-circle-fill",
          type: "fill",
          source: "radius-circle",
          paint: {
            "fill-color": "#3b82f6",
            "fill-opacity": 0.08,
          },
        });
        map!.addLayer({
          id: "radius-circle-line",
          type: "line",
          source: "radius-circle",
          paint: {
            "line-color": "#3b82f6",
            "line-width": 1.5,
            "line-dasharray": [3, 2],
          },
        });
      }
    }

    if (map.isStyleLoaded()) {
      addCircle();
    } else {
      map.on("load", addCircle);
    }
  }, [center, radius]);

  // Update markers
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    // Clear old markers
    for (const marker of markersRef.current.values()) {
      marker.remove();
    }
    markersRef.current.clear();

    if (results.length === 0) return;

    const bounds = new LngLatBounds();

    for (const facility of results) {
      const el = document.createElement("div");
      el.className = "search-marker";
      el.dataset.facilityId = String(facility.id);
      el.innerHTML = `<svg width="28" height="36" viewBox="0 0 28 36" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M14 0C6.268 0 0 6.268 0 14c0 10.5 14 22 14 22s14-11.5 14-22C28 6.268 21.732 0 14 0z" fill="#ef4444" class="marker-pin"/>
        <circle cx="14" cy="14" r="6" fill="white"/>
      </svg>`;
      el.style.cssText = "cursor: pointer; transition: filter 0.15s;";

      el.addEventListener("click", () => onMarkerClick(facility.id));

      const marker = new maplibregl.Marker({ element: el, anchor: "bottom" })
        .setLngLat([facility.lng, facility.lat])
        .addTo(map);

      markersRef.current.set(facility.id, marker);
      bounds.extend([facility.lng, facility.lat]);
    }

    // Include center in bounds if present
    if (center) {
      bounds.extend([center.lng, center.lat]);
    }

    map.fitBounds(bounds, { padding: 50, maxZoom: 12 });
  }, [results, center, onMarkerClick]);

  // Highlight hovered marker — change SVG fill, not transform (MapLibre owns transform)
  useEffect(() => {
    for (const [id, marker] of markersRef.current) {
      const el = marker.getElement();
      const pin = el.querySelector(".marker-pin") as SVGElement | null;
      if (id === hoveredId) {
        if (pin) pin.setAttribute("fill", "#2563eb");
        el.style.filter = "drop-shadow(0 2px 4px rgba(0,0,0,0.4))";
        el.style.zIndex = "10";
      } else {
        if (pin) pin.setAttribute("fill", "#ef4444");
        el.style.filter = "none";
        el.style.zIndex = "1";
      }
    }
  }, [hoveredId]);

  return (
    <div ref={containerRef} className="h-full w-full min-h-[400px] rounded-lg" />
  );
}
