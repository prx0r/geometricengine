from enum import Enum


class Phase(Enum):
    UNMAKING = "UNMAKING"
    REMAKING = "REMAKING"
    SELF_MAKING = "SELF-MAKING"
    META = "META"


class HXRMXSFunction(Enum):
    # UNMAKING (UM_01–UM_06)
    UM_01 = "definition_collapse"
    UM_02 = "contradiction_exposure"
    UM_03 = "reductio_extension"
    UM_04 = "ground_reality_check"
    UM_05 = "ego_displacement"
    UM_06 = "constraint_removal"

    # REMAKING (RM_01–RM_05)
    RM_01 = "analogy_scaffolding"
    RM_02 = "causal_chain_mapping"
    RM_03 = "conceptual_distinction"
    RM_04 = "instruction_protocol"
    RM_05 = "frame_upgrade"

    # SELF-MAKING (SM_01–SM_04)
    SM_01 = "direct_seeing"
    SM_02 = "witness_pivot"
    SM_03 = "synthesis_demand"
    SM_04 = "existential_commitment"

    # META (ME_01–ME_03)
    ME_01 = "process_discipline"
    ME_02 = "aporia_validation"
    ME_03 = "method_explanation"

    @classmethod
    def from_str(cls, s: str):
        normalized = s.strip().upper().replace("-", "_").replace(" ", "_")
        for member in cls:
            if member.name == normalized:
                return member
        return None

    @property
    def phase(self) -> Phase:
        prefix = self.name.split("_")[0]
        mapping = {
            "UM": Phase.UNMAKING,
            "RM": Phase.REMAKING,
            "SM": Phase.SELF_MAKING,
            "ME": Phase.META,
        }
        return mapping.get(prefix, Phase.META)
