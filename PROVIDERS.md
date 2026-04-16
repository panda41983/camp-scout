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

# ReserveCalifornia (Tyler Technologies API — post-Oct 2025)
 
## IMPORTANT: API changed in October 2025
 
ReserveCalifornia migrated from UseDirect (`calirdr.usedirect.com`) to Tyler Technologies
in October 2025. The old domain is DEAD. All camply/find-campsite documentation
referencing `calirdr.usedirect.com` or `/rdr/rdr/` paths is outdated.
 
## Base URL
 
```
https://california-rdr.prod.cali.rd12.recreation-management.tylerapp.com
```
 
## Required headers (every request)
 
```
Content-Type: application/json
Accept: application/json
tenantid: cali
```
 
No API key or auth token required. The `tenantid` header identifies California's
instance of Tyler's multi-tenant platform.
 
## Availability grid endpoint (THE KEY ENDPOINT)
 
```
POST /rdr/search/grid
```
 
### Request body
 
```json
{
  "FacilityId": "406",
  "UnitSort": "availability",
  "StartDate": "2026-06-19",
  "EndDate": "2026-06-25",
  "InSeasonOnly": true,
  "WebOnly": true,
  "IsADA": false,
  "RestrictADA": false,
  "UnitCategoryId": 1,
  "SleepingUnitId": 0,
  "MinVehicleLength": 0,
  "UnitTypesGroupIds": [],
  "AmenityIds": [],
  "CustomerId": 0,
  "customerClassificationId": 0
}
```
 
Notes:
- FacilityId is a STRING (not int)
- Dates are ISO YYYY-MM-DD
- UnitCategoryId 1 = camping
- The browser sends 7-day ranges; unclear if larger ranges work — test and document
- MinDate/MaxDate are optional (browser sends them but they may be ignorable)
### Response shape (verified April 2026)
 
```json
{
  "Message": "Built in 2.7 ms ...",
  "Filters": { ... },
  "StartDate": "2026-06-19",
  "EndDate": "2026-06-25",
  "NightsRequested": 7,
  "NightsActual": 7,
  "TodayDate": "2026-04-15",
  "TimeZone": "America/Los_Angeles",
  "MinDate": "2026-04-16",
  "MaxDate": "2026-10-15",
  "Facility": {
    "FacilityId": 406,
    "Name": "East Bay (sites 1-3)",
    "Description": "...",
    "FacilityType": 1,
    "UnitCount": 3,
    "AvailableUnitCount": 1,
    "SliceCount": 21,
    "AvailableSliceCount": 1,
    "Restrictions": {
      "FutureBookingStarts": "2026-04-17T00:00:00-07:00",
      "FutureBookingEnds": "2026-10-15T00:00:00-07:00",
      "MinimumStay": 1,
      "MaximumStay": 1
    },
    "Units": {
      "bucket2.39601": {
        "UnitId": 39601,
        "Name": "Hike in Campsite #2",
        "ShortName": "2",
        "IsAda": false,
        "AllowWebBooking": true,
        "IsWebViewable": true,
        "Slices": {
          "2026-06-19T00:00:00": {
            "Date": "2026-06-19",
            "IsFree": false,
            "IsBlocked": false,
            "IsWalkin": false,
            "ReservationId": 7768031,
            "Lock": null,
            "MinStay": 1,
            "IsReservationDraw": false
          },
          "2026-06-20T00:00:00": {
            "Date": "2026-06-19",
            "IsFree": true,
            "IsBlocked": false,
            "IsWalkin": false,
            "ReservationId": 0,
            "Lock": null,
            "MinStay": 1,
            "IsReservationDraw": false
          }
        }
      }
    }
  }
}
```
 
### How to read the response
 
- `Facility.Units` is a dict keyed by `"bucket{N}.{UnitId}"` (e.g. `"bucket2.39601"`)
- Each unit has `Slices` keyed by datetime string `"YYYY-MM-DDT00:00:00"`
- Each slice has:
  - `IsFree: bool` — TRUE = site is available for booking
  - `IsBlocked: bool` — TRUE = site is blocked by management
  - `IsWalkin: bool` — TRUE = walk-in only, not reservable online
  - `ReservationId: int` — 0 if free, nonzero if reserved
  - `Lock: null | string` — If not null, site is LOCKED (cancelled reservation
    waiting to be re-released). Value is the datetime when it becomes bookable
    (typically 8:00 AM PT next day). THIS IS THE KEY DIFFERENTIATOR FOR ALERTS.
  - `MinStay: int` — minimum nights required
  - `IsReservationDraw: bool` — lottery/draw reservation
### Mapping to our standard grid format
 
For CampScout's `availability_snapshots.grid` and `current_availability`:
 
| Slice state | Our status |
|---|---|
| IsFree=true, Lock=null | "available" |
| IsFree=false, Lock=null, ReservationId>0 | "reserved" |
| IsFree=false, Lock!=null | "locked" (store Lock datetime) |
| IsBlocked=true | "not_reservable" |
| IsWalkin=true | "walk_in" (treat as not reservable online) |
 
## Metadata endpoints
 
### Park/place search with availability
 
```
POST /rdr/search/place
```
 
Body:
```json
{
  "PlaceId": 614,
  "Latitude": 37.860909,
  "Longitude": -122.432568,
  "Nights": 3,
  "CustomerId": 0,
  "StartDate": "2026-06-19",
  "UnitCategoryId": 1,
  "SleepingUnitId": 0,
  "MinVehicleLength": 0,
  "UnitTypesGroupIds": [],
  "AmenityIds": [],
  "Sort": "distance",
  "IsADA": false,
  "RestrictADA": false,
  "NearbyLimit": 100,
  "isSearchAllParks": false,
  "customerClassificationId": 0,
  "InSeasonOnly": true,
  "WebOnly": true,
  "NearbyCountLimit": 10,
  "NearbyOnlyAvailable": false,
  "CountNearby": true,
  "CountUnits": true,
  "HighlightedPlaceId": 0
}
```
 
Returns park info with facility list and unit counts. Includes nearby parks.
 
### Search parks by name
 
```
GET /rdr/fd/citypark/namecontains/{query}
```
 
Typeahead search. Returns matching parks with PlaceId, Name, etc.
 
### Facility detail
 
```
GET /rdr/fd/facilities/{FacilityId}
```
 
Full metadata for a single campground.
 
### Park detail
 
```
GET /rdr/fd/placeinfo/additional-place-info/{PlaceId}
```
 
### Filters for a park
 
```
GET /rdr/search/filters/{PlaceId}
```
 
### Popular/nearby parks
 
```
GET /rdr/search/popular/places/nearlat/{lat}/long/{lng}/on/{date}/limit/{count}
```
 
### Booking restrictions
 
```
GET /rdr/fd/restrictions/startend/facility/{FacilityId}/category/{CategoryId}/unittype/{UnitTypeId}
```
 
Returns valid booking date window for a facility.
 
## Seeding strategy
 
For building our facilities table:
1. There's no single "list all facilities" endpoint visible in the browser traffic.
2. Options for seeding:
   a. Use `/rdr/search/place` with a grid of lat/lng points across California
      and `isSearchAllParks: true` to discover parks, then get facilities from
      each park's detail.
   b. Use `/rdr/fd/citypark/namecontains/` with single-letter queries (a, b, c...)
      to enumerate all parks, then fetch facilities per park.
   c. Check if the old `/rdr/search/facilities` or `/rdr/search/places` GET
      endpoints still work on the new domain (they might — try it).
3. Each park from the place search includes Latitude/Longitude, which we need
   for PostGIS.
## Booking URL construction
 
Park page: `https://www.reservecalifornia.com/park/{PlaceId}`
Facility page: `https://www.reservecalifornia.com/park/{PlaceId}/{FacilityId}`
 
## Rate limiting
 
No documented rate limit. Be conservative:
- Max 1 concurrent request
- Min 2 second delay between requests
- Exponential backoff on any error
## Key differences from old API
 
| Aspect | Old (UseDirect) | New (Tyler) |
|---|---|---|
| Domain | calirdr.usedirect.com | california-rdr.prod.cali.rd12.recreation-management.tylerapp.com |
| Path prefix | /rdr/rdr/ | /rdr/ |
| Tenant header | none | tenantid: cali |
| Date format | MM-DD-YYYY | YYYY-MM-DD (ISO) |
| FacilityId type | integer | string in request, integer in response |
| Units key format | UnitId only | "bucket{N}.{UnitId}" |
| Slice key format | "06/13/2026 12:00:00 AM" | "2026-06-13T00:00:00" |
| Lock field | present | present (confirmed April 2026) |