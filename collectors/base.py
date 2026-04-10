import logging
import hashlib
from pathlib import Path
from datetime import date, datetime, timedelta

import pandas as pd

from config import CACHE_DIR, CACHE_EXPIRE_DAYS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")


def _cache_path(key: str) -> Path:
    h = hashlib.md5(key.encode()).hexdigest()[:12]
    return CACHE_DIR / f"{h}.parquet"


def load_cache(key: str) -> pd.DataFrame | None:
    p = _cache_path(key)
    if not p.exists():
        return None
    age = datetime.now() - datetime.fromtimestamp(p.stat().st_mtime)
    if age > timedelta(days=CACHE_EXPIRE_DAYS):
        return None
    return pd.read_parquet(p)


def save_cache(key: str, df: pd.DataFrame) -> None:
    p = _cache_path(key)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(p)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
