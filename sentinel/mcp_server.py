"""Model Context Protocol (MCP) Server for Meridian Sentinel.

Provides read-first and draft-only tools for AI assistants (e.g. Claude Desktop, Antigravity)
to inspect fleet telemetry, evaluate prediction evidence, and draft maintenance work orders.
Strictly adheres to safety rules: human approval gates and model deployments can NEVER be
triggered or bypassed by MCP tools.
"""
import sys
import json
import logging
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy import text

from sentinel.db import Database
from sentinel.config import load_settings, ROOT
from sentinel.registry import service as registry_service
from sentinel.ingestion import service as ingestion_service
from sentinel.predictions import service as predictions_service
from sentinel.work_orders import service as work_orders_service

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger('sentinel.mcp')

TOOLS = [
    {
        "name": "list_machines",
        "description": "Enumerate registered aircraft turbofan engines with their asset codes, data sources, and latest health status in a tenant organization.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "organization_id": {
                    "type": "string",
                    "description": "The UUID of the tenant organization"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of machines to return (default 50, max 100)",
                    "default": 50
                }
            },
            "required": ["organization_id"]
        }
    },
    {
        "name": "get_sensor_trends",
        "description": "Retrieve historical sensor observations and telemetry readings (e.g. temperatures, pressures, rotor speeds) for a specific engine asset.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "organization_id": {
                    "type": "string",
                    "description": "The UUID of the tenant organization"
                },
                "machine_id": {
                    "type": "string",
                    "description": "The UUID of the target machine"
                },
                "start_cycle": {
                    "type": "integer",
                    "description": "Starting flight cycle (default 1)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of observation cycles to fetch (default 30, max 100)",
                    "default": 30
                }
            },
            "required": ["organization_id", "machine_id"]
        }
    },
    {
        "name": "get_prediction_evidence",
        "description": "Retrieve the latest causal Remaining Useful Life (RUL) prediction, model hash, and risk priority band (URGENT, HIGH, MEDIUM, LOW) for an engine asset.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "organization_id": {
                    "type": "string",
                    "description": "The UUID of the tenant organization"
                },
                "machine_id": {
                    "type": "string",
                    "description": "The UUID of the target machine"
                }
            },
            "required": ["organization_id", "machine_id"]
        }
    },
    {
        "name": "draft_work_order",
        "description": "Draft an unapproved maintenance work order proposal with pre-filled AMM 72-00 checklist tasks. NOTE: Assistants cannot approve work orders; human plant manager review is strictly required.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "organization_id": {
                    "type": "string",
                    "description": "The UUID of the tenant organization"
                },
                "machine_id": {
                    "type": "string",
                    "description": "The UUID of the machine"
                },
                "title": {
                    "type": "string",
                    "description": "Brief descriptive title for the maintenance inspection"
                },
                "description": {
                    "type": "string",
                    "description": "Detailed justification citing discrete sensor trend or RUL evidence"
                },
                "priority": {
                    "type": "string",
                    "enum": ["urgent", "high", "medium", "low"],
                    "description": "Suggested priority level based on predictive evidence"
                }
            },
            "required": ["organization_id", "machine_id", "title", "description"]
        }
    }
]


class MCPServer:
    def __init__(self, db: Database):
        self.db = db

    def handle_list_machines(self, arguments: dict) -> dict:
        org_id = UUID(str(arguments["organization_id"]))
        limit = min(int(arguments.get("limit", 50)), 100)
        with self.db.transaction() as s:
            rows = s.execute(text("""
                SELECT id, asset_code, machine_type, data_source, lifecycle_status,
                       source_dataset, source_subset, source_engine_id, source_split, source_file_sha256
                FROM machines
                WHERE tenant_id = :t
                ORDER BY asset_code ASC
                LIMIT :limit
            """), {'t': org_id, 'limit': limit}).mappings().all()
            machines = []
            for m in rows:
                binding = None
                if m["source_dataset"]:
                    binding = {
                        "dataset": m["source_dataset"],
                        "subset": m["source_subset"],
                        "engine_id": m["source_engine_id"],
                        "split": m["source_split"],
                        "file_sha256": m["source_file_sha256"]
                    }
                machines.append({
                    "id": str(m["id"]),
                    "asset_code": m["asset_code"],
                    "machine_type": m["machine_type"],
                    "data_source": m["data_source"],
                    "status": m["lifecycle_status"],
                    "source_binding": binding,
                })
            return {"total": len(machines), "machines": machines}

    def handle_get_sensor_trends(self, arguments: dict) -> dict:
        org_id = UUID(str(arguments["organization_id"]))
        machine_id = UUID(str(arguments["machine_id"]))
        start_cycle = int(arguments.get("start_cycle", 1))
        limit = min(int(arguments.get("limit", 30)), 100)

        with self.db.transaction() as s:
            dq = ingestion_service.quality(s, org_id, machine_id, 1, None)
            obs = ingestion_service.history(
                s, org_id, machine_id,
                start=start_cycle,
                end=start_cycle + limit - 1,
                after=start_cycle - 1,
                limit=limit
            )
            return {
                "machine_id": str(machine_id),
                "data_quality": dq,
                "observation_count": len(obs.get("items", [])),
                "cycles": [
                    {
                        "cycle": o["cycle"],
                        "settings": o["settings"],
                        "sensors": o["sensors"]
                    }
                    for o in obs.get("items", [])
                ]
            }

    def handle_get_prediction_evidence(self, arguments: dict) -> dict:
        org_id = UUID(str(arguments["organization_id"]))
        machine_id = UUID(str(arguments["machine_id"]))
        with self.db.transaction() as s:
            try:
                pred = predictions_service.get_latest_prediction(s, org_id, machine_id)
            except Exception:
                pred = None
            if not pred:
                return {
                    "machine_id": str(machine_id),
                    "status": "no_prediction_available",
                    "message": "No predictive RUL evaluation recorded for this machine."
                }
            return {
                "machine_id": str(machine_id),
                "prediction_id": str(pred["id"]),
                "predicted_rul_cycles": pred.get("predicted_rul"),
                "maintenance_priority": str(pred.get("priority", "UNKNOWN")).upper(),
                "cutoff_cycle": pred.get("cutoff_cycle"),
                "model_version": pred.get("model_version"),
                "model_bundle_sha256": pred.get("model_bundle_sha256"),
                "input_digest": pred.get("input_digest"),
                "policy_explanation": pred.get("policy_explanation"),
            }

    def handle_draft_work_order(self, arguments: dict) -> dict:
        org_id = UUID(str(arguments["organization_id"]))
        machine_id = UUID(str(arguments["machine_id"]))
        title = arguments["title"]
        description = arguments["description"]
        priority = arguments.get("priority", "medium")

        with self.db.transaction() as s:
            admin_user = s.execute(text("""
                SELECT user_id FROM memberships
                WHERE tenant_id = :t AND active AND 'admin' = ANY(roles)
                LIMIT 1
            """), {'t': org_id}).scalar_one_or_none()
            if not admin_user:
                raise ValueError("No authorized administrator found for tenant")

            draft = work_orders_service.create_manual_draft(
                s,
                tenant=org_id,
                machine_id=machine_id,
                actor_id=admin_user,
                title=title,
                description=description,
                priority=priority
            )
            return {
                "work_order_id": str(draft["id"]),
                "work_order_number": draft.get("work_order_number"),
                "status": "draft",
                "notice": "Draft work order created successfully. Under Meridian Sentinel policy, work orders require human review and approval by an authorized plant manager before maintenance execution."
            }

    def dispatch_tool(self, name: str, arguments: dict) -> dict:
        if name == "list_machines":
            return self.handle_list_machines(arguments)
        elif name == "get_sensor_trends":
            return self.handle_get_sensor_trends(arguments)
        elif name == "get_prediction_evidence":
            return self.handle_get_prediction_evidence(arguments)
        elif name == "draft_work_order":
            return self.handle_draft_work_order(arguments)
        else:
            raise ValueError(f"Unknown MCP tool: {name}")

    def handle_request(self, req: dict) -> dict:
        msg_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "meridian-sentinel-mcp",
                        "version": "1.0.0"
                    }
                }
            }
        elif method == "notifications/initialized":
            return None
        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"tools": TOOLS}
            }
        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            try:
                result_data = self.dispatch_tool(tool_name, tool_args)
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(result_data, indent=2)
                            }
                        ]
                    }
                }
            except Exception as e:
                logger.exception("Error executing MCP tool")
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32000,
                        "message": str(e)
                    }
                }
        else:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }

    def run_stdio(self):
        """Standard IO event loop for MCP communication."""
        logger.info("Meridian Sentinel MCP Server started on stdio.")
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
                resp = self.handle_request(req)
                if resp is not None:
                    sys.stdout.write(json.dumps(resp) + "\n")
                    sys.stdout.flush()
            except Exception as e:
                logger.error(f"Error handling MCP line: {e}")


def main():
    settings = load_settings(ROOT / '.env')
    db = Database(settings.database_url)
    server = MCPServer(db)
    server.run_stdio()


if __name__ == '__main__':
    main()

