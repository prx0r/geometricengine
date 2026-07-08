import json
from collections import Counter, defaultdict
from src.models.pedagogy import TurnRecord, TransitionRecord


class StateClassifier:
    def __init__(self, transitions: list[TransitionRecord]):
        self.state_transitions = defaultdict(list)
        for t in transitions:
            self.state_transitions[t.from_state].append(t.to_state)

    def classify(self, user_text: str) -> str:
        return "unknown"

    def known_states(self) -> list[str]:
        return list(self.state_transitions.keys())

    def likely_next_states(self, state: str) -> list[tuple[str, int]]:
        nexts = self.state_transitions.get(state, [])
        return Counter(nexts).most_common()


class MoveSelector:
    def __init__(self, transitions: list[TransitionRecord]):
        self.state_to_moves = defaultdict(list)
        for t in transitions:
            if t.move_function:
                self.state_to_moves[t.from_state].append({
                    "function": t.move_function,
                    "mechanism": t.mechanism_shape,
                    "actions": t.teaching_actions,
                    "register": t.register,
                    "to_state": t.to_state,
                    "predicted_impact": t.predicted_impact,
                })

    def possible_moves(self, state: str) -> list[dict]:
        return self.state_to_moves.get(state, [])

    def best_move(self, state: str) -> dict | None:
        moves = self.possible_moves(state)
        if not moves:
            return None
        fn_counts = Counter(m["function"] for m in moves)
        best_fn = fn_counts.most_common(1)[0][0]
        best = [m for m in moves if m["function"] == best_fn]
        return best[0]

    def unique_functions(self) -> list[str]:
        fns = set()
        for moves in self.state_to_moves.values():
            for m in moves:
                fns.add(m["function"])
        return sorted(fns)

    def unique_mechanisms(self) -> list[str]:
        mechs = set()
        for moves in self.state_to_moves.values():
            for m in moves:
                if m["mechanism"]:
                    mechs.add(m["mechanism"])
        return sorted(mechs)
