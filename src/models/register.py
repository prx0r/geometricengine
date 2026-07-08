from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Intensity(Enum):
    PR_01 = 1  # gentle_invitation
    PR_02 = 2  # steady_focus
    PR_03 = 3  # active_friction
    PR_04 = 4  # crushing_weight


class Intimacy(Enum):
    IN_01 = 1  # clinical_detached
    IN_02 = 2  # peer_collaborative
    IN_03 = 3  # authoritative_distant
    IN_04 = 4  # compassionate_intense


class Attunement(Enum):
    AT_01 = 1  # low_attunement
    AT_02 = 2  # medium_attunement
    AT_03 = 3  # high_attunement


class Style(Enum):
    LS_01 = 1  # minimalist_cut
    LS_02 = 2  # analytic_chain
    LS_03 = 3  # metaphorical_scaffold
    LS_04 = 4  # diagnostic_technical
    LS_05 = 5  # satirical_grotesque
    LS_06 = 6  # recursive_irony


class Depth(Enum):
    PD_01 = 1  # conceptual_abstract
    PD_02 = 2  # somatic_immediate
    PD_03 = 3  # emotional_dynamic
    PD_04 = 4  # nondual_witness


class MetaMode(Enum):
    MM_01 = 1  # direct_intervention
    MM_02 = 2  # explicit_meta


@dataclass
class RegisterProfile:
    intensity: Intensity
    intimacy: Intimacy
    attunement: Attunement
    style: Style
    depth: Depth
    meta_mode: MetaMode

    @classmethod
    def from_strings(cls, pr: str, inn: str, at: str, ls: str, pd: str, mm: str):
        return cls(
            intensity=Intensity[pr.replace("-", "_")],
            intimacy=Intimacy[inn.replace("-", "_")],
            attunement=Attunement[at.replace("-", "_")],
            style=Style[ls.replace("-", "_")],
            depth=Depth[pd.replace("-", "_")],
            meta_mode=MetaMode[mm.replace("-", "_")],
        )

    def to_tuple(self) -> tuple:
        return (self.intensity.value, self.intimacy.value,
                self.attunement.value, self.style.value,
                self.depth.value, self.meta_mode.value)
