import os

import numpy as np

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

import tensorflow as tf


class TrafficAutoencoderModel:
    def __init__(self, feature_order):
        self.feature_order = list(feature_order)
        self.model = None
        self.mean = None
        self.std = None
        self.threshold = None
        self.enabled = True
        self._train()

    def _generate_normal_samples(self):
        np.random.seed(7)
        rows = []
        for _ in range(280):
            rows.append(
                [
                    np.random.normal(20, 4),
                    abs(np.random.normal(1.0, 0.25)),
                    abs(np.random.normal(2200, 650)),
                    abs(np.random.normal(4100, 900)),
                    abs(np.random.normal(0.6, 0.2)),
                    abs(np.random.normal(85, 18)),
                    abs(np.random.normal(4, 1.4)),
                    abs(np.random.normal(3, 1.1)),
                    abs(np.random.normal(0.08, 0.03)),
                    abs(np.random.normal(2, 0.6)),
                    abs(np.random.normal(1, 0.8)),
                    abs(np.random.normal(4, 1.5)),
                    abs(np.random.normal(0.03, 0.02)),
                    abs(np.random.normal(4, 1.4)),
                    abs(np.random.normal(0.02, 0.01)),
                    abs(np.random.normal(60, 12)),
                    abs(np.random.normal(20, 7)),
                    abs(np.random.normal(0.1, 0.05)),
                    abs(np.random.normal(0.2, 0.08)),
                ]
            )
        return np.array(rows, dtype=np.float32)

    def _train(self):
        try:
            tf.random.set_seed(7)
            x_train = self._generate_normal_samples()
            self.mean = x_train.mean(axis=0)
            self.std = np.where(x_train.std(axis=0) < 1e-6, 1.0, x_train.std(axis=0))
            x_scaled = (x_train - self.mean) / self.std

            inputs = tf.keras.Input(shape=(len(self.feature_order),))
            encoded = tf.keras.layers.Dense(12, activation="relu")(inputs)
            encoded = tf.keras.layers.Dense(6, activation="relu")(encoded)
            decoded = tf.keras.layers.Dense(12, activation="relu")(encoded)
            outputs = tf.keras.layers.Dense(len(self.feature_order), activation="linear")(decoded)
            self.model = tf.keras.Model(inputs, outputs)
            self.model.compile(optimizer="adam", loss="mse")
            self.model.fit(x_scaled, x_scaled, epochs=6, batch_size=32, verbose=0)

            recon = self.model.predict(x_scaled, verbose=0)
            errors = np.mean(np.square(x_scaled - recon), axis=1)
            self.threshold = float(np.percentile(errors, 95))
        except Exception:
            self.enabled = False
            self.model = None
            self.mean = None
            self.std = None
            self.threshold = None

    def predict(self, feature):
        if not self.enabled or self.model is None:
            return {
                "reconstruction_error": 0.0,
                "threshold_ratio": 0.0,
                "risk_score": 0.0,
                "model_name": "Dense Autoencoder disabled",
            }
        vector = np.array([[float(feature.get(name, 0.0)) for name in self.feature_order]], dtype=np.float32)
        scaled = (vector - self.mean) / self.std
        recon = self.model.predict(scaled, verbose=0)
        error = float(np.mean(np.square(scaled - recon)))
        ratio = error / max(self.threshold, 1e-6)
        risk_score = max(min((ratio - 6.0) * 7.5, 100), 0)
        return {
            "reconstruction_error": round(error, 5),
            "threshold_ratio": round(ratio, 4),
            "risk_score": round(float(risk_score), 2),
            "model_name": "Dense Autoencoder",
        }

    def metadata(self):
        return {
            "deep_learning": "Dense Autoencoder",
            "enabled": self.enabled,
            "feature_count": len(self.feature_order),
        }
