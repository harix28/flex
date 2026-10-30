"""Work order maintenance planning & readiness evaluation service."""
from uuid import UUID
from sentinel.planning.inventory import find_parts_for_tasks
from sentinel.planning.shifts import get_available_technicians_for_task, get_tenant_roster
from sentinel.work_orders import service as work_orders_service


def evaluate_work_order_readiness(session, tenant_id: UUID, work_order_id: UUID) -> dict:
    """Evaluates whether an unblocked work order has available warehouse parts and qualified on-duty staff."""
    wo = work_orders_service.get_work_order(session, tenant_id, work_order_id)
    if not wo:
        raise ValueError("Work order not found")

    tasks = wo.get("tasks", [])
    task_codes = [t.get("code") for t in tasks if t.get("code")]
    if not task_codes:
        # Default fallback tasks if none explicitly listed
        task_codes = ["AMM 72-00-00", "AMM 72-31-00", "AMM 72-00-05"]

    # 1. Parts Availability Check
    parts_requirements = find_parts_for_tasks(tenant_id, task_codes)
    parts_shortage = [p for p in parts_requirements if not p["in_stock"]]

    # 2. Technician Qualification & Shift Check
    assigned_tech_id = wo.get("assigned_technician_id")
    roster = get_tenant_roster(tenant_id)

    assigned_tech = None
    if assigned_tech_id:
        assigned_tech = next((t for t in roster if t["technician_id"] == str(assigned_tech_id)), None)

    # Check overall qualified staff
    on_duty_qualified = []
    for code in task_codes:
        qualified = get_available_technicians_for_task(tenant_id, code)
        for q in qualified:
            if q["technician_id"] not in [x["technician_id"] for x in on_duty_qualified]:
                on_duty_qualified.append(q)

    # 3. Overall Readiness Assessment
    is_ready = True
    blockers = []

    if parts_shortage:
        is_ready = False
        short_names = ", ".join([p["part_number"] for p in parts_shortage])
        blockers.append(f"Warehouse parts shortage: {short_names}")

    if assigned_tech and not assigned_tech["is_on_duty"]:
        blockers.append(f"Assigned technician ({assigned_tech['name']}) is currently off-duty ({assigned_tech['shift_name']} shift)")

    if not assigned_tech and not on_duty_qualified:
        is_ready = False
        blockers.append("No qualified on-duty technicians available for required AMM tasks")

    return {
        "work_order_id": str(work_order_id),
        "status": wo.get("status"),
        "is_planning_ready": is_ready,
        "readiness_summary": "READY_FOR_EXECUTION" if is_ready else "PLANNING_BLOCKED",
        "blockers": blockers,
        "parts_checklist": parts_requirements,
        "assigned_technician": assigned_tech,
        "recommended_on_duty_technicians": on_duty_qualified
    }

