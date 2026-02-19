"""
LangGraph agent for roster reallocation.

Workflow:
  1. assess_impact      → Identify affected slots
  2. generate_options   → Propose candidate reallocations
  3. validate           → Check constraints
  4. finalize           → Commit roster version
"""
from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage
import operator


# ── State definition ──────────────────────────────────────────────────────────

class ReallocationState(TypedDict):
    """State passed through the workflow."""
    # Input
    current_roster: dict
    disruption_event: dict
    students: list[dict]
    instructors: list[dict]
    aircraft: list[dict]
    simulators: list[dict]
    
    # Workflow state
    affected_slots: list[dict]
    candidate_reallocations: list[dict]
    validated_roster: dict
    
    # Output
    final_roster: dict
    diff: dict
    churn_rate: float
    messages: Annotated[Sequence[BaseMessage], operator.add]


# ── Tool functions (agents call these) ───────────────────────────────────────

def fetch_current_roster_tool(week_start: str, db) -> dict:
    """Tool: Fetch the latest roster version from DB."""
    from app.models import RosterVersion
    from datetime import date
    
    latest = (
        db.query(RosterVersion)
        .filter(RosterVersion.week_start == date.fromisoformat(week_start))
        .order_by(RosterVersion.version.desc())
        .first()
    )
    
    if latest:
        return latest.roster_json
    return None


def apply_disruption_tool(roster: dict, event: dict) -> list[dict]:
    """Tool: Identify which slots are affected by disruption."""
    from app.reallocation.engine import DisruptionEvent, identify_affected_slots
    
    disruption = DisruptionEvent(
        event_type=event["event_type"],
        entity_id=event.get("entity_id"),
        from_time=event.get("from_time"),
        to_time=event.get("to_time"),
        metadata=event.get("metadata", {})
    )
    
    return identify_affected_slots(roster, disruption)


def validate_roster_constraints_tool(roster: dict) -> dict:
    """Tool: Check if roster violates any hard constraints."""
    violations = []
    seen = {}
    
    for day in roster["roster"]:
        for slot in day["slots"]:
            # Check double booking
            for entity in [slot["student_id"], slot["instructor_id"], slot["resource_id"]]:
                key = (entity, slot["date"], slot["start"])
                if key in seen:
                    violations.append({
                        "type": "DOUBLE_BOOKING",
                        "entity": entity,
                        "slot": slot["slot_id"],
                        "conflicts_with": seen[key]
                    })
                else:
                    seen[key] = slot["slot_id"]
    
    return {
        "valid": len(violations) == 0,
        "violations": violations
    }


def commit_roster_version_tool(roster: dict, diff: dict, correlation_id: str, db) -> int:
    """Tool: Save roster version to DB."""
    from app.models import RosterVersion
    from datetime import date
    
    week_start = date.fromisoformat(roster["week_start"])
    
    # Get next version number
    latest = (
        db.query(RosterVersion)
        .filter(RosterVersion.week_start == week_start)
        .order_by(RosterVersion.version.desc())
        .first()
    )
    new_version = (latest.version + 1) if latest else 1
    
    churn_rate = (diff["total_changes"] / max(1, sum(len(d["slots"]) for d in roster["roster"]))) * 100
    
    version_entry = RosterVersion(
        version=new_version,
        week_start=week_start,
        correlation_id=correlation_id,
        roster_json=roster,
        diff_json=diff,
        change_summary={"total_changes": diff["total_changes"]},
        churn_rate=churn_rate,
        coverage=0.0
    )
    db.add(version_entry)
    db.commit()
    
    return new_version


# ── Workflow nodes ────────────────────────────────────────────────────────────

def assess_impact_node(state: ReallocationState) -> ReallocationState:
    """Step 1: Identify affected slots."""
    from app.reallocation.engine import DisruptionEvent, identify_affected_slots
    
    event_dict = state["disruption_event"]
    disruption = DisruptionEvent(
        event_type=event_dict["event_type"],
        entity_id=event_dict.get("entity_id"),
        from_time=event_dict.get("from_time"),
        to_time=event_dict.get("to_time"),
        metadata=event_dict.get("metadata", {})
    )
    
    affected = identify_affected_slots(state["current_roster"], disruption)
    
    state["affected_slots"] = affected
    return state


def generate_options_node(state: ReallocationState) -> ReallocationState:
    """Step 2: Generate candidate reallocations."""
    from app.reallocation.engine import reallocate_roster, DisruptionEvent
    from copy import deepcopy
    
    event_dict = state["disruption_event"]
    disruption = DisruptionEvent(
        event_type=event_dict["event_type"],
        entity_id=event_dict.get("entity_id"),
        from_time=event_dict.get("from_time"),
        to_time=event_dict.get("to_time"),
        metadata=event_dict.get("metadata", {})
    )
    
    # Use reallocation engine to generate new roster
    result = reallocate_roster(
        current_roster=state["current_roster"],
        event=disruption,
        students=state["students"],
        instructors=state["instructors"],
        aircraft=state["aircraft"],
        simulators=state["simulators"],
        time_slots=[],  # Not needed for reallocation
    )
    
    state["candidate_reallocations"] = [result["new_roster"]]
    state["diff"] = result["diff"]
    state["churn_rate"] = result["churn_rate"]
    
    return state


def validate_node(state: ReallocationState) -> ReallocationState:
    """Step 3: Validate constraints."""
    # Pick best candidate (for now just the first one)
    candidate = state["candidate_reallocations"][0]
    
    validation = validate_roster_constraints_tool(candidate)
    
    if validation["valid"]:
        state["validated_roster"] = candidate
    else:
        # Fallback: use current roster if validation fails
        state["validated_roster"] = state["current_roster"]
        state["diff"] = {"added": [], "removed": [], "modified": [], "total_changes": 0}
        state["churn_rate"] = 0.0
    
    return state


def finalize_node(state: ReallocationState) -> ReallocationState:
    """Step 4: Finalize and prepare output."""
    state["final_roster"] = state["validated_roster"]
    return state


# ── Build graph ───────────────────────────────────────────────────────────────

def build_reallocation_graph():
    """Build the LangGraph workflow."""
    workflow = StateGraph(ReallocationState)
    
    # Add nodes
    workflow.add_node("assess_impact", assess_impact_node)
    workflow.add_node("generate_options", generate_options_node)
    workflow.add_node("validate", validate_node)
    workflow.add_node("finalize", finalize_node)
    
    # Define edges
    workflow.set_entry_point("assess_impact")
    workflow.add_edge("assess_impact", "generate_options")
    workflow.add_edge("generate_options", "validate")
    workflow.add_edge("validate", "finalize")
    workflow.add_edge("finalize", END)
    
    return workflow.compile()


# ── Main agent runner ─────────────────────────────────────────────────────────

def run_reallocation_agent(
    current_roster: dict,
    disruption_event: dict,
    students: list[dict],
    instructors: list[dict],
    aircraft: list[dict],
    simulators: list[dict],
) -> dict:
    """
    Run the LangGraph reallocation workflow.
    
    Returns: {
        "final_roster": {...},
        "diff": {...},
        "churn_rate": float,
        "affected_slots": [...]
    }
    """
    graph = build_reallocation_graph()
    
    initial_state = {
        "current_roster": current_roster,
        "disruption_event": disruption_event,
        "students": students,
        "instructors": instructors,
        "aircraft": aircraft,
        "simulators": simulators,
        "affected_slots": [],
        "candidate_reallocations": [],
        "validated_roster": {},
        "final_roster": {},
        "diff": {},
        "churn_rate": 0.0,
        "messages": []
    }
    
    # Run the graph
    result = graph.invoke(initial_state)
    
    return {
        "final_roster": result["final_roster"],
        "diff": result["diff"],
        "churn_rate": result["churn_rate"],
        "affected_slots": result["affected_slots"],
    }