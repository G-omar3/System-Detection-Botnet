from dataclasses import dataclass


@dataclass
class HybridWeights:
    rules: float = 0.70
    classical_ml: float = 0.20
    deep_learning: float = 0.10


class HybridDecisionEngine:
    def __init__(self, analyzer, classical_model, deep_learning_model, weights=None):
        self.analyzer = analyzer
        self.classical_model = classical_model
        self.deep_learning_model = deep_learning_model
        self.weights = weights or HybridWeights()

    def combine_scores(self, rule_score, ml_score, dl_score):
        blended = (
            rule_score * self.weights.rules
            + ml_score * self.weights.classical_ml
            + dl_score * self.weights.deep_learning
        )
        return round(max(min(blended, 100), 0), 2)

    def infer(self, feature):
        rule_score = self.analyzer.risk_score(feature)
        rule_activity = self.analyzer.classify_activity(feature)
        ml = self.classical_model.predict(feature)
        dl = self.deep_learning_model.predict(feature)
        final_score = self.combine_scores(rule_score, ml["risk_score"], dl["risk_score"])
        final_class = self.analyzer.class_from_score(final_score)
        activity_type = ml["activity_type"] if ml["activity_type"] != "normal" else rule_activity
        if rule_activity != "normal" and rule_score >= 30:
            activity_type = rule_activity
        if activity_type == "normal" and final_class != "normal":
            activity_type = self._fallback_activity(feature)
        if activity_type == "C2 communication" and feature.get("dns_requests", 0) == 0:
            if feature.get("packets", 0) >= 100 and feature.get("connection_frequency", 0) >= 0.5:
                activity_type = "DDoS"
            elif feature.get("smb_connections", 0) >= 3:
                activity_type = "propagation"
            elif feature.get("bytes_sent", 0) >= 9000 and feature.get("upload_download_ratio", 0) >= 2.5:
                activity_type = "exfiltration"
            else:
                activity_type = rule_activity
        if final_score >= 60 and activity_type in {"C2 communication", "propagation", "exfiltration", "DDoS"}:
            final_class = "botnet"
        severity = self.analyzer.severity(final_score)
        if final_class == "botnet":
            severity = "critical"
        explanations = self._build_explanations(feature, activity_type, final_class, ml, dl)
        return {
            "risk_score": final_score,
            "primary_class": final_class,
            "activity_type": activity_type,
            "severity": severity,
            "explanations": explanations,
            "rule_score": round(rule_score, 2),
            "ml_score": ml["risk_score"],
            "dl_score": dl["risk_score"],
            "ml_model": ml,
            "deep_learning_model": dl,
        }

    def _fallback_activity(self, feature):
        if feature.get("packets", 0) >= 100 and feature.get("connection_frequency", 0) >= 0.5:
            return "DDoS"
        if feature.get("dns_requests", 0) >= 3 and feature.get("dns_nxdomain_rate", 0) >= 0.4:
            return "C2 communication"
        if feature.get("smb_connections", 0) >= 3 and feature.get("distinct_destination_ips", 0) >= 3:
            return "propagation"
        if feature.get("bytes_sent", 0) >= 9000 and feature.get("upload_download_ratio", 0) >= 2.5:
            return "exfiltration"
        if (
            feature.get("failed_connections", 0) >= 4
            and feature.get("distinct_ports", 0) >= 4
            and feature.get("distinct_destination_ips", 0) >= 4
        ):
            return "scanning"
        return "normal"

    def _build_explanations(self, feature, activity_type, final_class, ml, dl):
        mapped = {
            "distinct_destination_ips": "trop d'IP contactees",
            "distinct_ports": "ports inhabituels",
            "dns_nxdomain_rate": "taux NXDOMAIN anormal",
            "periodicity": "pattern periodique detecte",
            "upload_download_ratio": "ratio upload/download eleve",
            "connection_frequency": "frequence de connexions elevee",
            "bytes_sent": "volume sortant eleve",
            "failed_connections": "trop de connexions echouees",
            "traffic_burst_score": "bursts de trafic detectes",
            "dns_requests": "nombre eleve de requetes DNS",
        }
        if final_class == "normal" and activity_type == "normal":
            neutral = ["profil reseau normal", "aucun signal critique"]
            if feature.get("dns_requests", 0) > 0:
                neutral.append("activite DNS reguliere")
            return neutral[:3]
        explanations = []
        if activity_type != "normal":
            explanations.append(f"activite proche de {activity_type}")
        if dl["risk_score"] >= 45:
            explanations.append("anomalie comportementale supplementaire detectee")
        for signal in ml.get("top_signals", []):
            label = mapped.get(signal)
            if label and label not in explanations:
                explanations.append(label)
        for rule_explanation in self.analyzer.explain(feature):
            if rule_explanation not in explanations:
                explanations.append(rule_explanation)
        return explanations[:6]

    def metadata(self):
        return {
            "strategy": "hybrid",
            "weights": {
                "rules": self.weights.rules,
                "classical_ml": self.weights.classical_ml,
                "deep_learning": self.weights.deep_learning,
            },
            "classical": self.classical_model.metadata(),
            "deep_learning": self.deep_learning_model.metadata(),
        }
