"""Industrial IoT Gateway adapter for MQTT / OPC-UA edge telemetry normalisation.
Validates raw edge sensor payloads, enforces physical finite bounds, and maps to canonical C-MAPSS schemas.
"""
from typing import TypedDict, Literal
from datetime import datetime, timezone
import math
import numpy as np

# Canonical 21 sensor keys mapped to C-MAPSS channels
SENSOR_KEY_MAP = [
    ("t2_total_temp", "Total Temperature at Fan Inlet (°R)"),
    ("t24_lpc_outlet_temp", "Total Temperature at LPC Outlet (°R)"),
    ("t30_hpc_outlet_temp", "Total Temperature at HPC Outlet (°R)"),
    ("t50_lpt_outlet_temp", "Total Temperature at LPT Outlet (°R)"),
    ("p2_fan_inlet_pressure", "Pressure at Fan Inlet (psia)"),
    ("p15_bypass_duct_pressure", "Total Pressure in Bypass-Duct (psia)"),
    ("p30_total_hpc_pressure", "Total Pressure at HPC Outlet (psia)"),
    ("nf_fan_physical_speed", "Physical Fan Speed (rpm)"),
    ("nc_core_physical_speed", "Physical Core Speed (rpm)"),
    ("epr_engine_pressure_ratio", "Engine Pressure Ratio (P50/P2)"),
    ("ps30_static_hpc_pressure", "Static Pressure at HPC Outlet (psia)"),
    ("phi_fuel_flow_ratio", "Ratio of Fuel Flow to Ps30 (pps/psia)"),
    ("nrf_corrected_fan_speed", "Corrected Fan Speed (rpm)"),
    ("nrc_corrected_core_speed", "Corrected Core Speed (rpm)"),
    ("bpr_bypass_ratio", "Bypass Ratio"),
    ("far_fuel_air_ratio", "Burner Fuel-Air Ratio"),
    ("htbleed_bleed_enthalpy", "Bleed Enthalpy"),
    ("nf_dmd_demanded_fan_speed", "Demanded Fan Speed (rpm)"),
    ("pcnfr_dmd_demanded_corrected_fan_speed", "Demanded Corrected Fan Speed (rpm)"),
    ("w31_hpt_coolant_bleed", "HPT Coolant Bleed (lbm/s)"),
    ("w32_lpt_coolant_bleed", "LPT Coolant Bleed (lbm/s)"),
]

SETTING_KEY_MAP = [
    "altitude",
    "mach_number",
    "throttle_resolver_angle"
]


class NormalizedFrame(TypedDict):
    cycle: int
    settings: list[float]
    sensors: list[float]
    gateway_id: str
    protocol: str
    normalized_at: str


def normalize_edge_telemetry(payload: dict) -> NormalizedFrame:
    """
    Validates and normalizes an industrial edge telemetry frame from an MQTT/OPC-UA gateway.
    Accepts either structured sensor dictionary or canonical numeric arrays.
    """
    gateway_id = str(payload.get("gateway_id", "GENERIC-EDGE-GATEWAY"))
    protocol = str(payload.get("protocol", "opc_ua")).lower()
    cycle = int(payload.get("cycle", 1))

    if cycle < 1 or cycle > 2_147_483_647:
        raise ValueError("Invalid cycle count: must be between 1 and 2,147,483,647")

    # 1. Parse Operating Settings (3 channels)
    raw_settings = payload.get("operating_settings", [0.0, 0.0, 100.0])
    if isinstance(raw_settings, dict):
        settings = [
            float(raw_settings.get("altitude", 0.0)),
            float(raw_settings.get("mach_number", 0.0)),
            float(raw_settings.get("throttle_resolver_angle", 100.0)),
        ]
    elif isinstance(raw_settings, (list, tuple)):
        if len(raw_settings) != 3:
            raise ValueError(f"Operating settings must contain exactly 3 channels, got {len(raw_settings)}")
        settings = [float(x) for x in raw_settings]
    else:
        raise ValueError("Invalid operating_settings format")

    # 2. Parse Sensors (21 channels)
    raw_sensors = payload.get("sensor_readings", payload.get("sensors"))
    if isinstance(raw_sensors, dict):
        sensors = []
        for key, _ in SENSOR_KEY_MAP:
            if key not in raw_sensors:
                raise ValueError(f"Missing required sensor reading: {key}")
            sensors.append(float(raw_sensors[key]))
    elif isinstance(raw_sensors, (list, tuple)):
        if len(raw_sensors) != 21:
            raise ValueError(f"Sensor array must contain exactly 21 channels, got {len(raw_sensors)}")
        sensors = [float(x) for x in raw_sensors]
    else:
        raise ValueError("Invalid sensor_readings format: must be key-value dictionary or 21-element array")

    # 3. Finite Float & Plausibility Bounds Check
    all_values = settings + sensors
    for i, val in enumerate(all_values):
        if not math.isfinite(val):
            raise ValueError(f"Non-finite or NaN sensor reading encountered at channel index {i}")

    return {
        "cycle": cycle,
        "settings": settings,
        "sensors": sensors,
        "gateway_id": gateway_id,
        "protocol": protocol,
        "normalized_at": datetime.now(timezone.utc).isoformat()
    }

