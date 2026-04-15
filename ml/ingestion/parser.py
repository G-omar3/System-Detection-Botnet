from ml_model.core import Analyzer


def parse_csv_logs(csv_text):
    return Analyzer().load_rows(csv_text)

