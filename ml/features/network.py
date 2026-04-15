NETWORK_FEATURES = [
    "distinct_destination_ips",
    "distinct_ports",
    "connection_frequency",
    "simultaneous_connections",
    "failed_connections",
]


def extract(feature_row):
    return {key: feature_row.get(key) for key in NETWORK_FEATURES}

