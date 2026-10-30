"""Mock IoT / Edge Gateway Telemetry Streamer for Meridian Sentinel.

Streams sensor observations cycle-by-cycle to the running Sentinel backend,
triggering live data ingestion, causal feature extraction, and real-time RUL prediction.

Usage:
    python scripts/stream_telemetry.py --asset NASA-FD001-TRAIN-1 --interval 1.5
    python scripts/stream_telemetry.py --asset NASA-FD001-TRAIN-1 --reset --start-cycle 1 --interval 1.0
"""
import argparse
import hashlib
import io
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sentinel.data import read_data, SETTINGS, SENSORS
from sentinel.ingestion.schemas import Batch, MAX_BATCH
from sentinel.ingestion.service import payload_digest


def parse_args():
    parser = argparse.ArgumentParser(description="Stream sensor telemetry to Meridian Sentinel")
    parser.add_argument("--origin", default="http://127.0.0.1:8001", help="Backend origin URL")
    parser.add_argument("--email", default="admin@meridian.example.com", help="Operator/Admin email")
    parser.add_argument("--password", default="Password12345!", help="Account password")
    parser.add_argument("--asset", default="NASA-FD001-TRAIN-1", help="Target machine asset code")
    parser.add_argument("--interval", type=float, default=1.5, help="Interval between cycles in seconds (default: 1.5)")
    parser.add_argument("--start-cycle", type=int, default=None, help="Start cycle (default: resume after latest or 1)")
    parser.add_argument("--end-cycle", type=int, default=None, help="End cycle (default: trajectory end)")
    parser.add_argument("--reset", action="store_true", help="Reset existing observations and predictions for this machine before streaming")
    return parser.parse_args()


class StreamClient:
    def __init__(self, origin: str, email: str, password: str):
        self.origin = origin.rstrip("/")
        self.email = email
        self.password = password
        self.client = httpx.Client(base_url=self.origin, timeout=15.0, follow_redirects=False)
        self.csrf_token = None
        self.tenant_id = None

    def login(self):
        login_res = self.client.post(
            "/api/v1/auth/login",
            headers={"Origin": self.origin, "X-CSRF-Protection": "1"},
            json={"email": self.email, "password": self.password},
        )
        if login_res.status_code != 200:
            raise RuntimeError(f"Login failed (HTTP {login_res.status_code}): {login_res.text}")
        data = login_res.json()
        self.csrf_token = data["csrf_token"]
        orgs = data.get("organizations", [])
        if not orgs:
            raise RuntimeError("No active organizations found for this user.")
        self.tenant_id = orgs[0]["id"]
        print(f"[AUTH] Logged in successfully as {self.email}")
        print(f"[AUTH] Active Tenant: {orgs[0]['name']} ({self.tenant_id})")

    def logout(self):
        if self.csrf_token:
            try:
                self.client.post(
                    "/api/v1/auth/logout",
                    headers={"Origin": self.origin, "X-CSRF-Token": self.csrf_token},
                )
            except Exception:
                pass
        self.client.close()

    def get_machine(self, asset_code: str):
        res = self.client.get(
            f"/api/v1/organizations/{self.tenant_id}/machines",
            headers={"Origin": self.origin},
            params={"asset_code": asset_code},
        )
        if res.status_code != 200:
            raise RuntimeError(f"Failed to fetch machine '{asset_code}': {res.text}")
        items = res.json().get("items", [])
        if items:
            return items[0]
        raise RuntimeError(f"Machine with asset_code '{asset_code}' not found in tenant.")

    def get_latest_cycle(self, machine_id: str) -> int:
        res = self.client.get(
            f"/api/v1/organizations/{self.tenant_id}/machines/{machine_id}/data-quality",
            headers={"Origin": self.origin},
        )
        if res.status_code == 200:
            return res.json().get("max_cycle") or 0
        return 0

    def ingest_cycle(self, machine_id: str, source: dict, observation: dict):
        batch = Batch.model_validate(dict(source=source, observations=[observation]))
        key = f"stream-e{source['engine_id']}-c{observation['cycle']}-{payload_digest(batch)[:16]}"
        res = self.client.post(
            f"/api/v1/organizations/{self.tenant_id}/machines/{machine_id}/replay-batches",
            headers={"Origin": self.origin, "X-CSRF-Token": self.csrf_token, "Idempotency-Key": key},
            json=batch.model_dump(mode="json"),
        )
        if res.status_code not in (200, 201):
            raise RuntimeError(f"Ingest failed at cycle {observation['cycle']} (HTTP {res.status_code}): {res.text}")
        return res.json()

    def compute_prediction(self, machine_id: str, cutoff_cycle: int):
        res = self.client.post(
            f"/api/v1/organizations/{self.tenant_id}/machines/{machine_id}/predictions",
            headers={"Origin": self.origin, "X-CSRF-Token": self.csrf_token},
            json={"cutoff_cycle": cutoff_cycle},
        )
        if res.status_code != 200:
            return None
        return res.json().get("prediction")


def load_trajectory(data_dir: Path, subset: str, partition: str, engine_id: int):
    path = data_dir / f"{partition}_{subset}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Source trajectory file not found: {path}")
    raw = path.read_bytes()
    frame = read_data(io.BytesIO(raw))
    selected = frame[frame.engine_id == engine_id].sort_values("cycle")
    if selected.empty:
        raise ValueError(f"No observations found for engine {engine_id} in {path.name}")
    source = dict(
        dataset="C-MAPSS",
        subset=subset,
        partition=partition,
        engine_id=engine_id,
        file_sha256=hashlib.sha256(raw).hexdigest(),
        schema_version=1,
    )
    rows = [
        dict(
            cycle=int(row.cycle),
            settings=[float(row[k]) for k in SETTINGS],
            sensors=[float(row[k]) for k in SENSORS],
        )
        for _, row in selected.iterrows()
    ]
    return source, rows


def reset_machine_data(tenant_id: str, machine_id: str):
    """Safely reset observations & predictions for the machine when --reset is requested."""
    from sentinel.config import ROOT, read_env
    from sentinel.db import Database
    from sqlalchemy import text
    env = read_env(ROOT / ".runtime/postgres.env")
    db = Database(env["DATABASE_URL"])
    with db.transaction() as s:
        s.execute(text("DELETE FROM predictions WHERE tenant_id=:t AND machine_id=:m"), dict(t=tenant_id, m=machine_id))
        s.execute(text("DELETE FROM replay_observations WHERE tenant_id=:t AND stream_id IN (SELECT id FROM replay_streams WHERE machine_id=:m)"), dict(t=tenant_id, m=machine_id))
        s.execute(text("DELETE FROM replay_batches WHERE tenant_id=:t AND machine_id=:m"), dict(t=tenant_id, m=machine_id))
    print(f"[RESET] Cleared observations and predictions for machine {machine_id}")


def main():
    args = parse_args()
    client = StreamClient(args.origin, args.email, args.password)
    try:
        client.login()
        machine = client.get_machine(args.asset)
        machine_id = machine["id"]
        binding = machine.get("source_binding") or {}
        subset = binding.get("subset", "FD001")
        partition = binding.get("split", "train")
        engine_id = binding.get("engine_id", 1)

        print(f"[STREAM TARGET] Asset: {args.asset} (ID: {machine_id})")
        print(f"[STREAM TARGET] Dataset: C-MAPSS {subset} | Partition: {partition} | Engine ID: {engine_id}")

        if args.reset:
            reset_machine_data(client.tenant_id, machine_id)

        data_dir = Path(__file__).resolve().parents[1] / "data/raw"
        source, rows = load_trajectory(data_dir, subset, partition, engine_id)
        total_cycles = len(rows)
        print(f"[DATA] Loaded {total_cycles} cycles from {partition}_{subset}.txt")

        latest_cycle = 0 if args.reset else client.get_latest_cycle(machine_id)
        start_cycle = args.start_cycle if args.start_cycle is not None else (latest_cycle + 1)
        end_cycle = args.end_cycle if args.end_cycle is not None else total_cycles

        if start_cycle > total_cycles:
            print(f"[STREAM] Machine already has all {total_cycles} cycles ingested! Use --reset to re-stream.")
            return

        print(f"[STREAMING] Starting telemetry stream from Cycle {start_cycle} to {end_cycle} at {args.interval}s interval...")
        print("-" * 80)

        for obs in rows:
            cycle = obs["cycle"]
            if cycle < start_cycle or cycle > end_cycle:
                continue

            t0 = time.perf_counter()
            # 1. Ingest observation cycle
            client.ingest_cycle(machine_id, source, obs)
            
            # 2. Trigger causal RUL inference
            pred = client.compute_prediction(machine_id, cutoff_cycle=cycle)
            elapsed_ms = (time.perf_counter() - t0) * 1000

            # 3. Format terminal status line
            rul_str = f"{pred['rul_cycles']:.1f} cycles" if pred and pred.get("rul_cycles") is not None else "N/A"
            band_str = (pred.get("priority_band") or "UNKNOWN").upper()
            status_str = pred.get("status", "unknown").upper() if pred else "UNKNOWN"

            # Key sensor values for display: T2 (sensor 2), T24 (sensor 3), T30 (sensor 4)
            s2 = obs["sensors"][1]
            s3 = obs["sensors"][2]
            s4 = obs["sensors"][3]

            color_code = "\033[92m" if band_str == "LOW" else "\033[93m" if band_str in ("MEDIUM", "HIGH") else "\033[91m"
            reset_code = "\033[0m"

            print(
                f"[TICK] Cycle {cycle:3d}/{total_cycles} | T_LPC: {s2:6.2f} | T_HPC: {s3:7.2f} | P_HPC: {s4:7.2f} | "
                f"{color_code}RUL: {rul_str:>11} | Status: {status_str} | Priority: {band_str:<6}{reset_code} ({elapsed_ms:.0f}ms)"
            )

            time.sleep(args.interval)

        print("-" * 80)
        print(f"[DONE] Telemetry streaming completed for {args.asset} (Cycles {start_cycle}..{end_cycle}).")

    except KeyboardInterrupt:
        print("\n[ABORTED] Streamer paused by operator (Ctrl+C).")
    finally:
        client.logout()


if __name__ == "__main__":
    main()
