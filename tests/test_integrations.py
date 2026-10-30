"""Unit tests for IoT edge gateway normalization and CMMS (SAP PM / Maximo) integration."""
import pytest
from sentinel.integrations.iot_gateway import normalize_edge_telemetry
from sentinel.integrations.cmms import export_to_sap_pm, export_to_maximo


def test_edge_telemetry_normalization():
    # 1. Valid dictionary sensor payload
    sample_sensors = {
        "t2_total_temp": 518.67,
        "t24_lpc_outlet_temp": 642.35,
        "t30_hpc_outlet_temp": 1589.70,
        "t50_lpt_outlet_temp": 1404.60,
        "p2_fan_inlet_pressure": 14.62,
        "p15_bypass_duct_pressure": 21.61,
        "p30_total_hpc_pressure": 553.75,
        "nf_fan_physical_speed": 2388.05,
        "nc_core_physical_speed": 9046.81,
        "epr_engine_pressure_ratio": 1.30,
        "ps30_static_hpc_pressure": 47.47,
        "phi_fuel_flow_ratio": 521.66,
        "nrf_corrected_fan_speed": 2388.08,
        "nrc_corrected_core_speed": 8128.52,
        "bpr_bypass_ratio": 8.4195,
        "far_fuel_air_ratio": 0.03,
        "htbleed_bleed_enthalpy": 392.0,
        "nf_dmd_demanded_fan_speed": 2388.0,
        "pcnfr_dmd_demanded_corrected_fan_speed": 100.0,
        "w31_hpt_coolant_bleed": 39.06,
        "w32_lpt_coolant_bleed": 23.4190
    }
    payload = {
        "gateway_id": "GATEWAY-HANGAR-01",
        "protocol": "mqtt_sparkplug_b",
        "cycle": 150,
        "operating_settings": {"altitude": 0.001, "mach_number": 0.0002, "throttle_resolver_angle": 100.0},
        "sensor_readings": sample_sensors
    }

    norm = normalize_edge_telemetry(payload)
    assert norm["cycle"] == 150
    assert norm["gateway_id"] == "GATEWAY-HANGAR-01"
    assert len(norm["settings"]) == 3
    assert len(norm["sensors"]) == 21
    assert norm["sensors"][0] == 518.67  # t2_total_temp

    # 2. Rejection of NaN / non-finite sensor
    bad_payload = dict(payload)
    bad_sensors = dict(sample_sensors)
    bad_sensors["t2_total_temp"] = float("nan")
    bad_payload["sensor_readings"] = bad_sensors

    with pytest.raises(ValueError, match="Non-finite or NaN"):
        normalize_edge_telemetry(bad_payload)


def test_cmms_export_policy_enforcement():
    # 1. Draft work orders MUST be rejected
    draft_wo = {
        "work_order_number": "WO-DRAFT-001",
        "status": "draft",
        "title": "Borescope Inspection",
        "tasks": [{"code": "AMM 72-31-00", "description": "HPC Borescope"}]
    }

    with pytest.raises(ValueError, match="Human approval by plant manager is strictly required"):
        export_to_sap_pm(draft_wo)

    with pytest.raises(ValueError, match="Human approval by plant manager is strictly required"):
        export_to_maximo(draft_wo)

    # 2. Approved work order succeeds with valid SAP PM structure
    approved_wo = {
        "work_order_number": "WO-APPR-002",
        "status": "approved",
        "title": "Borescope Inspection",
        "description": "Evidence shows 14 cycles RUL margin.",
        "priority": "urgent",
        "version": 2,
        "approved_at": "2026-10-30T10:00:00Z",
        "tasks": [{"code": "AMM 72-31-00", "description": "HPC Borescope"}]
    }

    sap = export_to_sap_pm(approved_wo)
    assert sap["HEADER"]["ORDER_ID"] == "SAP-WO-APPR-002"
    assert sap["HEADER"]["ORDER_TYPE"] == "PM01"
    assert sap["HEADER"]["STATUS"] == "REL"
    assert len(sap["OPERATIONS"]) == 1
    assert sap["OPERATIONS"][0]["TASK_CODE"] == "AMM 72-31-00"

    # 3. Approved work order succeeds with valid Maximo MIF structure
    maximo = export_to_maximo(approved_wo)
    assert maximo["WONUM"] == "MAX-WO-APPR-002"
    assert maximo["STATUS"] == "WAPPR"
    assert maximo["WORKTYPE"] == "CM"
    assert len(maximo["TASKS"]) == 1

