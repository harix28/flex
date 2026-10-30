"""Enterprise CMMS Integration Adapter for SAP Plant Maintenance (PM) and IBM Maximo.
Enforces strict policy: only human-approved work orders can be synchronized externally.
"""
from datetime import datetime, timezone
from typing import TypedDict, Literal


class SAPPMOrder(TypedDict):
    HEADER: dict
    NOTIFICATION: dict
    OPERATIONS: list[dict]
    SYSTEM_INFO: dict


class MaximoWorkOrder(TypedDict):
    WONUM: str
    ASSETNUM: str
    STATUS: str
    WORKTYPE: str
    DESCRIPTION: str
    ESTIMATED_RUL: str
    TASKS: list[dict]
    EXTERNAL_SYSTEM: str
    EXPORTED_AT: str


def export_to_sap_pm(work_order: dict) -> SAPPMOrder:
    """
    Translates an approved Meridian Sentinel work order into an SAP PM (PM01) order payload.
    Strictly enforces human approval gate: drafts are rejected.
    """
    status = work_order.get("status", "draft")
    if status == "draft":
        raise ValueError("Policy violation: Unapproved draft work orders cannot be synchronized to SAP PM. Human approval by plant manager is strictly required.")

    wo_num = work_order.get("work_order_number", "WO-TEMP")
    title = work_order.get("title", "Engine Inspection")
    machine_id = str(work_order.get("machine_id", "EQUIP-UNKNOWN"))
    desc = work_order.get("description", "")
    tasks = work_order.get("tasks", [])

    operations = []
    for i, t in enumerate(tasks, start=1):
        op_num = f"{i * 10:04d}"
        operations.append({
            "ACTIVITY": op_num,
            "CONTROL_KEY": "PM01",
            "WORK_CENTER": "AERO_HANGAR",
            "DESCRIPTION": t.get("description", "Inspect subsystem"),
            "TASK_CODE": t.get("code", "AMM-72-00")
        })

    return {
        "HEADER": {
            "ORDER_ID": f"SAP-{wo_num}",
            "ORDER_TYPE": "PM01",
            "PLANT": "US_AERO_01",
            "EQUIPMENT_ID": machine_id,
            "STATUS": "REL",  # Released in SAP
            "PRIORITY": "1" if work_order.get("priority") == "urgent" else "2",
        },
        "NOTIFICATION": {
            "NOTIF_TYPE": "M2",  # Malfunction Report
            "SHORT_TEXT": title[:40],
            "LONG_TEXT": desc,
            "REPORTED_BY": "MERIDIAN_SENTINEL_SYSTEM",
            "INCIDENT_TIMESTAMP": datetime.now(timezone.utc).isoformat()
        },
        "OPERATIONS": operations,
        "SYSTEM_INFO": {
            "source": "Meridian Sentinel Condition Monitoring Portal",
            "provenance_snapshot_version": work_order.get("version", 1),
            "approved_at": work_order.get("approved_at"),
            "export_timestamp": datetime.now(timezone.utc).isoformat()
        }
    }


def export_to_maximo(work_order: dict) -> MaximoWorkOrder:
    """
    Translates an approved Meridian Sentinel work order into an IBM Maximo (MXWO) payload.
    Strictly enforces human approval gate: drafts are rejected.
    """
    status = work_order.get("status", "draft")
    if status == "draft":
        raise ValueError("Policy violation: Unapproved draft work orders cannot be synchronized to IBM Maximo. Human approval by plant manager is strictly required.")

    wo_num = work_order.get("work_order_number", "WO-TEMP")
    title = work_order.get("title", "Engine Inspection")
    machine_id = str(work_order.get("machine_id", "EQUIP-UNKNOWN"))
    tasks = work_order.get("tasks", [])

    maximo_tasks = []
    for i, t in enumerate(tasks, start=1):
        maximo_tasks.append({
            "TASKID": i,
            "DESCRIPTION": t.get("description", "AMM Inspection task"),
            "TASKCODE": t.get("code", "AMM-72-00")
        })

    return {
        "WONUM": f"MAX-{wo_num}",
        "ASSETNUM": machine_id,
        "STATUS": "WAPPR",  # Waiting on Approval in Maximo
        "WORKTYPE": "CM",    # Corrective Maintenance
        "DESCRIPTION": title,
        "ESTIMATED_RUL": f"{work_order.get('snapshot_predicted_rul', 'N/A')} cycles",
        "TASKS": maximo_tasks,
        "EXTERNAL_SYSTEM": "MERIDIAN_SENTINEL",
        "EXPORTED_AT": datetime.now(timezone.utc).isoformat()
    }
