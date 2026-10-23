Search for flights (legs-based itinerary)

---
updatedAt: 2026-04-24T08:36:00.000Z
agentTools:
  projectIndex: https://docs.liteapi.travel/llms.txt
---

# Search for flights (legs-based itinerary)

## Overview

Search for available flights with real-time pricing from multiple providers. The itinerary **must** be sent as a non-empty `legs` array. Each leg follows the provider **SearchLeg** shape: required `origin`, `destination`, and `date` (YYYY-MM-DD); optional `direction` (`OUTBOUND` or `INBOUND`); optional per-leg `filters` that override global `filters` for that leg only.

**Not supported:** top-level `origin`, `destination`, `departureDate`, or `returnDate` — use `legs` only.

## When to Use

- **Listings** — live prices for search results UI
- **One-way, round-trip, or multi-city** — one leg per segment, in order
- **Filtering** — cabin class, stops, price, refundability, times (globally or per leg)
- **Streaming** — incremental provider results over SSE

## What You Get

- Offers from multiple providers
- Itineraries with segments, layovers, and durations
- Price breakdown (fares, taxes, fees) and baggage hints

## Key Features

- Multi-provider aggregation in one request
- **SSE:** send header `Accept: text/event-stream` on `POST /flights/rates`, or `POST /flights/rates/stream` with the same JSON body
- Global `filters`, `sort`

## Quick Start

**Required:** `legs` (at least one object with `origin`, `destination`, `date`), `adults` (≥ 1), `currency`

**Date limit:** each leg `date` must not be more than 11 months from today.

**Round-trip:** two legs (e.g. outbound then return with `direction` `OUTBOUND` / `INBOUND`). **One-way:** one leg.

# OpenAPI definition

```json
{
  "openapi": "3.0.0",
  "info": {
    "title": "API: Flights",
    "version": "3.0.0",
    "description": "The Flights API provides endpoints for searching flights, managing bookings, and accessing static flight data including airlines and airports."
  },
  "servers": [
    {
      "url": "https://api.liteapi.travel/v3.0"
    }
  ],
  "security": [
    {
      "apikeyAuth": []
    }
  ],
  "components": {
    "securitySchemes": {
      "apikeyAuth": {
        "name": "X-API-Key",
        "type": "apiKey",
        "in": "header"
      }
    },
    "schemas": {
      "FlightSegment": {
        "type": "object",
        "properties": {
          "arrivalTime": {
            "type": "string",
            "description": "Arrival time (ISO 8601)"
          },
          "carrier": {
            "type": "object",
            "properties": {
              "marketingCode": {
                "type": "string",
                "description": "Marketing carrier IATA code"
              },
              "marketingLogo": {
                "type": "string",
                "description": "Marketing carrier logo path/URL"
              },
              "marketingName": {
                "type": "string",
                "description": "Marketing carrier name"
              },
              "operatingCode": {
                "type": "string",
                "description": "Operating carrier IATA code"
              },
              "operatingLogo": {
                "type": "string",
                "description": "Operating carrier logo path/URL"
              },
              "operatingName": {
                "type": "string",
                "description": "Operating carrier name"
              }
            },
            "description": "Marketing and operating carrier details for this segment"
          },
          "departureTime": {
            "type": "string",
            "description": "Departure time (ISO 8601)"
          },
          "destinationCode": {
            "type": "string",
            "description": "Destination IATA code"
          },
          "direction": {
            "type": "string",
            "description": "OUTBOUND or INBOUND"
          },
          "duration": {
            "type": "object",
            "properties": {
              "iso8601": {
                "type": "string",
                "description": "Duration in ISO 8601 format (e.g. PT7H45M)"
              },
              "minutes": {
                "type": "integer",
                "description": "Duration in minutes"
              }
            },
            "description": "Flight duration in ISO 8601 and minutes"
          },
          "flight": {
            "type": "object",
            "properties": {
              "marketingNumber": {
                "type": "string",
                "description": "Flight number as marketed to passengers"
              },
              "operatingNumber": {
                "type": "string",
                "description": "Flight number as operated by the carrier"
              }
            },
            "description": "Marketing and operating flight numbers"
          },
          "originCode": {
            "type": "string",
            "description": "Origin IATA code"
          },
          "originName": {
            "type": "string",
            "description": "Full name of the origin airport"
          },
          "destinationName": {
            "type": "string",
            "description": "Full name of the destination airport"
          },
          "segmentKey": {
            "type": "string",
            "description": "Unique identifier for this segment, used to link with offers, fares, and amenities"
          },
          "stopCount": {
            "type": "integer",
            "description": "Number of en-route (technical) stops inside this segment. 0 means the segment is genuinely non-stop. A technical stop keeps the same flight number and aircraft (no plane change, no bag re-check) but adds ground time, so a one-segment journey can still have stops."
          },
          "stops": {
            "type": "array",
            "items": {
              "$ref": "#/components/schemas/FlightSegmentStop"
            },
            "description": "En-route (technical) stops inside this segment, in travel order. Omitted when stopCount is 0."
          }
        },
        "description": "A single flight segment (one flight number) within a journey. May contain en-route technical stops (see stopCount / stops)."
      },
      "FlightSegmentStop": {
        "type": "object",
        "properties": {
          "airportCode": {
            "type": "string",
            "description": "IATA code of the airport where the aircraft lands for the technical stop"
          },
          "airportName": {
            "type": "string",
            "description": "Full name of the stop airport"
          },
          "arrivalTime": {
            "type": "string",
            "description": "Local arrival time at the stop airport (ISO 8601)"
          },
          "departureTime": {
            "type": "string",
            "description": "Local departure time from the stop airport (ISO 8601)"
          },
          "duration": {
            "type": "object",
            "properties": {
              "iso8601": {
                "type": "string",
                "description": "Ground time in ISO 8601 format (e.g. PT50M)"
              },
              "minutes": {
                "type": "integer",
                "description": "Ground time in minutes"
              }
            },
            "description": "Time spent on the ground at the stop airport"
          }
        },
        "description": "An en-route (technical) stop within a single segment. Unlike a connection between segments, passengers stay on the same flight number: no plane change and no bag re-check.",
        "example": {
          "airportCode": "GIG",
          "airportName": "Rio Galeão – Tom Jobim International Airport",
          "arrivalTime": "2026-10-17T18:35:00",
          "departureTime": "2026-10-17T19:25:00",
          "duration": {
            "iso8601": "PT50M",
            "minutes": 50
          }
        }
      },
      "FlightPrice": {
        "type": "object",
        "properties": {
          "base": {
            "type": "number",
            "description": "Base fare amount as returned by the supplier (before taxes and fees). Never includes the partner markup."
          },
          "currency": {
            "type": "string",
            "description": "ISO 4217 currency code"
          },
          "fees": {
            "type": "number",
            "description": "Supplier service fees and surcharges plus, when the account passes them to the customer, the LiteAPI platform fees itemised in platformFees. Never includes the partner markup."
          },
          "taxes": {
            "type": "number",
            "description": "Total airline / government taxes applied to the fare, as returned by the supplier. Never includes the partner markup."
          },
          "total": {
            "type": "number",
            "description": "Total selling price, including the partner markup and, when present, platformFees.total. Because base and taxes are supplier values, total may exceed base + taxes + fees when a markup is configured."
          },
          "platformFees": {
            "type": "object",
            "description": "LiteAPI platform fees included in total and fees. Present only when the account passes the fees to the customer. Booking-level amounts (not distributed over perPassenger).",
            "properties": {
              "merchantOfRecord": {
                "type": "number",
                "description": "Merchant-of-record fee: percentage of the full transaction value, charged when LiteAPI collects the payment (Payment SDK / third-party). Removed at book time for credit-line and CREDIT_CARD settlements."
              },
              "ticketing": {
                "type": "number",
                "description": "Ticketing fee: percentage of the net fare with a floor and ceiling, per booking or per passenger depending on the account configuration. The rate may depend on the operating airlines. Applies to every payment method."
              },
              "ancillary": {
                "type": "number",
                "description": "Ancillary fee on attached seats and bags: percentage of each item's net price with a per-item floor and ceiling. Present on prebooks / bookings once services are attached. Applies to every payment method."
              },
              "total": {
                "type": "number",
                "description": "merchantOfRecord + ticketing + ancillary"
              }
            }
          },
          "perPassenger": {
            "type": "object",
            "properties": {
              "adult": {
                "type": "object",
                "properties": {
                  "base": {
                    "type": "number",
                    "description": "Base fare for this passenger type"
                  },
                  "currency": {
                    "type": "string",
                    "description": "ISO 4217 currency code"
                  },
                  "fees": {
                    "type": "number",
                    "description": "Fees for this passenger type"
                  },
                  "taxes": {
                    "type": "number",
                    "description": "Taxes for this passenger type (supplier amount, excludes markup)"
                  },
                  "total": {
                    "type": "number",
                    "description": "Total selling price for this passenger type, including the partner markup (may exceed base + taxes + fees)"
                  }
                },
                "description": "Price breakdown for each adult passenger"
              },
              "child": {
                "type": "object",
                "properties": {
                  "base": {
                    "type": "number",
                    "description": "Base fare for this passenger type"
                  },
                  "currency": {
                    "type": "string",
                    "description": "ISO 4217 currency code"
                  },
                  "fees": {
                    "type": "number",
                    "description": "Fees for this passenger type"
                  },
                  "taxes": {
                    "type": "number",
                    "description": "Taxes for this passenger type (supplier amount, excludes markup)"
                  },
                  "total": {
                    "type": "number",
                    "description": "Total selling price for this passenger type, including the partner markup (may exceed base + taxes + fees)"
                  }
                },
                "description": "Price breakdown for each child passenger"
              },
              "infant": {
                "type": "object",
                "properties": {
                  "base": {
                    "type": "number",
                    "description": "Base fare for this passenger type"
                  },
                  "currency": {
                    "type": "string",
                    "description": "ISO 4217 currency code"
                  },
                  "fees": {
                    "type": "number",
                    "description": "Fees for this passenger type"
                  },
                  "taxes": {
                    "type": "number",
                    "description": "Taxes for this passenger type (supplier amount, excludes markup)"
                  },
                  "total": {
                    "type": "number",
                    "description": "Total selling price for this passenger type, including the partner markup (may exceed base + taxes + fees)"
                  }
                },
                "description": "Price breakdown for each infant passenger"
              }
            },
            "description": "Price breakdown per passenger type"
          }
        },
        "description": "Full price breakdown including supplier base fare, taxes and fees, and per-passenger amounts. base, taxes and fees are always the supplier values and never include the partner markup; only total carries it, so total may exceed base + taxes + fees. The markup amount itself is not exposed."
      },
      "FlightOffer": {
        "type": "object",
        "properties": {
          "offerId": {
            "type": "string",
            "description": "Unique offer identifier"
          },
          "expiration": {
            "type": "string",
            "description": "Offer expiration time (ISO 8601)"
          },
          "pricing": {
            "$ref": "#/components/schemas/FlightOfferPricing",
            "description": "Pricing breakdown with FX conversion details"
          },
          "fare": {
            "type": "object",
            "properties": {
              "family": {
                "type": "string",
                "description": "Fare family name (e.g. Economy, Business, First)"
              },
              "mixedCabin": {
                "type": "boolean",
                "description": "True if outbound and inbound legs are in different cabin classes"
              },
              "mixedFareFamily": {
                "type": "boolean",
                "description": "True when legs are sold under different fare families/brands (e.g. Plus outbound + Basic inbound) combined into one fare. `family` reflects the first leg only; baggage and terms reflect the most restrictive leg."
              },
              "seatsRemaining": {
                "type": "integer",
                "description": "Number of seats remaining at this fare"
              }
            },
            "description": "Fare class information"
          },
          "terms": {
            "type": "object",
            "properties": {
              "changeable": {
                "type": "boolean",
                "description": "True if the fare allows changes (rebooking)"
              },
              "refundable": {
                "type": "boolean",
                "description": "True if the fare is refundable"
              },
              "summary": {
                "type": "array",
                "items": {
                  "type": "object",
                  "properties": {
                    "level": {
                      "type": "string",
                      "description": "Severity: info, warning, or danger"
                    },
                    "message": {
                      "type": "string",
                      "description": "Policy message text (e.g. Non-refundable, Changes allowed with fee)"
                    }
                  }
                },
                "description": "Human-readable policy messages with severity levels"
              },
              "changeFee": {
                "$ref": "#/components/schemas/FlightFee",
                "description": "Change fee details; null when the provider does not publish a fee"
              },
              "refundFee": {
                "$ref": "#/components/schemas/FlightFee",
                "description": "Refund/cancellation fee details; null when the provider does not publish a fee"
              },
              "hasChangeFee": {
                "type": "boolean",
                "description": "True when the provider signalled that a change fee applies to the fare, even when the actual amount is not published in `changeFee`. Lets clients render a \"change fee applies — amount on request\" remark for fares where the rule is known but the monetary amount is not exposed (common for LCC content distributed via GDS, e.g. U2 / easyJet via Sabre). When `false` or absent, no change fee is known to apply."
              },
              "hasRefundFee": {
                "type": "boolean",
                "description": "True when the provider signalled that a refund/cancellation fee applies to the fare, even when the actual amount is not published in `refundFee`. Lets clients render a \"cancellation fee applies — amount on request\" remark for fares where the rule is known but the monetary amount is not exposed. When `false` or absent, no refund fee is known to apply."
              }
            },
            "description": "Booking terms and conditions for this offer"
          },
          "provider": {
            "type": "object",
            "description": "Flight provider information",
            "properties": {
              "code": {
                "type": "string",
                "description": "Provider code (e.g. SABRE, TRAVELPORT, ATLAS, FLIGHTHUB)",
                "example": "SABRE"
              },
              "logo": {
                "type": "string",
                "description": "URL to provider logo",
                "example": "https://sandbox.nuitee.flights/static/providers/sabre.svg"
              }
            }
          },
          "baggage": {
            "type": "object",
            "description": "Baggage policy for this offer",
            "properties": {
              "hasCarryOnBag": {
                "type": "boolean",
                "description": "Whether carry-on bag is included"
              },
              "hasCheckedBag": {
                "type": "boolean",
                "description": "Whether checked bag is included"
              },
              "included": {
                "type": "array",
                "description": "List of included baggage allowances",
                "items": {
                  "type": "object",
                  "properties": {
                    "bagType": {
                      "type": "string",
                      "enum": [
                        "cabin",
                        "checked"
                      ],
                      "description": "Type of bag"
                    },
                    "description": {
                      "type": "string",
                      "description": "Human-readable baggage description"
                    },
                    "passengerType": {
                      "type": "string",
                      "enum": [
                        "ADT",
                        "CHD",
                        "INF"
                      ],
                      "description": "Passenger type this allowance applies to"
                    },
                    "pieces": {
                      "type": "integer",
                      "description": "Number of pieces allowed"
                    },
                    "pricing": {
                      "$ref": "#/components/schemas/FlightItemPricing",
                      "description": "Cost if not free (amount 0 means included)"
                    },
                    "unit": {
                      "type": "string",
                      "description": "Weight unit (e.g. kg)"
                    },
                    "weightKg": {
                      "type": "number",
                      "description": "Weight limit in kg"
                    }
                  }
                }
              }
            }
          },
          "segmentFares": {
            "type": "array",
            "description": "Per-segment fare details",
            "items": {
              "type": "object",
              "properties": {
                "bookingCode": {
                  "type": "string",
                  "description": "Booking/RBD class code (e.g. W, Y, J)"
                },
                "cabin": {
                  "type": "string",
                  "description": "Cabin class (e.g. Economy, Business, First)"
                },
                "fareBasisCode": {
                  "type": "string",
                  "description": "Fare basis code"
                },
                "fareFamily": {
                  "type": "string",
                  "description": "Fare family name"
                },
                "seatsRemaining": {
                  "type": "integer",
                  "description": "Number of seats remaining at this fare"
                },
                "segmentKey": {
                  "type": "string",
                  "description": "Links to the segment this fare applies to"
                }
              }
            }
          },
          "segmentAmenities": {
            "type": "array",
            "description": "Per-segment amenity data (each entry linked by segmentKey)",
            "items": {
              "$ref": "#/components/schemas/FlightSegmentAmenities"
            }
          }
        },
        "description": "A bookable offer for a journey, including pricing, baggage policy, fare details, and booking terms"
      },
      "FlightSegmentAmenities": {
        "type": "object",
        "description": "Amenities for a specific segment (linked by segmentKey)",
        "properties": {
          "aircraftType": {
            "type": "string",
            "description": "Aircraft model for this segment",
            "example": "Boeing 787-9"
          },
          "amenities": {
            "type": "array",
            "description": "List of amenities available on this segment",
            "items": {
              "$ref": "#/components/schemas/FlightAmenity"
            }
          },
          "segmentKey": {
            "type": "string",
            "description": "Links to the segment this amenities data belongs to (matches segment.segmentKey)",
            "example": "a3f2b1c9"
          }
        }
      },
      "FlightAmenity": {
        "type": "object",
        "description": "A single in-flight amenity for a segment",
        "properties": {
          "available": {
            "type": "boolean",
            "description": "Whether this amenity is offered on this segment",
            "example": true
          },
          "category": {
            "type": "string",
            "enum": [
              "wifi",
              "power",
              "entertainment",
              "food",
              "seat_comfort"
            ],
            "description": "Amenity category",
            "example": "wifi"
          },
          "chargeable": {
            "type": "boolean",
            "nullable": true,
            "description": "True if paid, False if free, null if unknown",
            "example": true
          },
          "details": {
            "type": "string",
            "nullable": true,
            "description": "Additional details (e.g. 'Streaming only', '34 inch pitch')",
            "example": "Available for purchase"
          },
          "name": {
            "type": "string",
            "description": "Human-readable amenity name",
            "example": "Wi-Fi"
          }
        }
      },
      "FlightJourney": {
        "type": "object",
        "properties": {
          "journeyKey": {
            "type": "string",
            "description": "Unique identifier for this journey (hash of route, flights, and times)"
          },
          "isCheapest": {
            "type": "boolean",
            "description": "True if this is the cheapest journey across all results"
          },
          "cheapestOffer": {
            "$ref": "#/components/schemas/FlightOffer",
            "description": "Quick reference to the lowest-priced offer for this journey"
          },
          "offers": {
            "type": "array",
            "items": {
              "$ref": "#/components/schemas/FlightOffer"
            },
            "description": "All available provider offers for this journey, sorted by price ascending"
          },
          "segments": {
            "type": "array",
            "items": {
              "$ref": "#/components/schemas/FlightSegment"
            },
            "description": "Ordered list of flight segments that make up this journey"
          },
          "parameters": {
            "type": "object",
            "properties": {
              "adults": {
                "type": "integer",
                "description": "Number of adult passengers"
              },
              "children": {
                "type": "integer",
                "description": "Number of child passengers"
              },
              "infants": {
                "type": "integer",
                "description": "Number of infant passengers"
              }
            },
            "description": "Passenger composition used in the search that produced this journey"
          },
          "timestamp": {
            "type": "string",
            "description": "UTC timestamp when this journey was retrieved from the provider"
          },
          "legDurations": {
            "type": "array",
            "items": {
              "$ref": "#/components/schemas/FlightLegDuration"
            },
            "description": "Per-direction elapsed times including layovers (outbound and/or inbound)"
          },
          "totalDuration": {
            "$ref": "#/components/schemas/FlightDuration",
            "description": "Total elapsed time from first departure to last arrival, including all layovers"
          },
          "connections": {
            "type": "array",
            "items": {
              "$ref": "#/components/schemas/FlightConnection"
            },
            "description": "Layover details between consecutive segments"
          }
        },
        "description": "A complete journey (one or more segments) with all available offers"
      },
      "FlightDuration": {
        "type": "object",
        "properties": {
          "iso8601": {
            "type": "string",
            "example": "PT2H30M",
            "description": "Duration in ISO 8601 format (e.g. PT2H30M)"
          },
          "minutes": {
            "type": "integer",
            "example": 150,
            "description": "Duration in minutes"
          }
        },
        "description": "Duration expressed in both ISO 8601 format and minutes"
      },
      "FlightLegDuration": {
        "type": "object",
        "properties": {
          "dayChange": {
            "type": "integer",
            "description": "Number of calendar days added crossing midnight (0 = same day arrival, 1 = next day, etc.)",
            "example": 1
          },
          "direction": {
            "type": "string",
            "enum": [
              "OUTBOUND",
              "INBOUND"
            ],
            "description": "Which leg this duration applies to",
            "example": "OUTBOUND"
          },
          "duration": {
            "$ref": "#/components/schemas/FlightDuration",
            "description": "Elapsed time for this leg including all layovers"
          },
          "overnightFlight": {
            "type": "boolean",
            "description": "True if the flight departs and arrives on different calendar days",
            "example": false
          }
        },
        "description": "Total elapsed time for one direction of a journey (outbound or inbound), including layovers"
      },
      "FlightMoneyAmount": {
        "type": "object",
        "properties": {
          "amount": {
            "type": "number",
            "description": "Monetary amount"
          },
          "currency": {
            "type": "string",
            "description": "ISO 4217 currency code"
          }
        },
        "description": "A monetary amount with currency"
      },
      "FlightItemPricing": {
        "type": "object",
        "properties": {
          "display": {
            "$ref": "#/components/schemas/FlightMoneyAmount",
            "description": "Customer-facing amount (converted to search currency if applicable)"
          },
          "converted": {
            "type": "boolean",
            "description": "True if FX currency conversion was applied"
          }
        },
        "description": "Pricing for an ancillary item (e.g. baggage)"
      },
      "FlightFee": {
        "type": "object",
        "nullable": true,
        "description": "Change or refund fee published by the provider. Null when the provider does not publish a fee.",
        "properties": {
          "pricing": {
            "type": "object",
            "nullable": true,
            "description": "Fee pricing; null when only a percentage is available",
            "properties": {
              "display": {
                "$ref": "#/components/schemas/FlightMoneyAmount",
                "description": "Customer-facing fee amount after FX conversion. Equals the supplier penalty unless a `penalties` markup is configured in the partner's flight markup configuration (the rateSearch markup is not applied to penalties)."
              },
              "converted": {
                "type": "boolean",
                "description": "True when FX conversion was applied"
              }
            }
          },
          "percent": {
            "type": "number",
            "nullable": true,
            "description": "Fee as a percentage of the base fare (e.g. 100 = full penalty). May appear without pricing."
          },
          "applicability": {
            "type": "string",
            "enum": [
              "anytime",
              "noShow",
              "beforeDeparture",
              "afterDeparture"
            ],
            "description": "When the fee applies"
          },
          "label": {
            "type": "string",
            "description": "Human-readable fee description (e.g. 'Change fee (before departure)')"
          }
        }
      },
      "FlightOfferPricing": {
        "type": "object",
        "properties": {
          "display": {
            "$ref": "#/components/schemas/FlightPrice",
            "description": "Customer-facing price breakdown (converted to search currency if applicable)"
          },
          "converted": {
            "type": "boolean",
            "description": "True if FX currency conversion was applied"
          }
        },
        "description": "Full offer pricing with per-passenger breakdown"
      },
      "Error": {
        "type": "object",
        "properties": {
          "error": {
            "type": "object",
            "properties": {
              "code": {
                "type": "integer",
                "description": "Numeric error code"
              },
              "message": {
                "type": "string",
                "description": "Short error message"
              },
              "description": {
                "type": "string",
                "description": "Detailed error description"
              },
              "key": {
                "type": "string",
                "description": "JSON path to the offending request field (e.g. bodyRequest.offerId, query.airlinePnr). Present on validation and client-input errors; omitted on auth and server-side errors.",
                "example": "bodyRequest.offerId"
              }
            },
            "description": "Error details"
          }
        },
        "description": "Standard error response envelope",
        "example": {
          "error": {
            "code": 4000,
            "message": "bad request",
            "description": "invalid flight extra charges: usePaymentSdk must be true for Stripe bookings"
          }
        }
      },
      "FlightSortOptionMeta": {
        "type": "object",
        "description": "Winner reference for a single sort criterion. The `offerId` matches a `journeys[].offers[].offerId` in the same response, allowing fast lookup of the winning offer's full details.",
        "properties": {
          "journeyKey": {
            "type": "string",
            "nullable": true,
            "description": "The journeyKey of the winning journey for this sort criterion"
          },
          "offerId": {
            "type": "string",
            "nullable": true,
            "description": "The offerId of the winning offer (matches `journeys[].offers[].offerId`). Present for offer-centric criteria (best, price); may be null for journey-centric criteria (duration, stops)."
          },
          "price": {
            "type": "number",
            "description": "Display total price of the winning offer (with margin applied)",
            "example": 753.87
          },
          "currency": {
            "type": "string",
            "description": "Currency code of the price (e.g. USD, EUR)",
            "example": "USD"
          }
        }
      },
      "FlightConnection": {
        "type": "object",
        "properties": {
          "arrivalAirportCode": {
            "type": "string",
            "example": "JFK",
            "description": "IATA code of the airport where the passenger arrives for this connection"
          },
          "arrivalAirportName": {
            "type": "string",
            "example": "John F Kennedy International Airport",
            "description": "Full name of the arrival airport for this connection"
          },
          "arrivalTime": {
            "type": "string",
            "example": "2026-01-20T14:30:00",
            "description": "UTC ISO 8601 arrival time at the connection airport"
          },
          "changeAirport": {
            "type": "boolean",
            "example": true,
            "description": "True if the passenger must change airports during this connection"
          },
          "departureAirportCode": {
            "type": "string",
            "example": "LGA",
            "description": "IATA code of the airport from which the passenger departs after layover"
          },
          "departureAirportName": {
            "type": "string",
            "example": "LaGuardia Airport",
            "description": "Full name of the departure airport after layover"
          },
          "departureTime": {
            "type": "string",
            "example": "2026-01-20T17:15:00",
            "description": "UTC ISO 8601 departure time from the connection airport"
          },
          "direction": {
            "type": "string",
            "enum": [
              "OUTBOUND",
              "INBOUND"
            ],
            "description": "Which leg of the journey this connection belongs to (OUTBOUND or INBOUND)"
          },
          "duration": {
            "$ref": "#/components/schemas/FlightDuration",
            "description": "Connection (layover) duration"
          },
          "overnight": {
            "type": "boolean",
            "example": false,
            "description": "True if the layover crosses midnight (arrival and departure on different calendar days)"
          }
        },
        "description": "Layover details between two consecutive flight segments"
      }
    }
  },
  "tags": [
    {
      "name": "Flight Search",
      "description": "Search for available flights and verify offers"
    }
  ],
  "paths": {
    "/flights/rates": {
      "post": {
        "tags": [
          "Flight Search"
        ],
        "summary": "Search for flights (legs-based itinerary)",
        "description": "## Overview\n\nSearch for available flights with real-time pricing from multiple providers. The itinerary **must** be sent as a non-empty `legs` array. Each leg follows the provider **SearchLeg** shape: required `origin`, `destination`, and `date` (YYYY-MM-DD); optional `direction` (`OUTBOUND` or `INBOUND`); optional per-leg `filters` that override global `filters` for that leg only.\n\n**Not supported:** top-level `origin`, `destination`, `departureDate`, or `returnDate` — use `legs` only.\n\n## When to Use\n\n- **Listings** — live prices for search results UI\n- **One-way, round-trip, or multi-city** — one leg per segment, in order\n- **Filtering** — cabin class, stops, price, refundability, times (globally or per leg)\n- **Streaming** — incremental provider results over SSE\n\n## What You Get\n\n- Offers from multiple providers\n- Itineraries with segments, layovers, and durations\n- Price breakdown (fares, taxes, fees) and baggage hints\n\n## Key Features\n\n- Multi-provider aggregation in one request\n- **SSE:** send header `Accept: text/event-stream` on `POST /flights/rates`, or `POST /flights/rates/stream` with the same JSON body\n- Global `filters`, `sort`\n\n## Quick Start\n\n**Required:** `legs` (at least one object with `origin`, `destination`, `date`), `adults` (≥ 1), `currency`\n\n**Date limit:** each leg `date` must not be more than 11 months from today.\n\n**Round-trip:** two legs (e.g. outbound then return with `direction` `OUTBOUND` / `INBOUND`). **One-way:** one leg.",
        "parameters": [],
        "requestBody": {
          "required": true,
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "required": [
                  "legs",
                  "adults",
                  "currency"
                ],
                "properties": {
                  "legs": {
                    "type": "array",
                    "minItems": 1,
                    "description": "Ordered itinerary legs (provider SearchLeg). One-way: one entry. Round-trip: outbound then inbound. Multi-city / open-jaw: additional legs in travel order.",
                    "items": {
                      "type": "object",
                      "required": [
                        "origin",
                        "destination",
                        "date"
                      ],
                      "properties": {
                        "origin": {
                          "type": "string",
                          "description": "Origin airport or city IATA code for this leg",
                          "example": "JFK"
                        },
                        "destination": {
                          "type": "string",
                          "description": "Destination airport or city IATA code for this leg",
                          "example": "CDG"
                        },
                        "date": {
                          "type": "string",
                          "format": "date",
                          "description": "Departure date for this leg (YYYY-MM-DD). Must not be more than 11 months from today.",
                          "example": "2026-07-01"
                        },
                        "direction": {
                          "type": "string",
                          "enum": [
                            "OUTBOUND",
                            "INBOUND"
                          ],
                          "description": "Leg direction (optional; defaults to OUTBOUND on the provider)",
                          "example": "OUTBOUND"
                        },
                        "filters": {
                          "type": "object",
                          "description": "Optional per-leg filters overriding global `filters` for this leg",
                          "example": {
                            "departureTimeAfter": "06:00",
                            "departureTimeBefore": "14:00",
                            "arrivalTimeAfter": "08:00",
                            "arrivalTimeBefore": "22:00",
                            "excludeConnectionAirports": [
                              "IST",
                              "DOH"
                            ],
                            "excludeOvernight": false,
                            "flightNumbers": [
                              "DE2017",
                              "DE4265"
                            ],
                            "flightNumbersMatch": "any",
                            "maxDuration": 600,
                            "maxStops": 1
                          },
                          "properties": {
                            "departureTimeAfter": {
                              "type": "string",
                              "pattern": "^([01]?[0-9]|2[0-3]):[0-5][0-9]$",
                              "description": "Departure after this local time (HH:MM, 24h)",
                              "example": "06:00"
                            },
                            "departureTimeBefore": {
                              "type": "string",
                              "pattern": "^([01]?[0-9]|2[0-3]):[0-5][0-9]$",
                              "description": "Departure before this local time (HH:MM, 24h)",
                              "example": "14:00"
                            },
                            "arrivalTimeAfter": {
                              "type": "string",
                              "pattern": "^([01]?[0-9]|2[0-3]):[0-5][0-9]$",
                              "description": "Arrival after this local time (HH:MM, 24h)",
                              "example": "08:00"
                            },
                            "arrivalTimeBefore": {
                              "type": "string",
                              "pattern": "^([01]?[0-9]|2[0-3]):[0-5][0-9]$",
                              "description": "Arrival before this local time (HH:MM, 24h)",
                              "example": "22:00"
                            },
                            "excludeConnectionAirports": {
                              "type": "array",
                              "items": {
                                "type": "string"
                              },
                              "description": "Exclude layovers at these airports (e.g. IST, DOH)",
                              "example": [
                                "IST",
                                "DOH"
                              ]
                            },
                            "excludeAirlines": {
                              "type": "array",
                              "items": {
                                "type": "string",
                                "pattern": "^[A-Za-z0-9]{2}$"
                              },
                              "description": "Exclude airlines on this leg only (2-character IATA airline codes, case-insensitive): a journey is removed when a flight on this leg is marketed or operated by one of them. Replaces the top-level filters.excludeAirlines on this leg; airlines excluded on your account are always excluded.",
                              "example": [
                                "AA"
                              ]
                            },
                            "excludeOvernight": {
                              "type": "boolean",
                              "description": "Exclude red-eye flights and overnight layovers",
                              "example": false
                            },
                            "flightNumbers": {
                              "type": "array",
                              "items": {
                                "type": "string"
                              },
                              "description": "Filter by flight numbers (e.g. SK500, AF123)",
                              "example": [
                                "DE2017",
                                "DE4265"
                              ]
                            },
                            "flightNumbersMatch": {
                              "type": "string",
                              "enum": [
                                "any",
                                "all"
                              ],
                              "description": "'any' = at least one match, 'all' = all specified flights",
                              "example": "any"
                            },
                            "maxDuration": {
                              "type": "integer",
                              "minimum": 1,
                              "description": "Max leg duration in minutes",
                              "example": 600
                            },
                            "maxStops": {
                              "type": "integer",
                              "minimum": 0,
                              "maximum": 2,
                              "description": "Max stops for this leg. Counts connections between segments and en-route technical stops inside a segment (segments[].stopCount); 0 = genuinely non-stop.",
                              "example": 1
                            }
                          }
                        }
                      }
                    },
                    "example": [
                      {
                        "origin": "JFK",
                        "destination": "CDG",
                        "date": "2026-07-01",
                        "direction": "OUTBOUND",
                        "filters": {
                          "departureTimeAfter": "06:00",
                          "departureTimeBefore": "14:00",
                          "arrivalTimeAfter": "08:00",
                          "arrivalTimeBefore": "22:00",
                          "excludeConnectionAirports": [
                            "IST",
                            "DOH"
                          ],
                          "excludeOvernight": false,
                          "flightNumbers": [
                            "DE2017",
                            "DE4265"
                          ],
                          "flightNumbersMatch": "any",
                          "maxDuration": 600,
                          "maxStops": 1
                        }
                      },
                      {
                        "origin": "CDG",
                        "destination": "JFK",
                        "date": "2026-08-02",
                        "direction": "INBOUND",
                        "filters": {
                          "maxStops": 1,
                          "excludeOvernight": true
                        }
                      }
                    ]
                  },
                  "adults": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Number of adults (12+)",
                    "example": 1
                  },
                  "children": {
                    "type": "integer",
                    "minimum": 0,
                    "description": "Number of children (2-11)",
                    "example": 0
                  },
                  "infants": {
                    "type": "integer",
                    "minimum": 0,
                    "description": "Number of infants (<2)",
                    "example": 0
                  },
                  "childrenAges": {
                    "type": "array",
                    "items": {
                      "type": "integer",
                      "minimum": 2,
                      "maximum": 11
                    },
                    "description": "Age of each child (2–11 inclusive, per IATA). Length must equal children count. Optional — omit if ages are not relevant.",
                    "example": [
                      5,
                      11
                    ]
                  },
                  "infantAges": {
                    "type": "array",
                    "items": {
                      "type": "integer",
                      "minimum": 0,
                      "maximum": 1
                    },
                    "description": "Age of each infant (under 2, per IATA). Length must equal infants count. Optional — omit if ages are not relevant.",
                    "example": [
                      1
                    ]
                  },
                  "cabinClass": {
                    "type": "string",
                    "enum": [
                      "ECONOMY",
                      "PREMIUM_ECONOMY",
                      "BUSINESS",
                      "FIRST"
                    ],
                    "description": "Cabin class (provider SearchFilters codes only). Same enum as filters.cabinClass.",
                    "example": "ECONOMY"
                  },
                  "currency": {
                    "type": "string",
                    "minLength": 1,
                    "description": "ISO 4217 currency code",
                    "example": "USD"
                  },
                  "country": {
                    "type": "string",
                    "description": "Optional ISO 3166-1 alpha-2 country code for point of sale",
                    "example": "US"
                  },
                  "margin": {
                    "type": "object",
                    "description": "Optional per-request markup overrides. Each property is a percentage that replaces your account-level flight markup for that category on this search only; categories you omit keep their configured markup. Set at least one property. Only honoured when flight margin editing is enabled for your account; ignored otherwise. `rateSearch` is applied to the fare prices returned by this search; `seats`, `bags` and `penalties` are attached to the returned offerIds and applied when the offer is verified, prebooked and booked.",
                    "properties": {
                      "rateSearch": {
                        "type": "number",
                        "minimum": 0,
                        "description": "Fare markup percentage (journey total and per-passenger prices). Takes precedence over any airline/route overrides configured for your account.",
                        "example": 10
                      },
                      "seats": {
                        "type": "number",
                        "minimum": 0,
                        "description": "Markup percentage for seat ancillaries.",
                        "example": 5
                      },
                      "bags": {
                        "type": "number",
                        "minimum": 0,
                        "description": "Markup percentage for baggage ancillaries and journey baggage prices.",
                        "example": 5
                      },
                      "penalties": {
                        "type": "number",
                        "minimum": 0,
                        "description": "Markup percentage applied to the displayed airline change / refund fees (`terms.changeFee`, `terms.refundFee`).",
                        "example": 0
                      }
                    },
                    "example": {
                      "rateSearch": 10,
                      "seats": 5,
                      "bags": 5
                    }
                  },
                  "filters": {
                    "type": "object",
                    "description": "Optional filters to refine search results",
                    "example": {
                      "departureTimeBefore": "14:00",
                      "arrivalTimeBefore": "18:00",
                      "excludeConnectionAirports": [
                        "IST",
                        "DOH"
                      ],
                      "excludeOvernight": false,
                      "flightNumbers": [
                        "DE2017",
                        "DE4265"
                      ],
                      "flightNumbersMatch": "any",
                      "maxDuration": 600,
                      "maxStops": 1,
                      "maxPrice": 1500,
                      "minPrice": 200,
                      "includesCarryOnBag": false,
                      "includesCheckedBag": false,
                      "changeableOnly": false,
                      "refundableOnly": false,
                      "showCheapestOfferOnly": false,
                      "cabinClass": "BUSINESS",
                      "cabinClassMatch": "at_least",
                      "legDurations": [
                        {
                          "direction": "OUTBOUND",
                          "maxMinutes": 600
                        },
                        {
                          "direction": "INBOUND",
                          "maxMinutes": 720
                        }
                      ]
                    },
                    "properties": {
                      "arrivalTimeBefore": {
                        "type": "string",
                        "description": "Filter journeys arriving before this time (HH:MM, 24h)",
                        "example": "18:00",
                        "pattern": "^([01]?[0-9]|2[0-3]):[0-5][0-9]$"
                      },
                      "cabinClass": {
                        "type": "string",
                        "enum": [
                          "ECONOMY",
                          "PREMIUM_ECONOMY",
                          "BUSINESS",
                          "FIRST",
                          "Economy",
                          "Business",
                          "First"
                        ],
                        "description": "Cabin class filter (maps to provider SearchFilters.cabinClass). Overrides top-level cabinClass for this field when both are set.",
                        "example": "BUSINESS"
                      },
                      "cabinClassMatch": {
                        "type": "string",
                        "enum": [
                          "exactly",
                          "at_least"
                        ],
                        "description": "'exactly' for exact match, 'at_least' for selected cabin or better",
                        "example": "at_least"
                      },
                      "changeableOnly": {
                        "type": "boolean",
                        "description": "When true, only show offers with changeable (modifiable) fares",
                        "example": false
                      },
                      "departureTimeBefore": {
                        "type": "string",
                        "description": "Filter journeys departing before this time (HH:MM, 24h)",
                        "example": "14:00",
                        "pattern": "^([01]?[0-9]|2[0-3]):[0-5][0-9]$"
                      },
                      "excludeConnectionAirports": {
                        "type": "array",
                        "items": {
                          "type": "string"
                        },
                        "description": "Exclude layovers at these airports (e.g. IST, DOH)",
                        "example": [
                          "IST",
                          "DOH"
                        ]
                      },
                      "excludeAirlines": {
                        "type": "array",
                        "items": {
                          "type": "string",
                          "pattern": "^[A-Za-z0-9]{2}$"
                        },
                        "description": "Exclude airlines (2-character IATA airline codes, case-insensitive): a journey is removed when any of its flights is marketed or operated by one of them (codeshares included), and an offer is removed when one of them is its validating (ticketing) carrier. A leg's own filters.excludeAirlines replaces this list on that leg. Airlines excluded on your account are always excluded in addition to this list.",
                        "example": [
                          "AA"
                        ]
                      },
                      "excludeOvernight": {
                        "type": "boolean",
                        "description": "Exclude red-eye flights and overnight layovers",
                        "example": false
                      },
                      "flightNumbers": {
                        "type": "array",
                        "items": {
                          "type": "string"
                        },
                        "description": "Filter by flight numbers (e.g. SK500, AF123)",
                        "example": [
                          "DE2017",
                          "DE4265"
                        ]
                      },
                      "flightNumbersMatch": {
                        "type": "string",
                        "enum": [
                          "any",
                          "all"
                        ],
                        "description": "'any' = at least one match, 'all' = all specified flights",
                        "example": "any"
                      },
                      "includesCarryOnBag": {
                        "type": "boolean",
                        "description": "Only show offers with carry-on included",
                        "example": false
                      },
                      "includesCheckedBag": {
                        "type": "boolean",
                        "description": "Only show offers with checked bag included",
                        "example": false
                      },
                      "legDurations": {
                        "type": "array",
                        "description": "Per-leg max duration constraints. Each entry limits one direction (OUTBOUND or INBOUND) independently.",
                        "example": [
                          {
                            "direction": "OUTBOUND",
                            "maxMinutes": 600
                          },
                          {
                            "direction": "INBOUND",
                            "maxMinutes": 720
                          }
                        ],
                        "items": {
                          "type": "object",
                          "required": [
                            "direction",
                            "maxMinutes"
                          ],
                          "properties": {
                            "direction": {
                              "type": "string",
                              "enum": [
                                "OUTBOUND",
                                "INBOUND"
                              ],
                              "description": "Which leg to constrain",
                              "example": "OUTBOUND"
                            },
                            "maxMinutes": {
                              "type": "integer",
                              "minimum": 1,
                              "description": "Maximum leg duration in minutes (inclusive)",
                              "example": 600
                            }
                          }
                        }
                      },
                      "maxDuration": {
                        "type": "integer",
                        "minimum": 1,
                        "nullable": true,
                        "description": "Maximum total journey duration in minutes (inclusive). Journeys exceeding this duration are excluded.",
                        "example": 600
                      },
                      "maxPrice": {
                        "type": "number",
                        "minimum": 0,
                        "description": "Maximum total price (offer total, in search currency)",
                        "example": 1500
                      },
                      "minPrice": {
                        "type": "number",
                        "minimum": 0,
                        "description": "Minimum total price (offer total, in search currency)",
                        "example": 200
                      },
                      "maxStops": {
                        "type": "integer",
                        "nullable": true,
                        "minimum": -1,
                        "maximum": 2,
                        "description": "Maximum number of stops: -1 or omit = any, 0 = genuinely non-stop, 1 = 1 or fewer, 2 = 2 or fewer. Stops include both connections between segments and en-route technical stops inside a segment (segments[].stopCount), so a single flight number with a technical landing is excluded by maxStops: 0.",
                        "example": 1
                      },
                      "refundableOnly": {
                        "type": "boolean",
                        "description": "When true, only show offers with refundable fares",
                        "example": false
                      },
                      "showCheapestOfferOnly": {
                        "type": "boolean",
                        "description": "Return only cheapest offer per journey",
                        "example": false
                      }
                    }
                  },
                  "sort": {
                    "type": "object",
                    "description": "Sort options for results",
                    "example": {
                      "sortBy": "price",
                      "sortOrder": "asc"
                    },
                    "properties": {
                      "sortBy": {
                        "type": "string",
                        "enum": [
                          "price",
                          "duration",
                          "departure",
                          "arrival",
                          "stops"
                        ],
                        "description": "Sort by price, duration, departure, arrival, or stops. The stops criterion counts connections plus en-route technical stops (segments[].stopCount).",
                        "example": "price"
                      },
                      "sortOrder": {
                        "type": "string",
                        "enum": [
                          "asc",
                          "desc"
                        ],
                        "description": "asc or desc",
                        "example": "asc"
                      }
                    }
                  }
                }
              },
              "example": {
                "legs": [
                  {
                    "origin": "JFK",
                    "destination": "CDG",
                    "date": "2026-07-01",
                    "direction": "OUTBOUND",
                    "filters": {
                      "departureTimeAfter": "06:00",
                      "departureTimeBefore": "14:00",
                      "arrivalTimeAfter": "08:00",
                      "arrivalTimeBefore": "22:00",
                      "excludeConnectionAirports": [
                        "IST",
                        "DOH"
                      ],
                      "excludeOvernight": false,
                      "flightNumbers": [
                        "DE2017",
                        "DE4265"
                      ],
                      "flightNumbersMatch": "any",
                      "maxDuration": 600,
                      "maxStops": 1
                    }
                  },
                  {
                    "origin": "CDG",
                    "destination": "JFK",
                    "date": "2026-08-02",
                    "direction": "INBOUND",
                    "filters": {
                      "maxStops": 1,
                      "excludeOvernight": true
                    }
                  }
                ],
                "adults": 1,
                "children": 0,
                "infants": 0,
                "currency": "USD",
                "country": "US",
                "filters": {
                  "maxStops": 1,
                  "maxPrice": 1500,
                  "includesCheckedBag": false,
                  "refundableOnly": false
                },
                "sort": {
                  "sortBy": "price",
                  "sortOrder": "asc"
                }
              }
            }
          },
          "description": "Flight rates search request. Itinerary is expressed only in `legs` (each leg: `origin`, `destination`, `date`; optional `direction`, `filters`). Passengers: `adults`, `children`, `infants`, optional `childrenAges` / `infantAges`. Also optional: `cabinClass`, `country` (point of sale), global `filters`, `sort`."
        },
        "responses": {
          "200": {
            "description": "Successful response",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "data": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "properties": {
                          "journeys": {
                            "type": "array",
                            "items": {
                              "$ref": "#/components/schemas/FlightJourney"
                            },
                            "description": "Journeys returned by this provider batch, sorted by price ascending"
                          },
                          "sortMetadata": {
                            "type": "object",
                            "nullable": true,
                            "description": "Precomputed winner references for each sort criterion. Use the `offerId` to quickly look up the winning offer in `journeys[].offers[]`. Sent with every response (including SSE partial results) so the frontend can keep stable sort-tab labels without recalculating.",
                            "properties": {
                              "best": {
                                "$ref": "#/components/schemas/FlightSortOptionMeta",
                                "description": "Journey with the lowest blended score (price + duration + stops). Stops include en-route technical stops (segments[].stopCount)."
                              },
                              "duration": {
                                "$ref": "#/components/schemas/FlightSortOptionMeta",
                                "description": "Journey with the shortest total flight time"
                              },
                              "price": {
                                "$ref": "#/components/schemas/FlightSortOptionMeta",
                                "description": "Cheapest journey"
                              },
                              "stops": {
                                "$ref": "#/components/schemas/FlightSortOptionMeta",
                                "description": "Journey with the fewest stops (connections between segments plus en-route technical stops inside segments)"
                              }
                            }
                          }
                        }
                      },
                      "description": "List of search result sets, one per provider batch"
                    }
                  }
                },
                "example": {
                  "data": [
                    {
                      "journeys": [
                        {
                          "journeyKey": "a3bbe883fe3a4f6b",
                          "isCheapest": true,
                          "timestamp": "2026-03-19T12:52:59.494Z",
                          "totalDuration": {
                            "iso8601": "PT7H45M",
                            "minutes": 465
                          },
                          "legDurations": [
                            {
                              "direction": "OUTBOUND",
                              "duration": {
                                "iso8601": "PT7H45M",
                                "minutes": 465
                              },
                              "dayChange": 1,
                              "overnightFlight": false
                            }
                          ],
                          "parameters": {
                            "adults": 1,
                            "children": 0,
                            "infants": 0
                          },
                          "segments": [
                            {
                              "segmentKey": "d0a8a7dd",
                              "stopCount": 0,
                              "originCode": "JFK",
                              "originName": "John F. Kennedy International Airport",
                              "destinationCode": "CDG",
                              "destinationName": "Charles de Gaulle Airport",
                              "departureTime": "2026-07-01T16:10:00",
                              "arrivalTime": "2026-07-02T05:55:00",
                              "direction": "OUTBOUND",
                              "duration": {
                                "iso8601": "PT7H45M",
                                "minutes": 465
                              },
                              "flight": {
                                "marketingNumber": "2017",
                                "operatingNumber": "2017"
                              },
                              "carrier": {
                                "marketingCode": "DE",
                                "marketingLogo": "https://sandbox.nuitee.flights/static/images/airlines/DE.png",
                                "marketingName": "Condor Flugdienst",
                                "operatingCode": "DE",
                                "operatingLogo": "https://sandbox.nuitee.flights/static/images/airlines/DE.png",
                                "operatingName": "Condor Flugdienst"
                              }
                            }
                          ],
                          "offers": [
                            {
                              "offerId": "h6NwaWTZJDAxOWQwNjFlLWRlMjYtNzI1NC1hZDNmLTA0ZDkwZmMxMDNhZaJ0cMtAh471wo9cKaJtdctAJAAAAAAAAKNjdXKjVVNEo3VpZM0CeaJkZKoyMDI2LTA3LTAxonJkqjIwMjYtMDgtMDI=",
                              "expiration": "2026-03-19T12:52:59.494Z",
                              "pricing": {
                                "display": {
                                  "total": 753.87,
                                  "currency": "USD",
                                  "base": 403.63,
                                  "fees": 0,
                                  "taxes": 350.24,
                                  "perPassenger": {
                                    "adult": {
                                      "base": 403.63,
                                      "currency": "USD",
                                      "fees": 0,
                                      "taxes": 350.24,
                                      "total": 753.87
                                    },
                                    "child": {
                                      "base": 0,
                                      "currency": "USD",
                                      "fees": 0,
                                      "taxes": 0,
                                      "total": 0
                                    },
                                    "infant": {
                                      "base": 0,
                                      "currency": "USD",
                                      "fees": 0,
                                      "taxes": 0,
                                      "total": 0
                                    }
                                  }
                                },
                                "converted": false
                              },
                              "provider": {
                                "code": "SABRE",
                                "logo": "https://sandbox.nuitee.flights/static/providers/sabre.svg"
                              },
                              "fare": {
                                "family": "Economy",
                                "mixedCabin": false,
                                "mixedFareFamily": false,
                                "seatsRemaining": 7
                              },
                              "baggage": {
                                "hasCarryOnBag": true,
                                "hasCheckedBag": false,
                                "included": [
                                  {
                                    "bagType": "cabin",
                                    "description": "1 carry-on bag up to 8 kg",
                                    "passengerType": "ADT",
                                    "pieces": 1,
                                    "pricing": {
                                      "display": {
                                        "amount": 0,
                                        "currency": "USD"
                                      },
                                      "converted": false
                                    },
                                    "unit": "kg",
                                    "weightKg": 8
                                  }
                                ]
                              },
                              "terms": {
                                "changeable": true,
                                "refundable": false,
                                "summary": [
                                  {
                                    "level": "warning",
                                    "message": "Change fee applies"
                                  },
                                  {
                                    "level": "danger",
                                    "message": "Non-refundable"
                                  }
                                ],
                                "changeFee": {
                                  "pricing": {
                                    "display": {
                                      "amount": 75,
                                      "currency": "USD"
                                    },
                                    "converted": false
                                  },
                                  "percent": null,
                                  "applicability": "beforeDeparture",
                                  "label": "Change fee (before departure)"
                                },
                                "refundFee": null
                              },
                              "segmentFares": [
                                {
                                  "segmentKey": "d0a8a7dd",
                                  "bookingCode": "W",
                                  "cabin": "Economy",
                                  "fareBasisCode": "WRAQ1",
                                  "fareFamily": "Economy",
                                  "seatsRemaining": 7
                                }
                              ],
                              "segmentAmenities": [
                                {
                                  "segmentKey": "d0a8a7dd",
                                  "aircraftType": "339",
                                  "amenities": [
                                    {
                                      "available": true,
                                      "category": "wifi",
                                      "chargeable": true,
                                      "name": "Wi-Fi",
                                      "details": "Available for purchase"
                                    },
                                    {
                                      "available": true,
                                      "category": "entertainment",
                                      "chargeable": false,
                                      "name": "In-seat entertainment",
                                      "details": null
                                    }
                                  ]
                                }
                              ]
                            }
                          ]
                        }
                      ],
                      "sortMetadata": {
                        "best": {
                          "journeyKey": "a3bbe883fe3a4f6b",
                          "offerId": "h6NwaWTZJDAxOWQwNjFlLWRlMjYtNzI1NC1hZDNmLTA0ZDkwZmMxMDNhZaJ0cMtAh471wo9cKaJtdctAJAAAAAAAAKNjdXKjVVNEo3VpZM0CeaJkZKoyMDI2LTA3LTAxonJkqjIwMjYtMDgtMDI=",
                          "price": 753.87,
                          "currency": "USD"
                        },
                        "price": {
                          "journeyKey": "a3bbe883fe3a4f6b",
                          "offerId": "h6NwaWTZJDAxOWQwNjFlLWRlMjYtNzI1NC1hZDNmLTA0ZDkwZmMxMDNhZaJ0cMtAh471wo9cKaJtdctAJAAAAAAAAKNjdXKjVVNEo3VpZM0CeaJkZKoyMDI2LTA3LTAxonJkqjIwMjYtMDgtMDI=",
                          "price": 753.87,
                          "currency": "USD"
                        },
                        "duration": {
                          "journeyKey": "a3bbe883fe3a4f6b"
                        },
                        "stops": {
                          "journeyKey": "a3bbe883fe3a4f6b"
                        }
                      }
                    }
                  ]
                }
              },
              "text/event-stream": {
                "schema": {
                  "type": "string",
                  "description": "When the request includes `Accept: text/event-stream`. Server-Sent Events (SSE): each message has optional `event:` (kebab-case, e.g. `rates-chunk`, `rates-complete`, `result`, `error`, `message`) and one or more `data:` lines, terminated by a blank line. Each `data` payload is JSON with the same `data[].journeys` shape as the `application/json` 200 response (no top-level `success` or `apiMeta`)."
                },
                "example": "event: rates-chunk\ndata: {\"data\":[{\"journeys\":[{\"journeyKey\":\"a3bbe883fe3a4f6b\",\"isCheapest\":true,\"timestamp\":\"2026-03-19T12:52:59.494Z\",\"totalDuration\":{\"iso8601\":\"PT7H45M\",\"minutes\":465},\"legDurations\":[{\"direction\":\"OUTBOUND\",\"duration\":{\"iso8601\":\"PT7H45M\",\"minutes\":465},\"dayChange\":1,\"overnightFlight\":false}],\"parameters\":{\"adults\":1,\"children\":0,\"infants\":0},\"segments\":[{\"segmentKey\":\"d0a8a7dd\",\"originCode\":\"JFK\",\"originName\":\"John F. Kennedy International Airport\",\"destinationCode\":\"CDG\",\"destinationName\":\"Charles de Gaulle Airport\",\"departureTime\":\"2026-07-01T16:10:00\",\"arrivalTime\":\"2026-07-02T05:55:00\",\"direction\":\"OUTBOUND\",\"duration\":{\"iso8601\":\"PT7H45M\",\"minutes\":465},\"flight\":{\"marketingNumber\":\"2017\",\"operatingNumber\":\"2017\"},\"carrier\":{\"marketingCode\":\"DE\",\"marketingLogo\":\"https://sandbox.nuitee.flights/static/images/airlines/DE.png\",\"marketingName\":\"Condor Flugdienst\",\"operatingCode\":\"DE\",\"operatingLogo\":\"https://sandbox.nuitee.flights/static/images/airlines/DE.png\",\"operatingName\":\"Condor Flugdienst\"}}],\"offers\":[{\"offerId\":\"h6NwaWTZJDAxOWQwNjFlLWRlMjYtNzI1NC1hZDNmLTA0ZDkwZmMxMDNhZaJ0cMtAh471wo9cKaJtdctAJAAAAAAAAKNjdXKjVVNEo3VpZM0CeaJkZKoyMDI2LTA3LTAxonJkqjIwMjYtMDgtMDI=\",\"expiration\":\"2026-03-19T12:52:59.494Z\",\"pricing\":{\"display\":{\"total\":753.87,\"currency\":\"USD\",\"base\":403.63,\"fees\":0,\"taxes\":350.24,\"perPassenger\":{\"adult\":{\"base\":403.63,\"currency\":\"USD\",\"fees\":0,\"taxes\":350.24,\"total\":753.87},\"child\":{\"base\":0,\"currency\":\"USD\",\"fees\":0,\"taxes\":0,\"total\":0},\"infant\":{\"base\":0,\"currency\":\"USD\",\"fees\":0,\"taxes\":0,\"total\":0}}},\"converted\":false},\"provider\":{\"code\":\"SABRE\",\"logo\":\"https://sandbox.nuitee.flights/static/providers/sabre.svg\"},\"fare\":{\"family\":\"Economy\",\"mixedCabin\":false,\"mixedFareFamily\":false,\"seatsRemaining\":7},\"baggage\":{\"hasCarryOnBag\":true,\"hasCheckedBag\":false,\"included\":[{\"bagType\":\"cabin\",\"description\":\"1 carry-on bag up to 8 kg\",\"passengerType\":\"ADT\",\"pieces\":1,\"pricing\":{\"display\":{\"amount\":0,\"currency\":\"USD\"},\"converted\":false},\"unit\":\"kg\",\"weightKg\":8}]},\"terms\":{\"changeable\":false,\"refundable\":false,\"summary\":[{\"level\":\"danger\",\"message\":\"Non-refundable fare\"}]},\"segmentFares\":[{\"segmentKey\":\"d0a8a7dd\",\"bookingCode\":\"W\",\"cabin\":\"Economy\",\"fareBasisCode\":\"WRAQ1\",\"fareFamily\":\"Economy\",\"seatsRemaining\":7}],\"segmentAmenities\":[{\"segmentKey\":\"d0a8a7dd\",\"aircraftType\":\"339\",\"amenities\":[{\"available\":true,\"category\":\"wifi\",\"chargeable\":true,\"name\":\"Wi-Fi\",\"details\":\"Available for purchase\"},{\"available\":true,\"category\":\"entertainment\",\"chargeable\":false,\"name\":\"In-seat entertainment\",\"details\":null}]}]}]}]}]}\n\nevent: rates-complete\ndata: {}\n"
              }
            }
          },
          "400": {
            "description": "Bad request — missing or invalid search parameters",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/Error"
                },
                "examples": {
                  "missingRequiredField": {
                    "summary": "Missing required field",
                    "value": {
                      "error": {
                        "code": 41002,
                        "description": "field 'Legs' failed validation 'min'",
                        "message": "required search field is missing",
                        "key": "bodyRequest.legs"
                      }
                    }
                  },
                  "invalidParametersInfant": {
                    "summary": "Invalid parameters: infant not allowed",
                    "value": {
                      "error": {
                        "code": 41012,
                        "description": "number of infants cannot exceed number of adults, each infant must be accompanied by an adult",
                        "message": "search input validation error",
                        "key": "bodyRequest.infants"
                      }
                    }
                  },
                  "invalidParametersPassenger": {
                    "summary": "Invalid parameters: invalid passenger data",
                    "value": {
                      "error": {
                        "code": 41006,
                        "description": "Invalid search parameters: passenger data is invalid",
                        "message": "invalid parameters: invalid passenger data",
                        "key": "bodyRequest"
                      }
                    }
                  },
                  "validationInfant": {
                    "summary": "Validation error: infant not allowed",
                    "value": {
                      "error": {
                        "code": 41009,
                        "description": "Search validation failed: infant passengers are not allowed",
                        "message": "search validation error: infant not allowed",
                        "key": "bodyRequest.infants"
                      }
                    }
                  }
                }
              }
            }
          },
          "401": {
            "description": "Unauthorized",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/Error"
                },
                "examples": {
                  "unauthorized": {
                    "summary": "Unauthorized",
                    "value": {
                      "error": {
                        "code": 41004,
                        "description": "Authentication failed",
                        "message": "unauthorized"
                      }
                    }
                  },
                  "credentialFailed": {
                    "summary": "Credential resolution failed",
                    "value": {
                      "error": {
                        "code": 41011,
                        "description": "Authentication failed: credential resolution failed",
                        "message": "unauthorized: credential resolution failed"
                      }
                    }
                  }
                }
              }
            }
          },
          "502": {
            "description": "Provider error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/Error"
                },
                "examples": {
                  "providerAuthFailedConnection": {
                    "summary": "Provider auth failed: connection",
                    "value": {
                      "error": {
                        "code": 51001,
                        "description": "Provider authentication failed due to connection failure",
                        "message": "provider authentication failed: connection failed",
                        "key": "bodyRequest"
                      }
                    }
                  },
                  "providerAuthFailedRoutingClosed": {
                    "summary": "Provider auth failed: routing closed",
                    "value": {
                      "error": {
                        "code": 51005,
                        "description": "Provider authentication failed: routing is closed",
                        "message": "provider auth failed: routing closed",
                        "key": "bodyRequest"
                      }
                    }
                  },
                  "providerErrorRoutingClosed": {
                    "summary": "Provider error: routing closed",
                    "value": {
                      "error": {
                        "code": 51006,
                        "description": "Provider returned an error: routing is closed",
                        "message": "provider error: routing closed",
                        "key": "bodyRequest"
                      }
                    }
                  }
                }
              }
            }
          },
          "503": {
            "description": "Service unavailable",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/Error"
                },
                "examples": {
                  "providerDisabled": {
                    "summary": "Provider disabled",
                    "value": {
                      "error": {
                        "code": 51003,
                        "description": "The search provider is currently disabled",
                        "message": "search provider disabled"
                      }
                    }
                  },
                  "serviceUnavailable": {
                    "summary": "Service unavailable",
                    "value": {
                      "error": {
                        "code": 51004,
                        "description": "The search service is temporarily unavailable",
                        "message": "search service unavailable"
                      }
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
```