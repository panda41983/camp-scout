# Upstream Provider Notes

## Recreation.gov / RIDB

- Base: https://ridb.recreation.gov/api/v1
- Auth: `apikey` header (not Bearer)
- Rate limit: 50 req/min
- Camping activity ID: 9
- Useful endpoints:
  - GET /facilities?state=CA&activity=9&limit=50&offset=N (paginate)
  - GET /facilities/{id} — full details inc. lat/lng, amenities
  - GET /facilities/{id}/campsites — sites within facility

## Recreation.gov availability (NOT in RIDB — internal endpoint)

- URL: https://www.recreation.gov/api/camps/availability/campground/{facility_id}/month
- Params: ?start_date=YYYY-MM-DDT00:00:00.000Z (must be 1st of month)
- No auth required, but use a real User-Agent
- Returns: {campsites: {site_id: {availabilities: {date: status}}}}
- Status values: "Available", "Reserved", "Not Available", "Not Reservable Management", ...

## ReserveCalifornia (UseDirect)

- Grid endpoint: POST https://calirdr.usedirect.com/rdr/rdr/search/grid
- Body: JSON with FacilityId, StartDate, EndDate, etc.
- (TBD — fill in once you've sniffed an actual request)