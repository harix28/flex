"""Unit tests for maintenance planning, warehouse inventory, and shift availability."""
from uuid import uuid4
from sentinel.planning import inventory, shifts


def test_warehouse_inventory_and_stock_update():
    tenant_id = uuid4()
    parts = inventory.get_tenant_inventory(tenant_id)
    assert len(parts) >= 5
    hpc_seal = next(p for p in parts if p["part_number"] == "AMM-72-31-HPC-SEAL")
    assert "Depot A" in hpc_seal["warehouse_bin"]
    assert hpc_seal["stock_qty"] > 0

    # Update stock
    updated = inventory.update_part_stock(tenant_id, "AMM-72-31-HPC-SEAL", 15)
    assert updated["stock_qty"] == 15

    # Check task parts mapping
    reqs = inventory.find_parts_for_tasks(tenant_id, ["AMM 72-31-00", "AMM 72-00-02"])
    assert len(reqs) == 2
    assert all(r["status"] == "AVAILABLE" for r in reqs)

    # Force shortage
    inventory.update_part_stock(tenant_id, "AMM-72-31-HPC-SEAL", 0)
    shortage_reqs = inventory.find_parts_for_tasks(tenant_id, ["AMM 72-31-00"])
    assert shortage_reqs[0]["status"] == "SHORTAGE"
    assert shortage_reqs[0]["available_stock"] == 0


def test_technician_shift_roster_and_qualifications():
    tenant_id = uuid4()
    roster = shifts.get_tenant_roster(tenant_id)
    assert len(roster) >= 3

    # On-duty qualified check for borescope
    borescope_techs = shifts.get_available_technicians_for_task(tenant_id, "AMM 72-31-00")
    assert len(borescope_techs) >= 1
    assert any("BORESCOPE_LEVEL_2" in t["qualifications"] for t in borescope_techs)

    # Off-duty technician toggle
    tech_id = roster[0]["technician_id"]
    toggled = shifts.update_technician_duty(tenant_id, tech_id, False)
    assert toggled["is_on_duty"] is False
