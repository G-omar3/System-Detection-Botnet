from ml_model.runtime import RUNTIME


def get_runtime():
    return RUNTIME


def train_and_save_model():
    runtime = get_runtime()
    return {
        "status": "ready",
        "pipeline": runtime.pipeline.metadata(),
    }


def analyze_rows(rows, config=None):
    return get_runtime().analyze_rows(rows, config or {})


def analyze_sample(config=None):
    return get_runtime().analyze_sample(config or {})


def analyze_live(config=None):
    return get_runtime().analyze_live(config or {})


def pipeline_metadata():
    return get_runtime().pipeline.metadata()
