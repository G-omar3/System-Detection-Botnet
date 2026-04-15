from ml_model.core import Analyzer


def group_by_ip_and_window(rows):
    return Analyzer().aggregate(rows)

