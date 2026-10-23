from typing import Any, Dict, List, Literal, Optional
from typing_extensions import TypedDict


class TripState(TypedDict, total=False):
    """
    Shared trip state schema for LangGraph orchestrator.
    Directly reflects Section 4.3 of the Technical Design Document.
    """
    trip_id: str
    user_request: str
    origin: Dict[str, Any]
    destination: Dict[str, Any]
    date_constraints: Dict[str, Any]
    traveller_details: Dict[str, Any]
    budget: Dict[str, Any]
    preferences: Dict[str, Any]
    
    # Transport outputs from Travel Agent
    transport_options: List[Dict[str, Any]]
    selected_transport_id: Optional[str]
    
    # Itinerary outputs from Itinerary Agent
    itinerary: Dict[str, Any]
    
    # Accommodation outputs from Hotel Agent
    accommodation_options: List[Dict[str, Any]]
    selected_accommodation_id: Optional[str]
    
    # Cost & Reconciliations
    cost_breakdown: Dict[str, Any]
    agent_status: Dict[str, str]
    validation_issues: List[Dict[str, Any]]
    
    # Overall plan status
    plan_status: Literal[
        "collecting_requirements",
        "researching",
        "provisional",
        "awaiting_user_choice",
        "validating",
        "ready",
        "failed"
    ]
