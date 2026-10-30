"""Aircraft engine parts catalog, warehouse bin locations, and inventory levels."""
from typing import TypedDict
from uuid import UUID

class PartItem(TypedDict):
    part_number: str
    name: str
    category: str
    warehouse_bin: str
    stock_qty: int
    min_required: int
    unit_cost_usd: float
    compatible_subsystems: list[str]

# Standard FAA AMM Chapter 72 engine replacement parts
DEFAULT_PARTS: list[PartItem] = [
    {
        "part_number": "AMM-72-31-HPC-SEAL",
        "name": "HPC Rotor Blade Tip Seal Kit (Stages 1-6)",
        "category": "Compressor",
        "warehouse_bin": "Depot A / Bay 3 / Bin 12",
        "stock_qty": 6,
        "min_required": 2,
        "unit_cost_usd": 1450.00,
        "compatible_subsystems": ["HPC", "high_pressure_compressor"]
    },
    {
        "part_number": "AMM-72-51-HPT-THERM",
        "name": "High Pressure Turbine Dual Thermocouple Probe",
        "category": "Turbine / Instrumentation",
        "warehouse_bin": "Depot A / Bay 2 / Bin 5",
        "stock_qty": 4,
        "min_required": 2,
        "unit_cost_usd": 3200.00,
        "compatible_subsystems": ["HPT", "LPT", "turbine"]
    },
    {
        "part_number": "AMM-72-00-OIL-FLTR",
        "name": "3-Micron Dual Oil Scavenge Filter Element",
        "category": "Lubrication",
        "warehouse_bin": "Depot B / Bay 1 / Bin 1",
        "stock_qty": 18,
        "min_required": 5,
        "unit_cost_usd": 280.00,
        "compatible_subsystems": ["lubrication", "oil_system", "general"]
    },
    {
        "part_number": "AMM-72-21-FAN-PIN",
        "name": "Titanium Fan Blade Retention Pin & Lockwire Set",
        "category": "Fan / LPC",
        "warehouse_bin": "Depot A / Bay 4 / Bin 8",
        "stock_qty": 8,
        "min_required": 3,
        "unit_cost_usd": 890.00,
        "compatible_subsystems": ["fan", "LPC"]
    },
    {
        "part_number": "AMM-72-41-NOZZLE-O",
        "name": "Fuel Spray Nozzle O-Ring & Combustion Seal Repair Pack",
        "category": "Combustion",
        "warehouse_bin": "Depot A / Bay 1 / Bin 9",
        "stock_qty": 12,
        "min_required": 4,
        "unit_cost_usd": 640.00,
        "compatible_subsystems": ["combustor", "fuel_nozzle"]
    }
]

# Tenant-scoped inventory: tenant_id -> list[PartItem]
_TENANT_INVENTORY: dict[str, list[PartItem]] = {}


def get_tenant_inventory(tenant_id: UUID) -> list[PartItem]:
    """Returns the warehouse inventory for a tenant, initializing with default catalog if empty."""
    t_key = str(tenant_id)
    if t_key not in _TENANT_INVENTORY:
        _TENANT_INVENTORY[t_key] = [dict(p) for p in DEFAULT_PARTS]
    return _TENANT_INVENTORY[t_key]


def update_part_stock(tenant_id: UUID, part_number: str, new_qty: int) -> PartItem | None:
    """Updates the stock quantity of a part in the warehouse."""
    inventory = get_tenant_inventory(tenant_id)
    for part in inventory:
        if part["part_number"] == part_number:
            part["stock_qty"] = max(0, new_qty)
            return part
    return None


def find_parts_for_tasks(tenant_id: UUID, task_codes: list[str]) -> list[dict]:
    """Maps AMM task codes to required spare parts and checks stock availability."""
    inventory = get_tenant_inventory(tenant_id)
    inv_map = {p["part_number"]: p for p in inventory}

    task_to_part = {
        "AMM 72-31-00": "AMM-72-31-HPC-SEAL",
        "AMM 72-51-00": "AMM-72-51-HPT-THERM",
        "AMM 72-00-02": "AMM-72-00-OIL-FLTR",
        "AMM 72-21-00": "AMM-72-21-FAN-PIN",
        "AMM 72-41-00": "AMM-72-41-NOZZLE-O",
    }

    requirements = []
    for code in task_codes:
        part_num = task_to_part.get(code)
        if part_num and part_num in inv_map:
            p = inv_map[part_num]
            in_stock = p["stock_qty"] > 0
            requirements.append({
                "task_code": code,
                "part_number": p["part_number"],
                "name": p["name"],
                "warehouse_bin": p["warehouse_bin"],
                "available_stock": p["stock_qty"],
                "in_stock": in_stock,
                "status": "AVAILABLE" if in_stock else "SHORTAGE"
            })
    return requirements
