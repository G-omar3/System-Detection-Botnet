import csv
import io
from pathlib import Path
from zoneinfo import ZoneInfo

from .autoencoder_model import TrafficAutoencoderModel
from .classical_model import ClassicalTrafficModel
from .core import (
    Analyzer,
    DATA_DIR,
    DEFAULT_LOG,
    LiveFlowStore,
    UdpJsonCollector,
    build_pdf_document,
    floor_window,
    iso_to_dt,
    minimal_pdf,
)
from .hybrid_pipeline import HybridDecisionEngine


BASE_DIR = Path(__file__).resolve().parent.parent
REPORT_TEMPLATE = BASE_DIR / "dashboard" / "templates" / "dashboard" / "report_template.txt"
CASABLANCA_TZ = ZoneInfo("Africa/Casablanca")


class SocRuntime:
    def __init__(self):
        self.analyzer = Analyzer()
        self.classical_model = ClassicalTrafficModel()
        self.deep_learning_model = TrafficAutoencoderModel(self.classical_model.feature_order)
        self.pipeline = HybridDecisionEngine(self.analyzer, self.classical_model, self.deep_learning_model)
        self.live_store = LiveFlowStore()

    def load_sample_csv(self):
        return DEFAULT_LOG.read_text(encoding="utf-8") if DEFAULT_LOG.exists() else ""

    def _counter(self, machines, predicate):
        return sum(1 for machine in machines if predicate(machine))

    def _attack_counter(self, machines):
        counter = {}
        for machine in machines:
            label = str(machine["activity_type"])
            counter[label] = counter.get(label, 0) + 1
        return counter

    def casablanca_time(self, value):
        current = iso_to_dt(value)
        if current.tzinfo is None:
            return current.replace(tzinfo=CASABLANCA_TZ)
        return current.astimezone(CASABLANCA_TZ)

    def build_timeline(self, rows, machines):
        machine_index = {
            (machine["machine_ip"], floor_window(self.casablanca_time(machine["window_start"]))): machine
            for machine in machines
        }
        buckets = {}
        for row in rows:
            timestamp = self.casablanca_time(row.get("timestamp"))
            minute_bucket = timestamp.replace(second=0, microsecond=0)
            bucket_key = minute_bucket.isoformat(timespec="minutes")
            current = buckets.setdefault(
                bucket_key,
                {
                    "timestamp": bucket_key,
                    "events": 0,
                    "bytes_sent": 0.0,
                    "bytes_received": 0.0,
                    "dns_events": 0,
                    "failed_events": 0,
                    "machines": set(),
                    "alert_machines": set(),
                    "normal_machines": set(),
                    "suspect_machines": set(),
                    "botnet_machines": set(),
                    "risk_by_machine": {},
                },
            )
            machine_ip = row.get("src_ip") or "unknown"
            current["events"] += 1
            current["bytes_sent"] += float(row.get("bytes_sent") or 0.0)
            current["bytes_received"] += float(row.get("bytes_received") or 0.0)
            current["machines"].add(machine_ip)
            if row.get("dns_query"):
                current["dns_events"] += 1
            if str(row.get("status", "")).upper() != "SUCCESS":
                current["failed_events"] += 1

            machine = machine_index.get((machine_ip, floor_window(timestamp)))
            if not machine:
                continue
            current["risk_by_machine"][machine_ip] = float(machine["risk_score"])
            if machine["is_alert"]:
                current["alert_machines"].add(machine_ip)
            primary_class = machine["primary_class"]
            if primary_class == "botnet":
                current["botnet_machines"].add(machine_ip)
            elif primary_class == "suspect":
                current["suspect_machines"].add(machine_ip)
            else:
                current["normal_machines"].add(machine_ip)

        timeline = []
        for _, bucket in sorted(buckets.items()):
            risks = list(bucket["risk_by_machine"].values())
            timeline.append(
                {
                    "timestamp": bucket["timestamp"],
                    "events": bucket["events"],
                    "active_machines": len(bucket["machines"]),
                    "average_risk": round(sum(risks) / max(len(risks), 1), 2),
                    "max_risk": round(max(risks), 2) if risks else 0.0,
                    "alert_machines": len(bucket["alert_machines"]),
                    "normal_machines": len(bucket["normal_machines"]),
                    "suspect_machines": len(bucket["suspect_machines"]),
                    "botnet_machines": len(bucket["botnet_machines"]),
                    "dns_events": bucket["dns_events"],
                    "failed_events": bucket["failed_events"],
                    "bytes_sent": round(bucket["bytes_sent"], 2),
                    "bytes_received": round(bucket["bytes_received"], 2),
                }
            )
        return timeline

    def analyze_rows(self, rows, config=None):
        config = config or {}
        threshold = float(config.get("threshold", 40))
        features = self.analyzer.aggregate(rows)
        machines = []
        for feature in features:
            prediction = self.pipeline.infer(feature)
            machine = dict(feature)
            machine.update(prediction)
            machine["is_alert"] = machine["severity"] != "info" or machine["risk_score"] >= threshold
            machines.append(machine)
        machines.sort(key=lambda item: item["risk_score"], reverse=True)

        alerts = []
        for machine in machines:
            if not machine["is_alert"]:
                continue
            alerts.append(
                {
                    "machine_ip": machine["machine_ip"],
                    "timestamp": machine["window_start"],
                    "type": machine["activity_type"],
                    "score": machine["risk_score"],
                    "severity": machine["severity"],
                    "justification": ", ".join(machine["explanations"][:3]),
                }
            )

        summary = {
            "machine_count": len(machines),
            "alert_count": len(alerts),
            "critical_count": self._counter(machines, lambda item: item["severity"] == "critical"),
            "suspect_count": self._counter(machines, lambda item: item["primary_class"] == "suspect"),
            "normal_count": self._counter(machines, lambda item: item["primary_class"] == "normal"),
            "attack_types": self._attack_counter(machines),
            "ml_model": self.pipeline.metadata(),
        }
        notifications = self.build_notifications(machines, alerts)
        timeline = self.build_timeline(rows, machines)
        return {
            "summary": summary,
            "machines": machines,
            "alerts": alerts,
            "notifications": notifications,
            "timeline": timeline,
        }

    def build_notifications(self, machines, alerts):
        notifications = []
        if machines:
            top = machines[0]
            notifications.append(
                {
                    "level": top["severity"],
                    "title": "Machine prioritaire",
                    "message": f"{top['machine_ip']} score {top['risk_score']} - {top['activity_type']}",
                    "key": f"priority-{top['machine_ip']}-{top['window_start']}",
                }
            )
        for alert in alerts[:4]:
            notifications.append(
                {
                    "level": alert["severity"],
                    "title": "Alerte reseau",
                    "message": f"{alert['machine_ip']} - {alert['type']} - {alert['justification']}",
                    "key": f"alert-{alert['machine_ip']}-{alert['timestamp']}",
                }
            )
        if any(machine["activity_type"] == "C2 communication" for machine in machines):
            notifications.append(
                {
                    "level": "critical",
                    "title": "C2 suspecte",
                    "message": "Un comportement de beaconing periodique a ete detecte.",
                    "key": "c2-detected",
                }
            )
        if any(machine["activity_type"] == "exfiltration" for machine in machines):
            notifications.append(
                {
                    "level": "warning",
                    "title": "Exfiltration suspectee",
                    "message": "Un volume sortant eleve a ete observe sur au moins une machine.",
                    "key": "exfiltration-detected",
                }
            )
        if not alerts:
            notifications.append(
                {
                    "level": "info",
                    "title": "Aucune alerte critique",
                    "message": "Le lot analyse ne contient pas de machine au-dessus du seuil.",
                    "key": "no-alerts",
                }
            )
        return notifications

    def analyze_sample(self, config=None):
        rows = self.analyzer.load_rows(self.load_sample_csv())
        return self.analyze_rows(rows, config or {})

    def analyze_live(self, config=None):
        rows = self.live_store.snapshot()
        return self.analyze_rows(rows, config or {})

    def start_live(self, mode="demo", host="127.0.0.1", port=5055):
        self.stop_live()
        normalized_mode = (mode or "http").lower()
        self.live_store.mode = normalized_mode
        self.live_store.started_at = "active"
        self.live_store.last_error = ""
        passive_sources = {
            "http": ("HTTP API", "Envoyer les evenements vers /api/live/ingest"),
            "zeek": ("Zeek JSON", "Convertir les logs Zeek puis envoyer vers /api/live/ingest"),
            "suricata": ("Suricata EVE", "Mapper les logs EVE JSON puis envoyer vers /api/live/ingest"),
            "tshark": ("tshark", "Transformer la capture en JSON puis pousser vers /api/live/ingest"),
            "netflow": ("NetFlow / Firewall", "Convertir les flows et pousser vers /api/live/ingest"),
        }
        if normalized_mode == "udp":
            try:
                collector = UdpJsonCollector(self.live_store, host=host, port=port)
                collector.start()
                self.live_store.collector = collector
                self.live_store.source_label = "UDP collector"
                self.live_store.ingest_hint = f"Envoyer les evenements JSON en UDP vers {host}:{port}"
            except OSError as exc:
                self.live_store.mode = "stopped"
                self.live_store.last_error = str(exc)
                self.live_store.source_label = "erreur"
                self.live_store.ingest_hint = "Impossible de demarrer le collector UDP"
        else:
            label, hint = passive_sources.get(normalized_mode, passive_sources["http"])
            self.live_store.source_label = label
            self.live_store.ingest_hint = hint
        return self.live_store.status()

    def stop_live(self):
        if self.live_store.collector:
            self.live_store.collector.stop()
        if self.live_store.demo:
            self.live_store.demo.stop()
        self.live_store.collector = None
        self.live_store.demo = None
        self.live_store.mode = "stopped"
        self.live_store.started_at = None
        self.live_store.source_label = "inactive"
        self.live_store.ingest_hint = "Aucune source configuree"
        return self.live_store.status()

    def reset_live(self):
        self.stop_live()
        self.live_store.reset()
        return self.live_store.status()

    def export_csv(self, result):
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["machine_ip", "window_start", "primary_class", "activity_type", "risk_score", "severity", "explanations"])
        for machine in result["machines"]:
            writer.writerow(
                [
                    machine["machine_ip"],
                    machine["window_start"],
                    machine["primary_class"],
                    machine["activity_type"],
                    machine["risk_score"],
                    machine["severity"],
                    " | ".join(machine["explanations"]),
                ]
            )
        return buffer.getvalue()

    def build_report_lines(self, result):
        summary = result["summary"]
        notifications = "\n".join(
            f"- [{item['level']}] {item['title']}: {item['message']}" for item in result["notifications"][:6]
        ) or "- Aucune notification"
        machines = "\n".join(
            f"- {machine['machine_ip']} | score {machine['risk_score']} | {machine['activity_type']} | {', '.join(machine['explanations'][:3])}"
            for machine in result["machines"][:6]
        )
        attack_types = ", ".join(f"{key}: {value}" for key, value in summary["attack_types"].items()) or "aucun"
        if REPORT_TEMPLATE.exists():
            text = REPORT_TEMPLATE.read_text(encoding="utf-8").format(
                machine_count=summary["machine_count"],
                alert_count=summary["alert_count"],
                critical_count=summary["critical_count"],
                suspect_count=summary["suspect_count"],
                attack_types=attack_types,
                notifications=notifications,
                machines=machines or "- Aucune machine",
            )
            return text.splitlines()
        return [
            "NetWatch SOC - Rapport du projet",
            "",
            f"Machines analysees: {summary['machine_count']}",
            f"Alertes: {summary['alert_count']}",
            f"Critiques: {summary['critical_count']}",
            f"Suspectes: {summary['suspect_count']}",
        ]

    def export_pdf(self, result):
        return self.export_template_pdf(result)

    def _pdf_text(self, x, y, text, font="F1", size=9, color=(0.1098, 0.1569, 0.2)):
        safe = str(text).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        return f"BT /{font} {size} Tf {color[0]} {color[1]} {color[2]} rg 1 0 0 1 {x} {y} Tm ({safe}) Tj ET\n"

    def _pdf_rect(self, x, y, w, h, fill, stroke=None, line_width=1):
        commands = []
        if stroke:
            commands.append(f"{line_width} w {stroke[0]} {stroke[1]} {stroke[2]} RG")
        commands.append(f"{fill[0]} {fill[1]} {fill[2]} rg")
        commands.append(f"n {x} {y} {w} {h} re B*" if stroke else f"n {x} {y} {w} {h} re f*")
        return "\n".join(commands) + "\n"

    def _level_label(self, score):
        if score >= 70:
            return "ELEVE", (0.2039, 0.3725, 0.6039)
        if score >= 30:
            return "MOYEN", (0.3176, 0.4824, 0.6941)
        return "FAIBLE", (0.4431, 0.5882, 0.7608)

    def _template_page_header(self, page_number):
        stream = ""
        stream += self._pdf_text(518.9, 22.6, f"Page {page_number}", size=8, color=(0.3647, 0.4275, 0.4941))
        if page_number == 1:
            stream += self._pdf_rect(57.02362, 727.5433, 493.2283, 80, (0.9569, 0.9725, 0.9922))
            stream += self._pdf_rect(57.02362, 727.5433, 5, 80, (0.4471, 0.6039, 0.7961))
            stream += self._pdf_text(77.0, 772.5, "SOC BOTNET ANALYZER", font="F2", size=22, color=(0.149, 0.2196, 0.3333))
            stream += self._pdf_text(
                77.0,
                755.5,
                "Rapport d'analyse de securite - Centre des operations de securite",
                size=10,
                color=(0.4039, 0.4824, 0.5961),
            )
            stream += self._pdf_text(404.0, 786.0, "02 April 2026  |  NetWatch SOC", size=9, color=(0.4039, 0.4824, 0.5961))
            stream += self._pdf_text(434.0, 772.0, "CONFIDENTIEL", font="F2", size=9, color=(0.3176, 0.4824, 0.6941))
        return stream

    def _template_metric_card(self, x, y, value, label, accent):
        stream = self._pdf_rect(x, y, 107.7, 82, (0.9412, 0.9529, 0.9725))
        stream += self._pdf_text(x + 6, y + 42, value, font="F2", size=26, color=accent)
        stream += self._pdf_text(x + 6, y + 10, label, font="F2", size=7, color=(0.3647, 0.4275, 0.4941))
        return stream

    def _template_machine_card(self, x, y, machine):
        label, level_color = self._level_label(machine["risk_score"])
        score_text = f"{machine['risk_score']:.1f}"
        justif = ", ".join(machine["explanations"][:2]) or "aucune observation"
        if len(justif) > 92:
            justif = justif[:89] + "..."
        stream = self._pdf_rect(x, y, 481.2283, 96, (0.9412, 0.9529, 0.9725))
        stream += self._pdf_text(x + 16, y + 72, machine["machine_ip"], font="F2", size=10, color=(0.2039, 0.3725, 0.6039))
        stream += self._pdf_text(x + 16, y + 56, f"Statut: {machine['primary_class'].upper()}", font="F1", size=8, color=(0.3647, 0.4275, 0.4941))
        stream += self._pdf_text(x + 16, y + 40, f"Menace: {str(machine['activity_type']).upper()}", font="F1", size=8, color=(0.3647, 0.4275, 0.4941))
        stream += self._pdf_text(x + 16, y + 18, f"Justification: {justif}", font="F1", size=8, color=(0.3647, 0.4275, 0.4941))
        stream += self._pdf_rect(x + 411.9, y + 10, 62.36, 50, (0.973, 0.979, 0.989))
        stream += self._pdf_text(x + 425.5, y + 34, score_text, font="F2", size=18, color=level_color)
        stream += self._pdf_text(x + 425.0, y + 14, "SCORE", size=7, color=(0.3647, 0.4275, 0.4941))
        stream += self._pdf_rect(x + 411.9, y + 2, 62.36, 18, level_color)
        stream += self._pdf_text(x + 428.0, y + 8, label, font="F2", size=7, color=(1, 1, 1))
        return stream

    def export_template_pdf(self, result):
        summary = result["summary"]
        machines = result["machines"][:6]
        notifications = result["notifications"][:4]
        p1 = self._template_page_header(1)
        p1 += self._pdf_text(57.0, 687.5, "RESUME EXECUTIF", font="F2", size=12)
        p1 += "1 w 0.8353 0.8471 0.8627 RG n 57.0 680.5 m 538.2 680.5 l S\n"
        p1 += self._template_metric_card(52.5, 589.5, str(summary["machine_count"]), "MACHINES ANALYSEES", (0.2039, 0.3725, 0.6039))
        p1 += self._template_metric_card(180.0, 589.5, str(summary["suspect_count"] + summary["critical_count"]), "MACHINES SUSPECTES", (0.3176, 0.4824, 0.6941))
        p1 += self._template_metric_card(307.6, 589.5, str(summary["critical_count"]), "MACHINES CRITIQUES", (0.2039, 0.3725, 0.6039))
        p1 += self._template_metric_card(435.2, 589.5, str(summary["alert_count"]), "ALERTES GENEREES", (0.3176, 0.4824, 0.6941))
        p1 += self._pdf_text(57.0, 546.5, "OBSERVATIONS PRINCIPALES", font="F2", size=12)
        p1 += "1 w 0.8353 0.8471 0.8627 RG n 57.0 539.5 m 538.2 539.5 l S\n"
        p1 += self._pdf_rect(57.0, 399.5, 481.2, 134, (0.9412, 0.9529, 0.9725))
        row_y = [503.5, 459.5, 429.5, 399.5]
        row_colors = [(0.9725, 0.9804, 0.9922), (0.9412, 0.9529, 0.9725), (0.9725, 0.9804, 0.9922), (0.9412, 0.9529, 0.9725)]
        for idx in range(4):
            p1 += self._pdf_rect(57.0, row_y[idx], 481.2, 30 if idx != 1 else 44, row_colors[idx])
        default_messages = [
            "Machine prioritaire detectee : aucune machine disponible.",
            "Communication suspecte : aucun signal periodique critique.",
            "Risque d'exfiltration : aucun volume sortant critique detecte.",
            "Aucune alerte active : le seuil courant n'a declenche aucune alerte critique.",
        ]
        for idx, note in enumerate(notifications):
            default_messages[idx] = f"{note['title']} : {note['message']}"
        colors = [(0.2039, 0.3725, 0.6039), (0.3176, 0.4824, 0.6941), (0.2039, 0.3725, 0.6039), (0.4431, 0.5882, 0.7608)]
        text_y = [511.5, 468.5, 437.5, 407.5]
        for idx, message in enumerate(default_messages):
            text = message if len(message) < 102 else message[:99] + "..."
            p1 += self._pdf_text(65.0, text_y[idx], "!", font="F2", size=14, color=colors[idx])
            p1 += self._pdf_text(93.0, text_y[idx], text, size=9)
        p1 += self._pdf_text(57.0, 359.5, "MACHINES PRIORITAIRES", font="F2", size=12)
        p1 += "1 w 0.8353 0.8471 0.8627 RG n 57.0 352.5 m 538.2 352.5 l S\n"
        for idx, machine in enumerate(machines[:2]):
            p1 += self._template_machine_card(57.0, 250.5 - (idx * 102), machine)

        p2 = self._template_page_header(2)
        for idx, machine in enumerate(machines[2:6]):
            p2 += self._template_machine_card(57.0, 711.5 - (idx * 102), machine)
        p2 += self._pdf_text(57.0, 263.5, "PILE DE DETECTION", font="F2", size=12)
        p2 += "1 w 0.8353 0.8471 0.8627 RG n 57.0 256.5 m 538.2 256.5 l S\n"
        p2 += self._pdf_rect(57.0, 138.5, 481.2, 112, (0.9412, 0.9529, 0.9725))
        rows = [
            ("Regles comportementales", "Signatures et seuils definis pour le comportement reseau"),
            ("IsolationForest", "Detection d'anomalies non supervisee par isolement d'instances"),
            ("RandomForestClassifier", "Classification supervisee des comportements observes"),
            ("Autoencoder (DNN)", "Detection d'ecarts de reconstruction sur les profils de trafic"),
        ]
        for idx, (left, right) in enumerate(rows):
            y = 230.5 - (idx * 28)
            if idx % 2 == 0:
                p2 += self._pdf_rect(57.0, y - 8, 481.2, 28, (0.9725, 0.9804, 0.9922))
            p2 += self._pdf_text(67.0, y, left, font="F2", size=9, color=(0.2039, 0.3725, 0.6039))
            p2 += self._pdf_text(222.9, y, right, size=8, color=(0.3647, 0.4275, 0.4941))
        return build_pdf_document([p1, p2])


RUNTIME = SocRuntime()
