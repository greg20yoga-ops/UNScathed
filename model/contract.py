"""Satu-satunya tempat yang memetakan nama kolom internal -> KONTRAK DATA di README repo tim.
TODO(Yoga/Christian): samakan kanan (nilai) dengan kolom wajib di README kontrak data v1."""
COLUMN_MAP = {
    "timestamp": "timestamp",
    "pv_actual_w": "pv_actual_w",
    "pv_expected_w": "pv_expected_w",
    "alarm": "alarm",
    "cause_guess": "cause_guess",
    "loss_rp": "loss_rp",
}
EXTRA_COLUMNS = ["pv_expected_raw_w", "ratio", "alarm_threshold", "scenario", "fault_label", "data_source"]


def to_contract(df):
    out = df.rename(columns=COLUMN_MAP)
    return out
