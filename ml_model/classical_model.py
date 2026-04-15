import numpy as np
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.preprocessing import StandardScaler


class ClassicalTrafficModel:
    feature_order = [
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

    def __init__(self):
        self.scaler = StandardScaler()
        self.anomaly_model = IsolationForest(
            n_estimators=180,
            contamination=0.18,
            random_state=42,
        )
        self.activity_model = RandomForestClassifier(
            n_estimators=220,
            max_depth=10,
            random_state=42,
        )
        self._train()

    def _row(self, label, noise=1.0):
        base = {
            "normal": [18, 0.9, 1800, 4200, 0.45, 70, 4, 3, 0.07, 2, 1, 4, 0.02, 4, 0.02, 55, 18, 0.10, 0.18],
            "scanning": [85, 0.2, 4200, 2300, 1.8, 160, 24, 16, 1.4, 9, 18, 1, 0.0, 1, 0.01, 3, 35, 0.25, 0.82],
            "C2 communication": [32, 0.15, 2200, 1500, 1.5, 88, 7, 4, 0.33, 3, 2, 14, 0.46, 12, 0.14, 12, 88, 0.82, 0.52],
            "exfiltration": [26, 1.3, 18500, 2600, 7.2, 115, 5, 3, 0.13, 2, 1, 2, 0.01, 2, 0.01, 75, 24, 0.35, 0.31],
            "propagation": [52, 0.35, 7600, 3900, 1.95, 140, 15, 7, 0.6, 6, 9, 2, 0.04, 2, 0.02, 8, 46, 0.24, 0.58],
            "DDoS": [160, 0.08, 14500, 7600, 1.9, 420, 14, 5, 2.6, 14, 4, 0, 0.0, 0, 0.0, 2, 28, 0.4, 0.95],
        }[label]
        spread = np.array([4, 0.2, 900, 1200, 0.6, 20, 3, 2, 0.15, 1.5, 2, 2, 0.06, 2, 0.03, 9, 10, 0.12, 0.08]) * noise
        return np.maximum(np.array(base) + np.random.normal(0, spread), 0.0)

    def _train(self):
        np.random.seed(42)
        x_train = []
        y_train = []
        for label, count in [
            ("normal", 180),
            ("scanning", 90),
            ("C2 communication", 95),
            ("exfiltration", 90),
            ("propagation", 90),
            ("DDoS", 85),
        ]:
            for _ in range(count):
                x_train.append(self._row(label))
                y_train.append(label)
        x_train = np.array(x_train)
        self.scaler.fit(x_train)
        scaled = self.scaler.transform(x_train)
        self.anomaly_model.fit(scaled)
        self.activity_model.fit(scaled, np.array(y_train))

    def _vectorize(self, feature):
        return np.array([[float(feature.get(name, 0.0)) for name in self.feature_order]])

    def _top_signals(self, feature):
        signal_map = []
        for key in self.feature_order:
            value = float(feature.get(key, 0.0))
            if key in {"bytes_sent", "bytes_received", "packets"}:
                score = min(value / 1000.0, 10.0)
            elif key in {"periodicity"}:
                score = value / 10.0
            elif key in {"dns_nxdomain_rate", "night_activity_ratio", "traffic_burst_score"}:
                score = value * 10.0
            else:
                score = value
            signal_map.append((key, score))
        signal_map.sort(key=lambda item: item[1], reverse=True)
        return [name for name, _ in signal_map[:4]]

    def predict(self, feature):
        vector = self._vectorize(feature)
        scaled = self.scaler.transform(vector)
        anomaly_raw = -self.anomaly_model.score_samples(scaled)[0]
        anomaly_score = max(min((anomaly_raw - 0.35) * 100, 100), 0)
        probabilities = self.activity_model.predict_proba(scaled)[0]
        labels = list(self.activity_model.classes_)
        best_idx = int(np.argmax(probabilities))
        activity_type = str(labels[best_idx])
        confidence = float(probabilities[best_idx])
        ml_score = anomaly_score * 0.6 + confidence * 40
        return {
            "risk_score": round(float(max(min(ml_score, 100), 0)), 2),
            "activity_type": activity_type,
            "confidence": round(confidence, 4),
            "anomaly_score": round(float(anomaly_score), 2),
            "model_name": "IsolationForest + RandomForestClassifier",
            "top_signals": self._top_signals(feature),
        }

    def metadata(self):
        return {
            "classical_ml": "IsolationForest + RandomForestClassifier",
            "training_mode": "synthetic behavioral profiles",
            "feature_count": len(self.feature_order),
        }
