"""File demo dashboard: satu unit per skenario, memakai jalur skor yang sama dengan alat IoT."""
import numpy as np
import pandas as pd

from ..data.prepare import load_processed
from ..detection.pipeline import score_unit
from . import faults

DEMO_START, DEMO_END = "2022-03-05", "2022-04-01"


def _aligned(trace, index, end):
    """Tempel rekaman baterai ke garis waktu unit: akhir rekaman jatuh pada waktu end."""
    shifted = trace.copy()
    shifted.index = end.ceil("h") - (trace.index.max() - trace.index)
    return shifted.reindex(index, method="nearest", tolerance=pd.Timedelta(minutes=30)).ffill().bfill()


def demo_file(test, control_peer, artifact, cfg):
    """Keluaran kontrak v1 untuk dashboard: satu unit per skenario pada periode uji."""
    healthy, weak = load_processed("bboxx_sehat_hourly.csv"), load_processed("bboxx_melemah_hourly.csv")
    rng = np.random.default_rng(cfg["faults"]["seed"])
    start = pd.Timestamp("2022-03-08 09:00", tz=cfg["site"]["tz"])

    def unit(frame, unit_id, fault_label=None, history=None):
        return score_unit(frame, artifact, cfg, unit_id, "lareunion", fault_label, history)

    def with_battery(frame, trace=healthy, end=None):
        return frame.join(_aligned(trace, frame.index, frame.index.max() if end is None else end))

    def injected(pattern, params, unit_id):
        frame, hit = faults.PATTERNS[pattern](test, start, cfg, rng, **params)
        labels = pd.Series(np.where(hit, pattern, "none"), index=test.index)
        frame = with_battery(frame)
        if pattern == "cable_cut":  # panel lepas: aki tidak terisi, jadi tidak ikut rekaman aslinya
            frame.loc[hit, "batt_i_a"] = frame.loc[hit, "batt_i_a"].clip(upper=0)
            frame.loc[hit, "batt_v"] = frame.loc[hit, "batt_v"].clip(upper=12.8)
        return unit(frame, unit_id, labels)

    removed = with_battery(test)
    gone = removed.index >= start
    removed.loc[gone, ["batt_v", "batt_i_a"]] = np.nan
    variants = cfg["faults"]["variants"]
    weak_end = start + pd.Timedelta(days=20)
    weak_history = weak.set_axis(weak_end.ceil("h") - (weak.index.max() - weak.index))
    units = [
        unit(with_battery(test), "PJU-demo-normal"),
        injected("cable_cut", variants["cable_cut"][1], "PJU-demo-kabel-putus"),
        injected("soiling", variants["soiling"][2], "PJU-demo-panel-kotor"),
        injected("partial_shading", variants["partial_shading"][1], "PJU-demo-bayangan"),
        injected("loose_connector", variants["loose_connector"][1], "PJU-demo-konektor-kendor"),
        unit(removed, "PJU-demo-baterai-dicabut", pd.Series(np.where(gone, "battery_removed", "none"), index=test.index)),
        unit(with_battery(test, weak, weak_end), "PJU-demo-baterai-melemah", history=weak_history),
        unit(with_battery(control_peer), "PJU-bayangan-nyata"),
    ]
    out = pd.concat(units, ignore_index=True)
    return out[out["timestamp"].between(DEMO_START, DEMO_END)]
