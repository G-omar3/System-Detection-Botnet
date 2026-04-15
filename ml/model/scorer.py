from ml_model.core import Analyzer


def risk_score(feature_row):
    return Analyzer().risk_score(feature_row)

