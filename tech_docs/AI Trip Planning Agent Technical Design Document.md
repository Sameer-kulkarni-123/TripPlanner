# AI Trip Planning Agent — Technical Design Document v0.1

Nuitee API docs link: [https://docs.liteapi.travel/reference/authentication](https://docs.liteapi.travel/reference/authentication)

**Version:** 0.1 — Initial Architecture and Travel Agent Specification  

**Status:** Draft — under active development  

**Last updated:** 23 October 2026

- **Index**
- Non-Technical Stuff
    
    # 1. Purpose and Scope
    
    This document defines the proposed technical architecture, component responsibilities, integrations, data flows, and implementation strategy for an AI-powered trip-planning application.
    
    The product will let users describe a trip in natural language. The Orchestrator Agent coordinates the Travel Agent for flights, trains, and buses; the Itinerary Agent for attractions and activities; and the Hotel Agent for accommodation discovery. The orchestrator reconciles the results and validates the overall trip budget.
    
    ## 1.1 Goals
    
    - Accept natural-language trip-planning requests.
    - Research transportation options across flights, trains, buses, and other supported modes.
    - Generate personalized itineraries and activity recommendations.
    - Recommend accommodation options through hotel search. Overall trip-budget reconciliation remains the Orchestrator Agent's responsibility.
    - Coordinate three specialized AI agents through a central orchestrator.
    - Present recommendations with transparent prices, schedules, and source references.
    - Support domestic and international trips, subject to third-party provider coverage.
    - Provide a modular architecture that can accommodate additional providers, agents, and capabilities.
    
    ## 1.2 Initial non-goals
    
    - Processing ticket purchases or hotel reservations within the application.
    - Operating a payment gateway for travel transactions.
    - Guaranteeing that every transport provider, country, route, or accommodation is supported.
    - Making autonomous, irreversible purchases.
    - Treating LLM-generated estimates as verified prices or availability.
- System Overview
    
    # 2. System Overview
    
    The application will use an **Orchestrator Agent** to coordinate three specialized agents:
    
    1. **Orchestrator Agent:** interprets the user's trip-planning goal, maintains workflow state, decides which specialist to call and when, resolves missing information, reconciles agent outputs, enforces cross-agent constraints, and produces the final trip plan.
    2. **Travel Agent:** transportation discovery, comparison, and ranking.
    3. **Itinerary Agent:** activities, attractions, and day-by-day scheduling.
    4. **Hotel Agent:** hotel discovery, filtering, comparison, and accommodation recommendations.
    
    ## 2.1 High-level architecture
    
    ```mermaid
    flowchart TD
        U["User"] --> FE["Frontend application"]
        FE --> API["Backend API - FastAPI"]
        API --> ORCH["Orchestrator Agent - implemented with LangGraph"]
        ORCH <--> STATE["Shared trip state"]
        ORCH --> TA["Travel Agent"]
        ORCH --> IA["Itinerary Agent"]
        ORCH --> HA["Hotel Agent"]
        TA --> TP["Transport provider adapters"]
        IA --> EXP["Nuitee experience search"]
        IA --> MAPS["Maps and places integrations"]
        HA --> HOTELS["Nuitee hotel search"]
        TA --> FLIGHTS["Nuitee flight search"]
        TP --> EXT["Other transport APIs, if added"]
        FLIGHTS --> NUITEE["Nuitee API"]
        HOTELS --> NUITEE
        EXP --> NUITEE
        MAPS --> EXT["External integrations"]
        API --> DB["PostgreSQL OR any other DB"]
    ```
    
    This is a logical architecture, not a requirement that each agent be a separate deployed service. The Orchestrator Agent is the coordinating decision-making component; LangGraph runs its workflow and manages transitions and state. Specialist agents may execute concurrently or sequentially depending on their dependencies.
    
- Technology Stack and Decision Status
    
    # 3. Technology Stack and Decision Status
    
    | Layer | Technology / choice | Status | Purpose |
    | --- | --- | --- | --- |
    | Backend language | Python | Confirmed | Primary language for backend and agent logic |
    | Backend API | FastAPI | Confirmed | API endpoints and request handling |
    | Orchestration | LangGraph | Confirmed | Stateful multi-agent workflow and execution control |
    | Agent components | LangChain where useful | Confirmed | Model integrations, tools, and structured outputs where they add value |
    | Data validation | Pydantic | Confirmed | Typed requests, agent outputs, and provider responses |
    | Primary database | PostgreSQL 
    supabase
    mySQL | Not Confirmed | Users, trips, itineraries, preferences, and search records |
    | External integrations | Nuitee | Open by provider | Transport, maps, places, and accommodation |
    | LLM provider and model | To be decided | Open | Powers agent reasoning and tool calling |
    | Frontend | To be decided | Open | Chat, trip management, and itinerary visualization |
    | Deployment | To be decided | Open | Hosting, secrets, monitoring, and CI/CD |
    | ~~Cache~~ | ~~Redis or equivalent~~ | ~~Open / optional~~ | ~~Short-lived search caching and request coordination~~ |
    | ~~Tool interoperability~~ | ~~MCP~~ | ~~Open / optional~~ | ~~Standardized tool access if multiple compatible clients need it~~ |
- Central Orchestrator Design
    
    # 4. Central Orchestrator Design
    
    ## 4.1 Responsibilities
    
    1. Receive a trip-planning request.
    2. Extract and validate trip requirements.
    3. Identify missing essential information and ask the user.
    4. Maintain shared trip state.
    5. Select agents and execution order.
    6. Coordinate concurrent work where possible.
    7. Reconcile transport, itinerary, and hotel results, then validate overall trip-budget constraints.
    8. Enforce cross-agent constraints.
    9. Trigger targeted revisions when constraints are violated.
    10. Return a validated trip plan.
    
    ## 4.2 Initial workflow
    
    ```mermaid
    flowchart TD
        A["Receive trip request"] --> B["Orchestrator Agent: extract and validate requirements"]
        B --> C{"Essential details missing?"}
        C -- Yes --> D["Ask user for clarification"]
        D --> B
        C -- No --> E["Travel Agent"]
        E --> F["Search and compare flights through Nuitee"]
        F --> G["Store transport options in shared trip state"]
        G --> H["Orchestrator Agent coordinates specialist work"]
        H --> I["Itinerary Agent: research experiences through Nuitee"]
        H --> J["Hotel Agent: search and compare hotels through Nuitee"]
        I --> K["Orchestrator Agent reconciles complete trip"]
        J --> K
        K --> L{"Constraints valid?"}
        L -- No --> M["Orchestrator requests targeted revision from relevant agent"]
        M --> K
        L -- Yes --> N["Return trip plan"]
    ```
    
    This is conceptual. The exact execution order and parallelism will be finalized after the Itinerary Agent and Hotel Agent are specified.
    
    ## 4.3 Shared trip state
    
    The orchestrator should maintain a typed representation of the trip rather than relying on conversation history as its sole source of truth.
    
    Expected fields include trip requirements, origin and destination, travel dates and date flexibility, traveller details, currency and total budget, preferences and hard constraints, transport options, selected transport, provisional itinerary, accommodation candidates, cost estimates, agent execution status, validation issues, source references, retrieval timestamps, and user decisions.
    
    Preliminary state sketch:
    
    ```python
    from typing import Any, Literal, TypedDict
    
    class TripState(TypedDict, total=False):
        trip_id: str
        user_request: str
        origin: dict[str, Any]
        destination: dict[str, Any]
        date_constraints: dict[str, Any]
        traveller_details: dict[str, Any]
        budget: dict[str, Any]
        preferences: dict[str, Any]
        transport_options: list[dict[str, Any]]
        selected_transport_id: str | None
        itinerary: dict[str, Any]
        accommodation_options: list[dict[str, Any]]
        cost_breakdown: dict[str, Any]
        agent_status: dict[str, str]
        validation_issues: list[dict[str, Any]]
        plan_status: Literal[
            "collecting_requirements", "researching", "provisional",
            "awaiting_user_choice", "validating", "ready", "failed"
        ]
    ```
    
    This is illustrative, not a finalized production schema. Detailed Pydantic models, state reducers, persistence rules, and database relationships will be defined during implementation planning.
    
    ## 4.4 Constraint reconciliation
    
    The orchestrator must validate the complete trip rather than assuming each agent's individual result is sufficient.
    
    Examples:
    
    - Hotel check-in must be compatible with arrival time.
    - An attraction visit must fit within available time and opening hours.
    - Travel between attractions must be geographically and temporally feasible.
    - Combined trip cost must respect the user's budget or explicitly identify an overrun.
    - Selected transport must be consistent with itinerary departure and arrival locations.
    - Changing transport must trigger recalculation of affected itinerary segments.
    
    Application code should perform mechanical validations. The LLM can interpret results and propose revisions, but it must not be the sole authority for declaring a plan feasible.
    
- Travel Agent
    
    # 5. Travel Agent
    
    ## 5.1 Purpose and scope
    
    The Travel Agent discovers, compares, and ranks transport options. 
    
    - 5.2 Responsibilities
        1. Accept validated travel requirements from the orchestrator.
        2. Resolve ambiguous origins and destinations.
        3. Identify applicable transport providers.
        4. Query independent providers concurrently when appropriate.
        5. Normalize results into a common schema.
        6. Calculate journey durations and comparable costs.
        7. Deduplicate journeys where reliable identification is possible.
        8. Filter options that violate hard constraints.
        9. Rank feasible options according to user preferences.
        10. Return structured results and supporting metadata.
        11. Identify missing data, unsupported routes, and provider failures.
        12. Supply verified outbound booking links when available.
    - 5.3 Search inputs
        
        
        | Field | Description |
        | --- | --- |
        | Origin | City, station, airport, or supported geographic identifier |
        | Destination | City, station, airport, or supported geographic identifier |
        | Departure date | Required or inferred from the user's request |
        | Return date | Optional for one-way trips |
        | Trip type | One-way, return, or potentially multi-city |
        | Travellers | Passenger counts and applicable categories |
        | Cabin/class | Optional transport-class preference |
        | Budget | Total budget, transport budget, or maximum fare |
        | Currency | Currency for displaying comparable prices |
        | Constraints | Arrival deadlines, maximum duration, transfers, accessibility needs |
        | Preferences | Cheapest, fastest, fewest transfers, comfort, or other priorities |
        | Date flexibility | Exact dates, flexible dates, or a date window |
    
    ## 5.4 Search architecture and provider adapters
    
    The Travel Agent should use a provider adapter layer rather than embedding provider-specific request and response formats in the agent.
    
    ```mermaid
    flowchart TD
        A["Travel Agent"] --> B["Transport Search Service"]
        B --> C["Flight Search - Nuitee"]
        B --> D["Train Search - provider TBD"]
        B --> E["Bus Search - provider TBD"]
        C --> F["Nuitee flight adapter"]
        D --> G["Rail provider adapter"]
        E --> H["Bus provider adapter"]
        F --> I["Provider API responses"]
        G --> I
        H --> I
        I --> J["Result normalizer"]
        J --> K["Comparison and ranking"]
        K --> L["Structured results"]
    ```
    
    The agent's reasoning logic should not need to know each provider's API schema.
    
    Illustrative internal interface:
    
    ```python
    from typing import Protocol
    
    class TransportProvider(Protocol):
        async def search(self, request):
            """Return normalized transport options."""
            ...
    ```
    
    A production interface should also define provider capabilities, supported search modes, error handling, pagination, cancellation, and result metadata.
    
    Proposed module structure:
    
    ```
    travel_agent/
    ├── agent.py
    ├── tools.py
    ├── schemas.py
    ├── services/
    │   ├── search.py
    │   ├── flights.py
    │   ├── trains.py
    │   └── buses.py
    ├── providers/
    │   ├── base.py
    │   ├── flight_nuitee.py
    │   ├── rail_provider.py
    │   └── bus_provider.py
    ├── calculations/
    │   ├── duration.py
    │   ├── fares.py
    │   ├── currency.py
    │   └── comparison.py
    └── validation/
        ├── schedule.py
        └── results.py
    ```
    
    ## 5.5 Selected travel search provider and remaining integrations
    
    **Nuitee is the selected provider for searching flights, hotels, and experiences.** 
    
    - API Endpoints for Flights
    
    ## 5.6 MCP integration decision
    
    The initial recommendation is to implement provider integrations as ordinary Python services and expose selected functions as LangGraph tools. MCP is optional and is not required to call external transport APIs.
    
    **Initial approach: direct Python tools**
    
    ```mermaid
    flowchart TD
        A["LangGraph Travel Agent"] --> B["Python tool layer"]
        B --> C["Provider adapters"]
        C --> D["External travel APIs"]
    ```
    
    ## 5.7 Deterministic calculation tools
    
    Numerical operations should be ordinary application functions, not entrusted to LLM arithmetic.
    
    Expected functions:
    
    - Journey-duration calculation.
    - Total passenger-fare calculation.
    - Currency conversion using a specified exchange-rate source.
    - Transport-option comparison and ranking.
    
    ## 5.8 Normalized transport data model
    
    Preliminary Pydantic model:
    
    ```python
    from datetime import datetime
    from decimal import Decimal
    from pydantic import BaseModel, HttpUrl
    
    class TransportOption(BaseModel):
        option_id: str
        mode: str
        origin_name: str
        destination_name: str
        departure_time: datetime
        arrival_time: datetime
        duration_minutes: int
        price: Decimal
        currency: str
        transfers: int
        provider_name: str
        booking_url: HttpUrl | None = None
        retrieved_at: datetime
        baggage_summary: str | None = None
    ```
    
    ## 5.10 Ranking algorithm
    
    The initial implementation should use a configurable deterministic ranking function:
    
    **S = w_c C + w_t T + w_x X + w_p P**
    
    Where:
    
    - C = normalized cost score.
    - T = normalized duration score.
    - X = normalized transfer/convenience score.
    - P = preference-fit score.
    - The weights sum to 1, and higher scores indicate more desirable options.
    
    - 5.11 Flexible-date search
        
        Flexible-date search is a **planned capability to evaluate**.
        
        Example request: “I want to travel from London to Rome for five days sometime in November. Find the cheapest dates.”
        
        The system may search multiple departure and return-date combinations, compare their costs, and return suitable options.
        
        Implementation considerations:
        
        - Represent the date window and trip duration explicitly.
        - Limit the number of date combinations per request.
        - Use provider-supported flexible-date features where available.
        - Otherwise generate a bounded set of individual search requests.
        - Apply concurrency limits and provider rate limits.
        - Cache results only as permitted by provider terms.
        - Track retrieval timestamps and refresh stale prices when needed.
        - Compare equivalent trip durations and passenger configurations.
        - Return the actual dates associated with each recommendation.
        - Clearly indicate date combinations that could not be checked.
        
        Flexible-date search may follow the initial exact-date implementation.
        
    
    # 6. Travel Agent–Orchestrator Interaction
    
    ## 6.1 Proposed sequence
    
    1. The orchestrator validates the trip request.
    2. It sends the Travel Agent origin, destination, dates, traveller details, currency, budget constraints, and preferences.
    3. The Travel Agent searches applicable providers.
    4. It normalizes and ranks results.
    5. It returns structured options, source references, retrieval timestamps, and search limitations.
    6. The orchestrator passes relevant transport information to other agents.
    7. A provisional itinerary and cost estimate are created.
    8. The user chooses a transport option.
    9. The orchestrator updates shared state and validates itinerary and budget constraints.
    10. If the choice makes part of the plan infeasible, affected components are recalculated.
    
    ## 6.2 Provisional and validated itinerary states
    
    - **Provisional itinerary:** built using a promising transport option or a clearly identified arrival-time assumption.
    - **Validated itinerary:** updated after the user chooses an option and relevant schedule, location, and budget constraints have been checked.
    
    This allows itinerary research to proceed while the user compares transport options without treating an unselected journey as final.
    
    ## 6.3 Targeted recalculation
    
    Changing transport may affect first-day activities, hotel check-in, ground transfers, meal planning, total transport cost, and time available at the destination.
    
    The orchestrator should identify affected dependencies and request targeted revisions rather than regenerating the entire itinerary unnecessarily.
    
- Itinerary Agent
    
    # 7. Itinerary Agent
    
    ## 7.1 Purpose and scope
    
    The Itinerary Agent researches destination activities and experiences, then turns suitable options into a practical day-by-day schedule. 
    
    ## 7.2 Responsibilities
    
    1. Receive destination, trip dates, traveller profile, interests, constraints, and transport context from the Orchestrator Agent.
    2. Discover attractions, tours, experiences, and activities through Nuitee where supported.
    3. Use additional places, maps, routing, or opening-hours sources only after those integrations are selected and documented.
    4. Normalize results into internal Pydantic models and retain source references and retrieval timestamps.
    5. Filter activities by user interests, age/accessibility needs, operating dates, location, duration, and price.
    6. Group geographically nearby activities to reduce unnecessary travel.
    7. Create a provisional day-by-day itinerary with realistic time blocks, travel buffers, meal breaks, and rest periods.
    8. Identify missing or uncertain details, including opening hours, ticket availability, duration, and travel time.
    9. Return structured activities, schedule proposals, estimated costs, and validation warnings to the orchestrator.
    10. Revise only affected days or activities when transport, hotel location, dates, budget, or user preferences change.
    
    If hotel or transport choices are not final, the agent should label the schedule provisional rather than silently assuming they are confirmed.
    
    ## 7.4 Discovery and itinerary workflow
    
    ```mermaid
    flowchart TD
        A["Orchestrator sends destination and trip context"] --> B["Validate required inputs"]
        B --> C["Discover experiences through Nuitee"]
        C --> D["Normalize results and retain source metadata"]
        D --> E["Filter by interests, dates, cost, and constraints"]
        E --> F["Group activities by area and estimated duration"]
        F --> G["Build provisional day-by-day schedule"]
        G --> H["Check time windows, travel buffers, and opening-hour evidence"]
        H --> I["Return itinerary, cost estimates, and uncertainty flags"]
        I --> J["Orchestrator reconciles transport, hotel, and total budget"]
        J --> K{"Relevant constraints changed?"}
        K -- Yes --> L["Revise affected days or activities"]
        L --> I
        K -- No --> M["Present validated or explicitly provisional plan"]
    ```
    
    The itinerary may be drafted in parallel with hotel discovery and before the user selects transport. Once transport and accommodation choices are known, the orchestrator should request targeted updates to arrival/departure days and location-sensitive activities.
    
    ## 7.5 Output contract and validation
    
    The Itinerary Agent should return structured data rather than only prose. Each activity should include, when available:
    
    - Stable internal ID and provider/source ID.
    - Name, category, concise description, and source URL.
    - Address or geographic coordinates.
    - Suggested date, start/end time, duration, and time zone.
    - Opening-hours evidence and date-specific availability status.
    - Price, currency, price basis (per person/group), and whether it is verified or estimated.
    - Booking or ticket URL, only when supplied or verified.
    - Estimated travel time/distance from the preceding activity and hotel, with source and timestamp.
    - Accessibility/age constraints and other relevant requirements.
    - Retrieval timestamp, confidence/uncertainty flags, and validation warnings.
    
    Application code should check schedule overlap, travel buffers, local time zones, trip boundaries, duplicate activities, and known opening-hour conflicts. If opening hours or availability are unknown, mark them unknown; do not invent confirmation. The Orchestrator Agent owns final cross-agent reconciliation and total trip-budget validation.
    
    ## 7.6 API documentation template — Nuitee experiences and supporting place/routing APIs
    
    API Documentation Missing
    
    ## 7.7 Interaction with the Orchestrator Agent
    
    1. The orchestrator sends the validated trip context and identifies which fields are confirmed versus provisional.
    2. The Itinerary Agent searches for experiences and returns normalized candidates, costs, source metadata, and uncertainties.
    3. The orchestrator combines these results with transport and hotel candidates, checks the full-trip budget, and validates timing and location constraints.
    4. If a chosen flight changes arrival time, the hotel location changes, or the user changes preferences, the orchestrator sends a focused revision request to the Itinerary Agent.
    5. The agent returns updated affected days and identifies which previous assumptions are no longer valid.
    6. The orchestrator decides whether the overall plan is ready to present or needs further clarification.
    
    The Itinerary Agent must not assume that its preferred activity schedule overrides confirmed transport times, user hard constraints, or the orchestrator's overall budget validation.
    
- Hotel Agent
    
    # 8. Hotel Agent
    
    ## 8.1 Purpose and scope
    
    The Hotel Agent discovers, filters, compares, and recommends accommodation options. 
    
    ## 8.2 Responsibilities
    
    1. Receive destination, stay dates, guest/room requirements, budget constraints, and preferences from the orchestrator.
    2. Search Nuitee for accommodation options where supported.
    3. Normalize hotel properties, room/rate options, amenities, location, policies, price, and source identifiers.
    4. Filter out options that violate hard requirements such as occupancy, dates, accessibility needs, or maximum accommodation budget.
    5. Compare total stay cost, location, amenities, cancellation conditions, guest suitability, and other requested factors.
    6. Distinguish property-level details from room/rate-specific details.
    7. Identify missing, estimated, stale, or unverified prices and availability.
    8. Return ranked accommodation candidates with source references and verified links where available.
    9. Re-run or refresh searches when dates, guest counts, destination, budget, or user preferences change.
    10. Report limitations and provider failures rather than inventing inventory or policies.
    
    The agent recommends options only. The initial application does not complete hotel bookings or payments.
    
    ## 8.4 Hotel search and comparison workflow
    
    ```mermaid
    flowchart TD
        A["Orchestrator sends stay requirements"] --> B["Validate destination, dates, and occupancy"]
        B --> C["Search hotels through Nuitee"]
        C --> D["Normalize properties and room/rate options"]
        D --> E["Check price basis, taxes, policies, and freshness"]
        E --> F["Filter hard constraints"]
        F --> G["Compare location, amenities, rate, and cancellation terms"]
        G --> H["Return ranked hotel candidates and source metadata"]
        H --> I["Orchestrator combines hotel, transport, and activity costs"]
        I --> J{"Budget or schedule conflict?"}
        J -- Yes --> K["Orchestrator requests targeted alternatives"]
        K --> C
        J -- No --> L["Present recommendations with uncertainty clearly labelled"]
    ```
    
    Hotel search can run in parallel with itinerary research once destination, dates, and minimum guest details are known. When the itinerary becomes available, the orchestrator may ask the Hotel Agent to re-rank options by location or travel convenience. Do not serialize these tasks unnecessarily if they have enough independent input to start.
    
    ## 8.5 Output contract and validation
    
    For each property and relevant room/rate option, return fields when available:
    
    - Internal option ID, provider property ID, and rate/room identifier.
    - Property name, address, coordinates, category/class, and source URL.
    - Room type, occupancy, included amenities, and meal plan.
    - Check-in/check-out dates and number of nights.
    - Total stay price, currency, taxes/fees, price basis, and any excluded charges.
    - Cancellation/refund policy, payment terms, and deposit details.
    - Availability status and last-verified/retrieval timestamp.
    - Booking or property deep link supplied by the provider.
    - Distance or estimated travel time to relevant itinerary locations, including the source if calculated externally.
    - Required guest information, age restrictions, accessibility information, and relevant caveats.
    - Provider warnings, missing fields, and estimated-versus-confirmed indicators.
    
    The implementation must not compare a nightly price with a total-stay price as though they were equivalent. Preserve currency, occupancy, room count, number of nights, taxes/fees, meal plan, and cancellation conditions when comparing rates. Revalidate prices and availability when supported before presenting them as current. The orchestrator performs final total-trip budget reconciliation.
    
    ## 8.7 Interaction with the Orchestrator Agent
    
    1. The orchestrator supplies destination, stay dates, occupancy, budget constraints, preferences, and any confirmed transport context.
    2. The Hotel Agent returns normalized property/rate options, total-stay cost details, policies, source references, and uncertainty flags.
    3. The orchestrator compares the accommodation cost with transport and activity estimates and checks the overall trip budget.
    4. If the total budget is exceeded, the orchestrator may ask the Hotel Agent for cheaper properties, alternate areas, or more flexible cancellation/rate options, while preserving hard requirements.
    5. If the user changes dates or occupancy, the orchestrator requests a new search because prices and availability may no longer apply.
    6. If itinerary locations become known, the orchestrator may request re-ranking by location or travel convenience.
    7. The orchestrator returns the final recommendation and clearly identifies estimates, missing information, and unconfirmed availability.
    
    The Hotel Agent must not silently relax hard constraints or claim that a room is booked. If no suitable result exists, return that outcome and the constraints that prevented a match.
    
- Initial Backend Structure
    
    # 9. Initial Backend Structure
    
    ```
    backend/
    ├── app/
    │   ├── main.py
    │   ├── api/
    │   ├── core/
    │   │   ├── config.py
    │   │   ├── security.py
    │   │   └── logging.py
    │   ├── orchestrator/
    │   │   ├── graph.py
    │   │   ├── state.py
    │   │   └── nodes.py
    │   ├── agents/
    │   │   ├── travel/
    │   │   ├── itinerary/
    │   │   └── hotel/
    │   ├── integrations/
    │   │   ├── transport/
    │   │   ├── maps/
    │   │   └── accommodation/
    │   ├── models/
    │   ├── schemas/
    │   ├── services/
    │   └── repositories/
    ├── tests/
    ├── migrations/
    ├── pyproject.toml
    └── README.md
    ```
    
    A modular monolith is a reasonable initial deployment approach. The agents do not need separate microservices unless scaling, ownership, or operational requirements later justify it.