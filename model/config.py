from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_config(path=None):
    path = Path(path) if path else ROOT / "config.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def steps_per_hour(index):
    """Jumlah baris data per jam (hourly=1, 15 menit=4)."""
    dt = index.to_series().diff().dropna().dt.total_seconds().median()
    return max(1, int(round(3600 / dt)))
