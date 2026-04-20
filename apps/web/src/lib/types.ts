export interface SearchRequest {
  center: { lat: number; lng: number };
  radius_miles: number;
  date_start: string;
  date_end: string;
  nights: number;
}

export interface FacilityResult {
  id: number;
  name: string;
  parent_name: string | null;
  provider: string;
  lat: number;
  lng: number;
  available_dates: string[];
  booking_url: string;
  last_updated: string;
}

export interface SoldOutFacility {
  id: number;
  name: string;
  parent_name: string | null;
  provider: string;
  lat: number;
  lng: number;
  booking_url: string;
  last_updated: string | null;
}

export interface SearchResponse {
  results: FacilityResult[];
  sold_out: SoldOutFacility[];
  total: number;
}

export interface WatchResponse {
  id: number;
  name: string | null;
  facility_ids: number[] | null;
  date_start: string;
  date_end: string;
  nights: number;
  is_active: boolean;
  created_at: string;
}

export interface NotificationResponse {
  id: number;
  watch_id: number;
  facility_name: string;
  available_dates: string[];
  channel: string;
  sent_at: string;
  booking_url: string;
}
