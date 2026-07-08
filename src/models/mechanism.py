from enum import Enum


class MechanismShape(Enum):
    STRUCTURAL_ANALOGY = "structural_analogy"
    COMPARISON_CONTRAST = "comparison_contrast"
    SYSTEM_DYNAMICS = "system_dynamics"
    STRUCTURAL_MAPPING = "structural_mapping"
    CAUSAL_CHAIN = "causal_chain"
    THRESHOLDING = "thresholding"
    CONSTRAINT_COLLAPSE = "constraint_collapse"
    ONTOLOGICAL_SHIFT = "ontological_shift"
    SUBJECT_OBJECT_INVERSION = "subject_object_inversion"
    SOURCE_TRACING = "source_tracing"
    ABSTRACT_TO_CONCRETE = "abstract_to_concrete_check"
    RECURSION_LOOP = "recursion_loop"
    GROUND_REALITY_CHECK = "ground_reality_check"
    HORIZON_EXTRAPOLATION = "horizon_extrapolation"
    NONE = "none"

    @classmethod
    def from_str(cls, s: str):
        normalized = s.strip().lower().replace(" ", "_").replace("-", "_")
        for member in cls:
            if member.value == normalized:
                return member
        return cls.NONE
