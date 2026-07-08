from dataclasses import dataclass, field
from typing import Optional
from .register import RegisterProfile
from .mechanism import MechanismShape
from .function import HXRMXSFunction, Phase


@dataclass
class PedagogyBlock:
    lineage: str
    phase: Optional[Phase]
    function_id: Optional[HXRMXSFunction]
    student_state: str
    behavior_tags: list[str]
    mechanism_shape: MechanismShape
    teaching_actions: list[str]
    register: Optional[RegisterProfile]
    traps_avoided: list[str]
    intent: str
    approach: str
    impact_predicted: str
    impact_confidence: str
    impact_update: str
    accumulated_insight: str
    my_thoughts: str


@dataclass
class TurnRecord:
    episode_id: str
    turn_index: int
    lineage: str
    user_text: str
    assistant_visible_text: str
    pedagogy: PedagogyBlock


@dataclass
class TransitionRecord:
    episode_id: str
    from_turn: int
    to_turn: int
    from_state: str
    move_function: Optional[str]
    mechanism_shape: Optional[str]
    teaching_actions: list[str]
    register: Optional[tuple]
    predicted_impact: str
    observed_user_text: str
    to_state: str
    impact_update: str
    lineage: str
    prediction_match: str  # "true", "partial", "false", "unknown"


@dataclass
class EpisodeArc:
    episode_id: str
    lineage: str
    state_sequence: list[str]
    function_sequence: list[str]
    mechanism_sequence: list[str]
    action_sequence: list[list[str]]
    register_sequence: list[Optional[tuple]]
    predicted_impact_sequence: list[str]
    final_state: str
    arc_length: int
    arc_summary: str
