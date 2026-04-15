TEMPORAL_FEATURES = [
    "mean_interconnection_time",
    "periodicity",
    "night_activity_ratio",
    "traffic_burst_score",
]


def extract(feature_row):
    return {key: feature_row.get(key) for key in TEMPORAL_FEATURES}

