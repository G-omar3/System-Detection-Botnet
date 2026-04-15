TRAFFIC_FEATURES = [
    "total_connections",
    "avg_duration",
    "bytes_sent",
    "bytes_received",
    "upload_download_ratio",
    "packets",
]


def extract(feature_row):
    return {key: feature_row.get(key) for key in TRAFFIC_FEATURES}

