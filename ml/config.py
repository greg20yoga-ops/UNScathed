import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ML_DIR = ROOT / "ml"
PROCESSED_DIR = ROOT / "data" / "processed"
ARTIFACT_DIR = ML_DIR / "artifacts"
DEFAULT_SITE = "lareunion"


def load_config(site=DEFAULT_SITE):
    """Parameter umum + parameter lokasi. Nama lokasi bisa datang dari luar, jadi dibatasi."""
    if not re.fullmatch(r"[a-z0-9_-]+", site):
        raise ValueError(f"nama lokasi tidak valid: {site!r}")
    path = ML_DIR / "sites" / f"{site}.yaml"
    if not path.exists():
        raise ValueError(f"lokasi tidak dikenal: {site}")
    with open(ML_DIR / "config.yaml", encoding="utf-8") as f, open(path, encoding="utf-8") as g:
        return {**yaml.safe_load(f), **yaml.safe_load(g)}
