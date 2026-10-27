import type { PlaceResult } from "../api/types";

// Quick picks shown before you type. Any other city comes from GET /api/v1/places/search
// (Open-Meteo geocoding + the nearest airport from LiteAPI). Each row is reference data the
// agents need as input: coordinates, IANA time zone and the main airport code.

export interface Place {
  city: string;
  region?: string | null;
  country: string;
  countryCode: string;
  /** Nearest airport; null when none was found within reach (flights are then skipped). */
  iata: string | null;
  airport: string | null;
  airportKm?: number | null;
  lat: number;
  lon: number;
  tz: string;
  /** "region" for states, islands and areas (Goa, Ladakh): searched over a wider radius. */
  kind?: "city" | "region";
  /** For regions: the town travellers usually stay in, used as the map centre. */
  base?: string | null;
}

export const PLACES: Place[] = [
  { city: "Rome", country: "Italy", countryCode: "IT", iata: "FCO", airport: "Fiumicino", lat: 41.8967, lon: 12.4822, tz: "Europe/Rome" },
  { city: "Paris", country: "France", countryCode: "FR", iata: "CDG", airport: "Charles de Gaulle", lat: 48.8566, lon: 2.3522, tz: "Europe/Paris" },
  { city: "London", country: "United Kingdom", countryCode: "GB", iata: "LHR", airport: "Heathrow", lat: 51.5074, lon: -0.1278, tz: "Europe/London" },
  { city: "Barcelona", country: "Spain", countryCode: "ES", iata: "BCN", airport: "El Prat", lat: 41.3874, lon: 2.1686, tz: "Europe/Madrid" },
  { city: "Amsterdam", country: "Netherlands", countryCode: "NL", iata: "AMS", airport: "Schiphol", lat: 52.3676, lon: 4.9041, tz: "Europe/Amsterdam" },
  { city: "Lisbon", country: "Portugal", countryCode: "PT", iata: "LIS", airport: "Humberto Delgado", lat: 38.7223, lon: -9.1393, tz: "Europe/Lisbon" },
  { city: "Istanbul", country: "Türkiye", countryCode: "TR", iata: "IST", airport: "Istanbul Airport", lat: 41.0082, lon: 28.9784, tz: "Europe/Istanbul" },
  { city: "Dubai", country: "United Arab Emirates", countryCode: "AE", iata: "DXB", airport: "Dubai International", lat: 25.2048, lon: 55.2708, tz: "Asia/Dubai" },
  { city: "Singapore", country: "Singapore", countryCode: "SG", iata: "SIN", airport: "Changi", lat: 1.3521, lon: 103.8198, tz: "Asia/Singapore" },
  { city: "Bangkok", country: "Thailand", countryCode: "TH", iata: "BKK", airport: "Suvarnabhumi", lat: 13.7563, lon: 100.5018, tz: "Asia/Bangkok" },
  { city: "Tokyo", country: "Japan", countryCode: "JP", iata: "HND", airport: "Haneda", lat: 35.6762, lon: 139.6503, tz: "Asia/Tokyo" },
  { city: "Seoul", country: "South Korea", countryCode: "KR", iata: "ICN", airport: "Incheon", lat: 37.5665, lon: 126.978, tz: "Asia/Seoul" },
  { city: "Sydney", country: "Australia", countryCode: "AU", iata: "SYD", airport: "Kingsford Smith", lat: -33.8688, lon: 151.2093, tz: "Australia/Sydney" },
  { city: "New York", country: "United States", countryCode: "US", iata: "JFK", airport: "John F. Kennedy", lat: 40.7128, lon: -74.006, tz: "America/New_York" },
  { city: "Cape Town", country: "South Africa", countryCode: "ZA", iata: "CPT", airport: "Cape Town International", lat: -33.9249, lon: 18.4241, tz: "Africa/Johannesburg" },
  { city: "Bengaluru", country: "India", countryCode: "IN", iata: "BLR", airport: "Kempegowda", lat: 12.9716, lon: 77.5946, tz: "Asia/Kolkata" },
  { city: "New Delhi", country: "India", countryCode: "IN", iata: "DEL", airport: "Indira Gandhi", lat: 28.6139, lon: 77.209, tz: "Asia/Kolkata" },
  { city: "Mumbai", country: "India", countryCode: "IN", iata: "BOM", airport: "Chhatrapati Shivaji Maharaj", lat: 19.076, lon: 72.8777, tz: "Asia/Kolkata" },
  { city: "Jaipur", country: "India", countryCode: "IN", iata: "JAI", airport: "Jaipur International", lat: 26.9124, lon: 75.7873, tz: "Asia/Kolkata" },
  { city: "Kochi", country: "India", countryCode: "IN", iata: "COK", airport: "Cochin International", lat: 9.9312, lon: 76.2673, tz: "Asia/Kolkata" },
  { city: "Goa", region: null, country: "India", countryCode: "IN", iata: "GOI", airport: "Goa International (Dabolim)", lat: 15.4989, lon: 73.8278, tz: "Asia/Kolkata", kind: "region", base: "Panaji" },
  { city: "Hyderabad", region: "Telangana", country: "India", countryCode: "IN", iata: "HYD", airport: "Rajiv Gandhi International", lat: 17.385, lon: 78.4867, tz: "Asia/Kolkata" },
  { city: "Udaipur", region: "Rajasthan", country: "India", countryCode: "IN", iata: "UDR", airport: "Maharana Pratap", lat: 24.5854, lon: 73.7125, tz: "Asia/Kolkata" },
  { city: "Varanasi", region: "Uttar Pradesh", country: "India", countryCode: "IN", iata: "VNS", airport: "Lal Bahadur Shastri International", lat: 25.3176, lon: 82.9739, tz: "Asia/Kolkata" },
  { city: "Rishikesh", region: "Uttarakhand", country: "India", countryCode: "IN", iata: "DED", airport: "Dehradun Jolly Grant", lat: 30.0869, lon: 78.2676, tz: "Asia/Kolkata" },
  { city: "Leh", region: "Ladakh", country: "India", countryCode: "IN", iata: "IXL", airport: "Kushok Bakula Rimpochee", lat: 34.1526, lon: 77.5771, tz: "Asia/Kolkata" },
  { city: "Kolkata", region: "West Bengal", country: "India", countryCode: "IN", iata: "CCU", airport: "Netaji Subhas Chandra Bose International", lat: 22.5726, lon: 88.3639, tz: "Asia/Kolkata" },
  { city: "Chennai", region: "Tamil Nadu", country: "India", countryCode: "IN", iata: "MAA", airport: "Chennai International", lat: 13.0827, lon: 80.2707, tz: "Asia/Kolkata" },
];

export const byCity = (city: string) => PLACES.find((p) => p.city === city);

export const byIata = (code: string) => PLACES.find((p) => p.iata === code);

export function fromResult(r: PlaceResult): Place {
  return {
    city: r.city,
    region: r.region ?? null,
    country: r.country ?? r.country_code,
    countryCode: r.country_code,
    iata: r.airport?.code ?? null,
    airport: r.airport?.name ?? null,
    airportKm: r.airport?.distance_km ?? null,
    lat: r.latitude,
    lon: r.longitude,
    tz: r.timezone ?? "",
    kind: r.kind ?? "city",
    base: r.base ?? null,
  };
}

export const placeKey = (p: Place) => `${p.city}|${p.lat.toFixed(3)}|${p.lon.toFixed(3)}`;

/** Longest word in a name; used to size the destination headline so words never break. */
export const longestWord = (s: string) => Math.max(...s.split(/\s+/).map((w) => w.length), 1);

/** Keys of INTEREST_KEYWORDS in backend/app/agents/itinerary/calculations/filtering.py */
export const INTERESTS = [
  "history", "art", "museums", "food", "culture", "architecture", "sightseeing", "nature",
  "outdoors", "adventure", "beach", "relaxation", "shopping", "family", "music", "nightlife",
] as const;

export const CURRENCIES = ["USD", "EUR", "INR", "GBP"] as const;
