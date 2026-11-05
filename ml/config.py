from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ML_DIR = ROOT / "ml"
PROCESSED_DIR = ROOT / "data" / "processed"
ARTIFACT_DIR = ML_DIR / "artifacts"


def load_config(path=None):
    with open(path or ML_DIR / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)
