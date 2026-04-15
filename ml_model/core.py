import csv
import io
import json
import socket
import statistics
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DEFAULT_LOG = DATA_DIR / "network_logs_sample.csv"
WINDOW_MINUTES = 5
LIVE_RETENTION_MINUTES = 30
CASABLANCA_TZ = ZoneInfo("Africa/Casablanca")


def clamp(value, low=0.0, high=100.0):
    return max(low, min(high, float(value)))


def casablanca_now():
    return datetime.now(CASABLANCA_TZ)


def safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value, default=0):
    try:
        if value in (None, ""):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def iso_to_dt(value):
    if isinstance(value, datetime):
        return value
    if not value:
        return casablanca_now()
    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(text, pattern)
            except ValueError:
                continue
    return casablanca_now()


def floor_window(ts, minutes=WINDOW_MINUTES):
    ts = iso_to_dt(ts)
    return ts.replace(minute=(ts.minute // minutes) * minutes, second=0, microsecond=0)


def median_iqr(values):
    ordered = sorted(float(v) for v in values if v is not None)
    if not ordered:
        return 0.0, 1.0
    med = statistics.median(ordered)
    if len(ordered) < 4:
        return med, max(abs(med), 1.0)
    lower = ordered[: len(ordered) // 2]
    upper = ordered[(len(ordered) + 1) // 2 :]
    q1 = statistics.median(lower) if lower else ordered[0]
    q3 = statistics.median(upper) if upper else ordered[-1]
    return med, max(q3 - q1, 1.0)


def _pdf_escape(text):
    return str(text).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def minimal_pdf(title, lines):
    page_height = 792
    margin_top = 64
    line_height = 18
    max_lines = 36
    pages = []
    current = [title, ""]
    for line in lines:
        current.append(str(line))
        if len(current) >= max_lines:
            pages.append(current)
            current = [title, ""]
    if current:
        pages.append(current)

    objects = []
    page_ids = []
    next_id = 1
    catalog_id = next_id
    next_id += 1
    pages_id = next_id
    next_id += 1
    font_id = next_id
    next_id += 1

    for page_lines in pages:
        page_id = next_id
        content_id = next_id + 1
        next_id += 2
        page_ids.append((page_id, content_id, page_lines))

    objects.append(f"{catalog_id} 0 obj << /Type /Catalog /Pages {pages_id} 0 R >> endobj")
    kids = " ".join(f"{page_id} 0 R" for page_id, _, _ in page_ids)
    objects.append(f"{pages_id} 0 obj << /Type /Pages /Count {len(page_ids)} /Kids [{kids}] >> endobj")
    objects.append(f"{font_id} 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj")

    for page_id, content_id, page_lines in page_ids:
        objects.append(
            f"{page_id} 0 obj << /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 612 {page_height}] "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >> endobj"
        )
        text_lines = ["BT", "/F1 12 Tf", f"72 {page_height - margin_top} Td"]
        first = True
        for line in page_lines:
            if not first:
                text_lines.append(f"0 -{line_height} Td")
            text_lines.append(f"({_pdf_escape(line)}) Tj")
            first = False
        text_lines.append("ET")
        stream = "\n".join(text_lines).encode("latin-1", errors="ignore")
        header = f"{content_id} 0 obj << /Length {len(stream)} >> stream\n".encode("latin-1")
        footer = b"\nendstream endobj"
        objects.append((header, stream, footer))

    output = b"%PDF-1.4\n"
    offsets = [0]
    for obj in objects:
        offsets.append(len(output))
        if isinstance(obj, tuple):
            output += obj[0] + obj[1] + obj[2] + b"\n"
        else:
            output += obj.encode("latin-1") + b"\n"
    xref_offset = len(output)
    output += f"xref\n0 {len(offsets)}\n".encode("latin-1")
    output += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        output += f"{off:010d} 00000 n \n".encode("latin-1")
    output += (
        f"trailer << /Size {len(offsets)} /Root {catalog_id} 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode(
            "latin-1"
        )
    )
    return output


def build_pdf_document(page_streams):
    page_height = 841.8898
    objects = []
    page_ids = []
    next_id = 1
    catalog_id = next_id
    next_id += 1
    pages_id = next_id
    next_id += 1
    font_regular_id = next_id
    next_id += 1
    font_bold_id = next_id
    next_id += 1

    for stream in page_streams:
        page_id = next_id
        content_id = next_id + 1
        next_id += 2
        page_ids.append((page_id, content_id, stream))

    objects.append(f"{catalog_id} 0 obj << /Type /Catalog /Pages {pages_id} 0 R >> endobj")
    kids = " ".join(f"{page_id} 0 R" for page_id, _, _ in page_ids)
    objects.append(f"{pages_id} 0 obj << /Type /Pages /Count {len(page_ids)} /Kids [{kids}] >> endobj")
    objects.append(f"{font_regular_id} 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj")
    objects.append(f"{font_bold_id} 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >> endobj")

    for page_id, content_id, stream in page_ids:
        objects.append(
            f"{page_id} 0 obj << /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 595.2756 {page_height}] "
            f"/Resources << /Font << /F1 {font_regular_id} 0 R /F2 {font_bold_id} 0 R >> >> "
            f"/Contents {content_id} 0 R >> endobj"
        )
        stream_bytes = stream.encode("latin-1", errors="ignore")
        header = f"{content_id} 0 obj << /Length {len(stream_bytes)} >> stream\n".encode("latin-1")
        footer = b"\nendstream endobj"
        objects.append((header, stream_bytes, footer))

    output = b"%PDF-1.4\n"
    offsets = [0]
    for obj in objects:
        offsets.append(len(output))
        if isinstance(obj, tuple):
            output += obj[0] + obj[1] + obj[2] + b"\n"
        else:
            output += obj.encode("latin-1") + b"\n"
    xref_offset = len(output)
    output += f"xref\n0 {len(offsets)}\n".encode("latin-1")
    output += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        output += f"{off:010d} 00000 n \n".encode("latin-1")
    output += (
        f"trailer << /Size {len(offsets)} /Root {catalog_id} 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode(
            "latin-1"
        )
    )
    return output


@dataclass
class MachineWindow:
    machine_ip: str
    window_start: datetime
    rows: list = field(default_factory=list)


class Analyzer:
    feature_keys = [
        "total_connections",
        "avg_duration",
        "bytes_sent",
        "bytes_received",
        "upload_download_ratio",
        "packets",
        "distinct_destination_ips",
        "distinct_ports",
        "connection_frequency",
        "simultaneous_connections",
        "failed_connections",
        "dns_requests",
        "dns_nxdomain_rate",
        "domain_diversity",
        "dns_frequency",
        "mean_interconnection_time",
        "periodicity",
        "night_activity_ratio",
        "traffic_burst_score",
    ]

    def load_rows(self, csv_text):
        reader = csv.DictReader(io.StringIO(csv_text.strip()))
        rows = []
        for row in reader:
            if not row:
                continue
            rows.append(
                {
                    "timestamp": row.get("timestamp", ""),
                    "src_ip": row.get("src_ip", ""),
                    "dst_ip": row.get("dst_ip", ""),
                    "dst_port": safe_int(row.get("dst_port")),
                    "protocol": row.get("protocol", "TCP"),
                    "bytes_sent": safe_float(row.get("bytes_sent")),
                    "bytes_received": safe_float(row.get("bytes_received")),
                    "packets": safe_int(row.get("packets")),
                    "duration": safe_float(row.get("duration")),
                    "status": row.get("status", "SUCCESS"),
                    "dns_query": row.get("dns_query", ""),
                    "dns_response_code": row.get("dns_response_code", ""),
                }
            )
        return rows

    def aggregate(self, rows):
        grouped = {}
        for row in rows:
            src_ip = row.get("src_ip") or "unknown"
            key = (src_ip, floor_window(row.get("timestamp")))
            grouped.setdefault(key, MachineWindow(machine_ip=src_ip, window_start=key[1])).rows.append(row)

        features = []
        for (machine_ip, window_start), machine_window in grouped.items():
            machine_rows = sorted(machine_window.rows, key=lambda item: iso_to_dt(item.get("timestamp")))
            timestamps = [iso_to_dt(item.get("timestamp")) for item in machine_rows]
            durations = [safe_float(item.get("duration")) for item in machine_rows]
            sent = [safe_float(item.get("bytes_sent")) for item in machine_rows]
            received = [safe_float(item.get("bytes_received")) for item in machine_rows]
            packets = [safe_int(item.get("packets")) for item in machine_rows]
            destinations = {item.get("dst_ip") for item in machine_rows if item.get("dst_ip")}
            ports = {safe_int(item.get("dst_port")) for item in machine_rows if item.get("dst_port") not in (None, "")}
            smb_connections = sum(1 for item in machine_rows if safe_int(item.get("dst_port")) in {445, 139})
            failed = [item for item in machine_rows if str(item.get("status", "")).upper() != "SUCCESS"]
            dns_rows = [item for item in machine_rows if item.get("dns_query")]
            nxdomain = [item for item in dns_rows if str(item.get("dns_response_code", "")).upper() == "NXDOMAIN"]
            domains = {item.get("dns_query") for item in dns_rows if item.get("dns_query")}
            intervals = []
            if len(timestamps) > 1:
                for left, right in zip(timestamps, timestamps[1:]):
                    intervals.append(max((right - left).total_seconds(), 0.0))
            overlap = 1
            for idx, start in enumerate(timestamps):
                current = 1
                left_end = start + timedelta(seconds=durations[idx] or 0)
                for jdx in range(idx + 1, len(timestamps)):
                    right = timestamps[jdx]
                    if right <= left_end:
                        current += 1
                overlap = max(overlap, current)
            total_connections = len(machine_rows)
            total_sent = sum(sent)
            total_received = sum(received)
            window_seconds = max((timestamps[-1] - timestamps[0]).total_seconds(), 1.0) if timestamps else 1.0
            burst_score = 0.0
            if timestamps and total_connections >= 8:
                bucket = Counter(ts.strftime("%Y-%m-%d %H:%M:%S") for ts in timestamps)
                average_bucket = total_connections / max(len(bucket), 1)
                burst_ratio = max(bucket.values()) / max(average_bucket, 1.0)
                burst_score = clamp((burst_ratio - 1.0) / 3.0, 0.0, 1.0)
            periodicity = 0.0
            if len(intervals) >= 4:
                mean_interval = statistics.mean(intervals)
                stdev_interval = statistics.pstdev(intervals) if len(intervals) > 1 else 0.0
                periodicity = clamp((1 - (stdev_interval / max(mean_interval, 1.0))) * 100)

            feature = {
                "machine_ip": machine_ip,
                "window_start": window_start.isoformat(),
                "total_connections": total_connections,
                "avg_duration": statistics.mean(durations) if durations else 0.0,
                "bytes_sent": total_sent,
                "bytes_received": total_received,
                "upload_download_ratio": total_sent / max(total_received, 1.0),
                "packets": sum(packets),
                "distinct_destination_ips": len(destinations),
                "distinct_ports": len(ports),
                "connection_frequency": total_connections / max(window_seconds, 1.0),
                "simultaneous_connections": overlap,
                "failed_connections": len(failed),
                "dns_requests": len(dns_rows),
                "dns_nxdomain_rate": len(nxdomain) / max(len(dns_rows), 1),
                "domain_diversity": len(domains),
                "dns_frequency": len(dns_rows) / max(window_seconds, 1.0),
                "mean_interconnection_time": statistics.mean(intervals) if intervals else float(WINDOW_MINUTES * 60),
                "periodicity": periodicity,
                "night_activity_ratio": sum(1 for ts in timestamps if ts.hour < 6 or ts.hour >= 22) / max(total_connections, 1),
                "traffic_burst_score": burst_score,
                "smb_connections": smb_connections,
            }
            features.append(feature)
        return sorted(features, key=lambda item: (item["machine_ip"], item["window_start"]))

    def normalize(self, features):
        stats = {key: median_iqr([feature[key] for feature in features]) for key in self.feature_keys}
        normalized = []
        for feature in features:
            current = dict(feature)
            for key in self.feature_keys:
                median, iqr = stats[key]
                current[f"{key}_norm"] = (feature[key] - median) / iqr
            normalized.append(current)
        return normalized

    def classify_activity(self, feature):
        if (
            feature["connection_frequency"] >= 0.4
            and feature["distinct_ports"] >= 4
            and feature["distinct_destination_ips"] >= 4
            and feature["failed_connections"] >= 4
        ):
            return "scanning"
        if (
            feature["packets"] > 100
            and feature["connection_frequency"] >= 0.5
            and feature["distinct_destination_ips"] <= 2
            and feature["distinct_ports"] <= 2
        ):
            return "DDoS"
        if feature["periodicity"] > 70 and feature["dns_nxdomain_rate"] > 0.3:
            return "C2 communication"
        if feature["upload_download_ratio"] > 3.0 and feature["bytes_sent"] > 6000:
            return "exfiltration"
        if feature.get("smb_connections", 0) > 2 and feature["distinct_destination_ips"] > 4:
            return "propagation"
        if feature["connection_frequency"] > 1.4 and feature["packets"] > 220:
            return "DDoS"
        return "normal"

    def explain(self, feature):
        explanations = []
        if feature["distinct_destination_ips"] >= 8:
            explanations.append("trop d'IP contactees")
        if feature["periodicity"] >= 70:
            explanations.append("pattern periodique detecte")
        if feature["dns_requests"] >= 5:
            explanations.append("nombre eleve de requetes DNS")
        if feature["distinct_ports"] >= 5:
            explanations.append("ports inhabituels")
        if feature["dns_nxdomain_rate"] >= 0.4:
            explanations.append("taux NXDOMAIN anormal")
        if feature["upload_download_ratio"] >= 2.5:
            explanations.append("ratio upload/download eleve")
        if feature["failed_connections"] >= 4:
            explanations.append("trop de connexions echouees")
        if feature["traffic_burst_score"] >= 0.45:
            explanations.append("bursts de trafic detectes")
        return explanations or ["profil reseau globalement stable"]

    def risk_score(self, feature):
        score = 0.0
        score += clamp(max(feature["distinct_destination_ips"] - 4, 0) * 4.0, 0, 18)
        score += clamp(max(feature["distinct_ports"] - 3, 0) * 4.0, 0, 16)
        score += clamp(max(feature["failed_connections"] - 2, 0) * 3.5, 0, 15)
        if feature["dns_requests"] >= 3:
            score += clamp(feature["dns_nxdomain_rate"] * 35, 0, 18)
        if feature["dns_requests"] >= 2 or feature["connection_frequency"] >= 0.4:
            score += clamp(max(feature["periodicity"] - 55, 0) * 0.28, 0, 14)
        if feature["upload_download_ratio"] >= 2.0 and feature["bytes_sent"] >= 5000:
            score += clamp((feature["upload_download_ratio"] - 1.5) * 7.0, 0, 14)
        if feature["total_connections"] >= 8:
            score += clamp(feature["traffic_burst_score"] * 10, 0, 10)
        if feature.get("smb_connections", 0) >= 3 and feature["distinct_destination_ips"] >= 4:
            score += 14
        if feature["packets"] >= 100 and feature["connection_frequency"] >= 0.5:
            score += clamp((feature["packets"] - 80) * 0.28, 0, 22)
        return round(clamp(score), 2)

    def class_from_score(self, score):
        if score >= 60:
            return "botnet"
        if score >= 30:
            return "suspect"
        return "normal"

    def severity(self, score):
        if score >= 60:
            return "critical"
        if score >= 30:
            return "warning"
        return "info"


class LiveFlowStore:
    def __init__(self):
        self.rows = []
        self.mode = "stopped"
        self.started_at = None
        self.lock = threading.Lock()
        self.collector = None
        self.demo = None
        self.source_label = "inactive"
        self.ingest_hint = "Aucune source configuree"
        self.last_error = ""

    def reset(self):
        with self.lock:
            self.rows = []
        self.last_error = ""

    def add_row(self, row):
        clean = dict(row)
        clean["timestamp"] = clean.get("timestamp") or casablanca_now().isoformat()
        with self.lock:
            self.rows.append(clean)
            cutoff = casablanca_now() - timedelta(minutes=LIVE_RETENTION_MINUTES)
            self.rows = [item for item in self.rows if iso_to_dt(item.get("timestamp")) >= cutoff]

    def add_rows(self, rows):
        for row in rows:
            self.add_row(row)

    def snapshot(self):
        with self.lock:
            return list(self.rows)

    def status(self):
        return {
            "mode": self.mode,
            "started_at": self.started_at,
            "row_count": len(self.snapshot()),
            "collector_running": bool(self.collector and self.collector.running),
            "demo_running": bool(self.demo and self.demo.running),
            "source_label": self.source_label,
            "ingest_hint": self.ingest_hint,
            "last_error": self.last_error,
        }


class DemoStream:
    def __init__(self, store, demo_rows):
        self.store = store
        self.demo_rows = list(demo_rows)
        self.running = False
        self.thread = None

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def _loop(self):
        idx = 0
        while self.running and self.demo_rows:
            row = dict(self.demo_rows[idx % len(self.demo_rows)])
            row["timestamp"] = casablanca_now().isoformat()
            self.store.add_row(row)
            idx += 1
            time.sleep(0.8)


class UdpJsonCollector:
    def __init__(self, store, host="127.0.0.1", port=5055):
        self.store = store
        self.host = host
        self.port = port
        self.running = False
        self.sock = None
        self.thread = None

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._listen, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass

    def _listen(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.host, self.port))
        self.sock.settimeout(1.0)
        while self.running:
            try:
                payload, _ = self.sock.recvfrom(65535)
            except (OSError, socket.timeout):
                continue
            try:
                row = json.loads(payload.decode("utf-8"))
                if isinstance(row, dict):
                    self.store.add_row(row)
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
