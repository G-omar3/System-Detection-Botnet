from ml.model.pipeline import get_runtime


def trigger_alert_logic(machines, alerts):
    return get_runtime().build_notifications(machines, alerts)
