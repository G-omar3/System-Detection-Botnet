DNS_FEATURES = [
    "dns_requests",
    "dns_nxdomain_rate",
    "domain_diversity",
    "dns_frequency",
]


def extract(feature_row):
    return {key: feature_row.get(key) for key in DNS_FEATURES}

