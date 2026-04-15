import argparse
import csv
import json
import time
from datetime import datetime
from pathlib import Path
from urllib import error, request
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CASABLANCA_TZ = ZoneInfo("Africa/Casablanca")

SCENARIOS = {
    "normal": DATA_DIR / "demo_normal.csv",
    "normal-office": DATA_DIR / "demo_normal_office.csv",
    "normal-branch": DATA_DIR / "demo_normal_branch.csv",
    "normal-workday": DATA_DIR / "demo_normal_workday.csv",
    "suspect": DATA_DIR / "demo_suspect_recon.csv",
    "suspect-dns": DATA_DIR / "demo_suspect_dns_anomaly.csv",
    "scanning": DATA_DIR / "demo_scanning.csv",
    "c2": DATA_DIR / "demo_c2_beaconing.csv",
    "botnet": DATA_DIR / "demo_botnet_multistage.csv",
    "exfiltration": DATA_DIR / "demo_exfiltration.csv",
    "propagation": DATA_DIR / "demo_propagation.csv",
    "ddos": DATA_DIR / "demo_ddos.csv",
    "ddos-distributed": DATA_DIR / "demo_ddos_distributed.csv",
    "mixed": DATA_DIR / "demo_mixed_lab.csv",
    "mixed-enterprise": DATA_DIR / "demo_mixed_enterprise.csv",
    "presentation": DATA_DIR / "demo_presentation_finale.csv",
}


def post_json(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with request.urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def read_rows(csv_path):
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def replay_rows(base_url, rows, delay, batch_size, keep_timestamps):
    ingest_url = f"{base_url}/api/live/ingest"
    sent = 0
    for index in range(0, len(rows), batch_size):
        batch = []
        for row in rows[index : index + batch_size]:
            current = dict(row)
            if not keep_timestamps:
                current["timestamp"] = datetime.now(CASABLANCA_TZ).isoformat()
            batch.append(current)
        payload = {"rows": batch} if len(batch) > 1 else {"row": batch[0]}
        post_json(ingest_url, payload)
        sent += len(batch)
        print(f"[replay] evenements envoyes: {sent}/{len(rows)}")
        if delay > 0 and sent < len(rows):
            time.sleep(delay)


def main():
    parser = argparse.ArgumentParser(description="Rejouer un scenario reseau vers SentinelFlux.")
    parser.add_argument("--scenario", choices=sorted(SCENARIOS.keys()), default="mixed")
    parser.add_argument("--file", help="Chemin d'un CSV personnalise")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--delay", type=float, default=0.8, help="Delai entre les lots en secondes")
    parser.add_argument("--batch-size", type=int, default=1, help="Nombre d'evenements par lot")
    parser.add_argument("--start-live", action="store_true", help="Demarrer le mode live HTTP avant le replay")
    parser.add_argument("--reset-live", action="store_true", help="Nettoyer le flux live avant le replay")
    parser.add_argument("--keep-timestamps", action="store_true", help="Garder les timestamps du CSV")
    args = parser.parse_args()

    csv_path = Path(args.file).resolve() if args.file else SCENARIOS[args.scenario]
    if not csv_path.exists():
        raise SystemExit(f"Fichier introuvable: {csv_path}")

    try:
        if args.reset_live:
            post_json(f"{args.base_url}/api/live/reset", {})
            print("[replay] flux live reinitialise")
        if args.start_live:
            post_json(
                f"{args.base_url}/api/live/start",
                {"mode": "http", "host": "127.0.0.1", "port": 5055},
            )
            print("[replay] mode live HTTP demarre")

        rows = read_rows(csv_path)
        print(f"[replay] scenario: {csv_path.name}")
        print(f"[replay] lignes chargees: {len(rows)}")
        replay_rows(args.base_url, rows, max(args.delay, 0), max(args.batch_size, 1), args.keep_timestamps)
        print("[replay] termine")
    except error.URLError as exc:
        raise SystemExit(f"Connexion impossible vers {args.base_url}: {exc}") from exc


if __name__ == "__main__":
    main()
