"""Technician shift scheduling, FAA A&P qualifications, and duty rosters."""
from typing import TypedDict
from uuid import UUID
from datetime import datetime, timezone

class TechnicianSchedule(TypedDict):
    technician_id: str
    name: str
    shift_name: str  # morning, afternoon, night
    shift_hours: str
    qualifications: list[str]
    is_on_duty: bool

# Seed schedules matching the standard demo technicians
DEFAULT_ROSTER: list[TechnicianSchedule] = [
    {
        "technician_id": "00000000-0000-0000-0000-000000000003",
        "name": "Sarah Miller (Lead A&P)",
        "shift_name": "morning",
        "shift_hours": "06:00 - 14:00 UTC",
        "qualifications": ["FAA_AP_AIRFRAME_POWERPLANT", "BORESCOPE_LEVEL_2", "TURBINE_HOT_SECTION"],
        "is_on_duty": True
    },
    {
        "technician_id": "00000000-0000-0000-0000-000000000004",
        "name": "James Chen (Senior Tech)",
        "shift_name": "afternoon",
        "shift_hours": "14:00 - 22:00 UTC",
        "qualifications": ["FAA_AP_AIRFRAME_POWERPLANT", "VIBRATION_DIAGNOSTICS"],
        "is_on_duty": True
    },
    {
        "technician_id": "00000000-0000-0000-0000-000000000005",
        "name": "Elena Rostova (Avionics Tech)",
        "shift_name": "night",
        "shift_hours": "22:00 - 06:00 UTC",
        "qualifications": ["AVIONICS_ELECTRICAL", "ENGINE_INSTRUMENTATION"],
        "is_on_duty": False
    }
]

_TENANT_ROSTERS: dict[str, list[TechnicianSchedule]] = {}


def get_tenant_roster(tenant_id: UUID) -> list[TechnicianSchedule]:
    """Returns the shift roster for technicians in a tenant organization."""
    t_key = str(tenant_id)
    if t_key not in _TENANT_ROSTERS:
        _TENANT_ROSTERS[t_key] = [dict(r) for r in DEFAULT_ROSTER]
    return _TENANT_ROSTERS[t_key]


def update_technician_duty(tenant_id: UUID, technician_id: str, is_on_duty: bool) -> TechnicianSchedule | None:
    """Updates whether a technician is currently on duty."""
    roster = get_tenant_roster(tenant_id)
    for tech in roster:
        if tech["technician_id"] == technician_id:
            tech["is_on_duty"] = is_on_duty
            return tech
    return None


def get_available_technicians_for_task(tenant_id: UUID, task_code: str) -> list[TechnicianSchedule]:
    """Finds currently on-duty technicians qualified for a given AMM task code."""
    roster = get_tenant_roster(tenant_id)

    task_qualification_map = {
        "AMM 72-31-00": "BORESCOPE_LEVEL_2",
        "AMM 72-51-00": "TURBINE_HOT_SECTION",
        "AMM 72-00-05": "VIBRATION_DIAGNOSTICS",
    }
    required_qual = task_qualification_map.get(task_code, "FAA_AP_AIRFRAME_POWERPLANT")

    qualified = [
        t for t in roster
        if t["is_on_duty"] and required_qual in t["qualifications"]
    ]
    return qualified
