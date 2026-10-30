"""Admin-only automated ingestion, data cleaning, EDA, feature engineering, and live fleet updating."""
from datetime import datetime, timezone
import hashlib
import io
import json
from uuid import UUID, uuid4
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
import numpy as np
import pandas as pd
from sqlalchemy import text

from sentinel.auth.context import AuthContext
from sentinel.data import COLUMNS, SENSORS, SETTINGS, VALUES, sha256
from sentinel.features import feature_names, window_features
from sentinel.ingestion.schemas import Batch, MAX_BATCH
from sentinel.ingestion.service import ingest
from sentinel.predictions.service import compute_and_persist
from sentinel.registry.schemas import InstallationCreate, MachineCreate, SensorCreate
from sentinel.registry.service import Registry


def admin_pipeline_router(database, settings, predictor=None) -> APIRouter:
    router = APIRouter(prefix="/api/v1/organizations/{tenant_id}/admin/pipeline", tags=["Admin ML Pipeline"])
    auth = AuthContext(database, settings)

    @router.post("/process-dataset")
    async def process_dataset(tenant_id: UUID, request: Request, file: UploadFile = File(...)):
        # 1. Enforce strict Admin-only authentication gate
        with auth.transaction(request) as s:
            actor = auth.principal(s, request)
            auth.csrf(request, actor)
            auth.membership(s, actor, tenant_id, "members.manage")  # Admin required

        # 2. Read incoming CSV / text content
        raw_bytes = await file.read()
        if not raw_bytes or len(raw_bytes) > 25 * 1024 * 1024:  # 25 MB limit
            raise HTTPException(400, "File empty or exceeds 25 MB limit")

        try:
            # Try parsing with comma or whitespace separator
            try:
                df_raw = pd.read_csv(io.BytesIO(raw_bytes))
                if df_raw.shape[1] < 5:
                    df_raw = pd.read_csv(io.BytesIO(raw_bytes), sep=r"\s+", header=None)
            except Exception:
                df_raw = pd.read_csv(io.BytesIO(raw_bytes), sep=r"\s+", header=None)
        except Exception as e:
            raise HTTPException(400, f"Cannot parse file format: {str(e)}")

        # 3. Clean and normalize data (Flexible Option B Mapping)
        # If unnamed numeric columns of shape 26, map to C-MAPSS standard
        if df_raw.shape[1] == 26 and (df_raw.columns[0] == 0 or '0' in str(df_raw.columns[0])):
            df_raw.columns = COLUMNS
        else:
            # Flexible mapping of user-supplied columns
            col_map = {}
            for col in df_raw.columns:
                c_str = str(col).strip().lower()
                if c_str in ("engine", "engine_id", "id", "unit", "machine", "asset"):
                    col_map[col] = "engine_id"
                elif c_str in ("cycle", "time", "flight_cycle", "step"):
                    col_map[col] = "cycle"
                else:
                    # Map sensor_1 -> sensor_01, s1 -> sensor_01, etc.
                    for s_idx in range(1, 22):
                        if c_str in (f"sensor_{s_idx}", f"sensor_{s_idx:02d}", f"s{s_idx}", f"sensor{s_idx}"):
                            col_map[col] = f"sensor_{s_idx:02d}"
                    for set_idx in range(1, 4):
                        if c_str in (f"setting_{set_idx}", f"setting{set_idx}", f"op_setting_{set_idx}", f"setting_{set_idx:02d}"):
                            col_map[col] = f"setting_{set_idx}"
            df_raw = df_raw.rename(columns=col_map)

        # Ensure default required columns exist
        if "engine_id" not in df_raw.columns:
            df_raw["engine_id"] = 1
        if "cycle" not in df_raw.columns:
            df_raw["cycle"] = np.arange(1, len(df_raw) + 1)

        # Fill missing settings with nominal defaults if not present
        for set_col in SETTINGS:
            if set_col not in df_raw.columns:
                df_raw[set_col] = 0.0

        # Fill missing sensors with nominal zero if completely absent
        missing_sensors = []
        for s_col in SENSORS:
            if s_col not in df_raw.columns:
                df_raw[s_col] = 0.0
                missing_sensors.append(s_col)

        # Drop non-finite rows (NaN, inf) & duplicate cycles
        initial_rows = len(df_raw)
        df_clean = df_raw.dropna(subset=["engine_id", "cycle"] + VALUES).copy()
        df_clean = df_clean.sort_values(["engine_id", "cycle"]).drop_duplicates(["engine_id", "cycle"])
        dropped_rows = initial_rows - len(df_clean)

        # 4. Perform Automated EDA
        eda_summary = {}
        correlations = {}
        wear_trends = {}

        for sensor in SENSORS:
            vals = df_clean[sensor].to_numpy(dtype=float)
            s_std = float(vals.std())
            s_mean = float(vals.mean())
            s_min = float(vals.min())
            s_max = float(vals.max())
            # Trend calculation (linear regression slope with respect to cycle)
            cycles = df_clean["cycle"].to_numpy(dtype=float)
            if len(cycles) > 1 and s_std > 1e-6:
                c_norm = cycles - cycles.mean()
                slope = float((c_norm @ (vals - s_mean)) / (c_norm @ c_norm))
                corr = float(np.corrcoef(cycles, vals)[0, 1])
                if not np.isfinite(corr):
                    corr = 0.0
            else:
                slope = 0.0
                corr = 0.0

            eda_summary[sensor] = {
                "mean": round(s_mean, 4),
                "std": round(s_std, 4),
                "min": round(s_min, 4),
                "max": round(s_max, 4),
                "degradation_slope": round(slope, 6),
                "cycle_correlation": round(corr, 4),
                "status": "constant" if s_std < 1e-5 else ("degrading" if abs(corr) > 0.4 else "active"),
            }

        # 5. Feature Engineering (Trailing Window W=30, 96 causal features)
        window_size = 30
        engineered_windows = []
        target_features = []

        for eng_id, g in df_clean.groupby("engine_id"):
            arr = g[VALUES].to_numpy(dtype=float)
            if len(arr) >= 2:
                # compute window feature on latest available window (up to 30)
                sub = arr[-min(window_size, len(arr)):]
                # pad or extract
                if len(sub) >= 2:
                    t = np.arange(len(sub), dtype=float)
                    t -= t.mean()
                    feat = np.concatenate([sub[-1], sub.mean(0), sub.std(0), (t @ sub / (t @ t)) if len(sub) > 2 else np.zeros(len(VALUES))])
                    engineered_windows.append({
                        "engine_id": int(eng_id),
                        "latest_cycle": int(g["cycle"].iloc[-1]),
                        "window_points": len(sub),
                        "features_count": len(feat),
                    })

        # 6. Auto-Register & Ingest into Database and Predict
        results_engines = []
        file_hash = hashlib.sha256(raw_bytes).hexdigest()

        with database.transaction() as s:
            registry = Registry(s, tenant_id, actor["user_id"], uuid4())
            unique_engines = df_clean["engine_id"].unique()

            for eng_id in unique_engines:
                eng_df = df_clean[df_clean["engine_id"] == eng_id]
                asset_code = f"INGESTED-ENG-{eng_id}-{file_hash[:6].upper()}"

                # Check or create machine
                old_m = s.execute(
                    text("SELECT * FROM machines WHERE tenant_id=:t AND asset_code=:code"),
                    dict(t=tenant_id, code=asset_code),
                ).mappings().one_or_none()

                if old_m:
                    m_id = old_m["id"]
                else:
                    m_id = registry.create_machine(
                        MachineCreate(
                            asset_code=asset_code,
                            name=f"Ingested Degradation Stream Engine {eng_id}",
                            machine_type="cmapss_engine",
                            data_source="nasa_replay",
                            source_binding=dict(
                                dataset="C-MAPSS",
                                subset="FD001",
                                engine_id=int(eng_id) if int(eng_id) > 0 else 1,
                                split="test",
                                file_sha256=file_hash,
                            ),
                        )
                    )["id"]

                # Ensure sensors & installations exist
                for ch in SENSORS:
                    s_code = f"{asset_code}-{ch}"
                    existing_s = s.execute(
                        text("SELECT id FROM sensors WHERE tenant_id=:t AND sensor_code=:c"),
                        dict(t=tenant_id, c=s_code),
                    ).scalar_one_or_none()
                    if not existing_s:
                        new_s_id = registry.create_sensor(
                            SensorCreate(
                                sensor_code=s_code,
                                name=f"Logical {ch}",
                                kind="cmapss_channel",
                                data_source="nasa_replay",
                                channel_id=ch,
                            )
                        )["id"]
                    else:
                        new_s_id = existing_s

                    existing_inst = s.execute(
                        text("SELECT id FROM installations WHERE tenant_id=:t AND machine_id=:m AND sensor_id=:s"),
                        dict(t=tenant_id, m=m_id, s=new_s_id),
                    ).scalar_one_or_none()

                    if not existing_inst:
                        registry.install(
                            m_id,
                            InstallationCreate(
                                sensor_id=new_s_id,
                                channel=ch,
                                installed_at=datetime.now(timezone.utc),
                                note="Admin uploaded degradation stream",
                            ),
                        )

                # Ingest observation batch
                rows = [
                    dict(
                        cycle=int(row["cycle"]),
                        settings=[float(row[k]) for k in SETTINGS],
                        sensors=[float(row[k]) for k in SENSORS],
                    )
                    for _, row in eng_df.iterrows()
                ]

                source_meta = dict(
                    dataset="C-MAPSS",
                    subset="FD001",
                    partition="test",
                    engine_id=int(eng_id),
                    file_sha256=file_hash,
                    schema_version=1,
                )

                for offset in range(0, len(rows), MAX_BATCH):
                    b_rows = rows[offset:offset + MAX_BATCH]
                    batch_model = Batch.model_validate(dict(source=source_meta, observations=b_rows))
                    ingest(s, tenant_id, m_id, actor["user_id"], uuid4(), batch_model, f"admin-upload-{eng_id}-{offset}")

                # Predict RUL if predictor loaded
                pred_result = None
                if predictor is not None:
                    pred_result = compute_and_persist(s, tenant_id, m_id, actor["user_id"], uuid4(), predictor)

                rul_display = (
                    f"{pred_result.get('rul_cycles', 0):.1f} cycles"
                    if pred_result and pred_result.get("rul_cycles") is not None
                    else "N/A"
                )

                results_engines.append({
                    "engine_id": int(eng_id),
                    "asset_code": asset_code,
                    "machine_id": str(m_id),
                    "total_cycles_ingested": len(rows),
                    "estimated_rul": rul_display,
                    "priority_band": pred_result.get("priority_band") if pred_result else "unknown",
                })

        return {
            "status": "success",
            "filename": file.filename,
            "cleaning": {
                "initial_rows": initial_rows,
                "cleaned_rows": len(df_clean),
                "dropped_rows": dropped_rows,
                "missing_sensors_padded": missing_sensors,
                "unique_engines_found": len(unique_engines),
            },
            "eda_analysis": eda_summary,
            "feature_engineering": {
                "schema": "cmapss-trailing-v1",
                "feature_count_per_window": len(feature_names()),
                "feature_names_sample": feature_names()[:10],
                "windows_computed": len(engineered_windows),
            },
            "ingested_fleet": results_engines,
            "dashboard_message": f"Successfully ingested {len(results_engines)} engine(s). The Fleet Overview dashboard has been live-updated!",
        }

    return router
