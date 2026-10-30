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
        org_id = UUID(arguments["organization_id"])
        limit = min(int(arguments.get("limit", 50)), 100)
        with self.db.transaction() as s:
            res = registry_service.list_machines(s, org_id, limit=limit)
            machines = []
            for m in res.get("items", []):
                machines.append({
                    "id": str(m["id"]),
                    "asset_code": m["asset_code"],
                    "machine_type": m["machine_type"],
                    "data_source": m["data_source"],
                    "status": m["status"],
                    "source_binding": m.get("source_binding"),
                })
            return {"total": len(machines), "machines": machines}

    def handle_get_sensor_trends(self, arguments: dict) -> dict:
        org_id = UUID(arguments["organization_id"])
        machine_id = UUID(arguments["machine_id"])
        start_cycle = int(arguments.get("start_cycle", 1))
        limit = min(int(arguments.get("limit", 30)), 100)

        with self.db.transaction() as s:
            dq = ingestion_service.get_data_quality(s, org_id, machine_id)
            obs = ingestion_service.get_observations(
                s, org_id, machine_id,
                start_cycle=start_cycle,
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
        org_id = UUID(arguments["organization_id"])
        machine_id = UUID(arguments["machine_id"])
        with self.db.transaction() as s:
            pred = predictions_service.get_latest_prediction(s, org_id, machine_id)
            if not pred:
                return {
                    "machine_id": str(machine_id),
                    "status": "no_prediction_available",
                    "message": "No predictive RUL evaluation recorded for this machine."
                }
            return {
                "machine_id": str(machine_id),
                "prediction_id": str(pred["id"]),
                "predicted_rul_cycles": pred["predicted_rul"],
                "maintenance_priority": pred["priority"].upper(),
                "cutoff_cycle": pred["cutoff_cycle"],
                "model_version": pred["model_version"],
                "model_bundle_sha256": pred["model_bundle_sha256"],
                "input_digest": pred["input_digest"],
                "policy_explanation": pred.get("policy_explanation"),
            }

    def handle_draft_work_order(self, arguments: dict) -> dict:
        org_id = UUID(arguments["organization_id"])
        machine_id = UUID(arguments["machine_id"])
        title = arguments["title"]
        description = arguments["description"]
        priority = arguments.get("priority", "medium")

        # Create system-actor UUID for assistant draft creation
        assistant_actor = UUID("00000000-0000-0000-0000-000000000002")

        with self.db.transaction() as s:
            draft = work_orders_service.create_work_order(
                s,
                tenant_id=org_id,
                actor_id=assistant_actor,
                machine_id=machine_id,
                title=title,
                description=description,
                priority=priority,
                source="mcp_assistant",
                tasks=[
                    {"code": "AMM 72-00-00", "description": "Pre-Inspection Engine Lockout & Safety Tagging"},
                    {"code": "AMM 72-31-00", "description": "Flexible Borescope Inspection of Compressor Blades"},
                    {"code": "AMM 72-00-05", "description": "Post-Maintenance Ground Run Verification"}
                ]
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

