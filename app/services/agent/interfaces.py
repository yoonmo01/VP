# app/services/agent/interfaces.py
from typing import Protocol, Tuple, Dict, Any
from uuid import UUID


class IGuidelineRepo(Protocol):

    def pick_preventive(self) -> Tuple[str, str]:
        ...

    def pick_attack(self) -> Tuple[str, str]:
        ...


class IAgent(Protocol):

    def decide_kind(self, case_id: UUID) -> str:
        ...  # 'P' or 'A'

    def personalize(self, case_id: UUID, offender_id: int, victim_id: int,
                    run_no: int) -> Dict[str, Any]:
        ...
