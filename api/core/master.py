"""api/core/master.py — master parquet 로더 (공유 유틸)."""
from __future__ import annotations

import glob
import logging
from functools import lru_cache
from pathlib import Path

import pandas as pd

from config import PROCESSED_DIR

log = logging.getLogger("api.core.master")

_MASTER_PATH = PROCESSED_DIR / "master_full.parquet"

# ── 캐시된 master (프로세스 재시작 시 갱신) ──────────────────────────────────
_cached_master: pd.DataFrame | None = None
_cached_mtime: float = 0.0


def get_master(force_reload: bool = False) -> pd.DataFrame:
    """최신 master parquet을 로드한다.

    - master_full.parquet이 있으면 우선 사용 (파이프라인이 항상 최신으로 덮어씀)
    - 없으면 master_YYYY-MM-DD_YYYY-MM-DD.parquet 중 알파벳 마지막 파일 사용
    - mtime 기반 파일 변경 감지: 파일이 바뀌면 자동으로 재로드

    Returns:
        master DataFrame (빈 DataFrame이면 호출측에서 503 처리 권장)
    """
    global _cached_master, _cached_mtime

    path = _resolve_master_path()
    if path is None:
        log.error("master parquet 파일을 찾을 수 없음: %s", PROCESSED_DIR)
        return pd.DataFrame()

    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0

    if not force_reload and _cached_master is not None and mtime == _cached_mtime:
        return _cached_master

    try:
        df = pd.read_parquet(path)
        # 중복 인덱스 제거 (마지막 값 유지)
        dup_count = df.index.duplicated().sum()
        if dup_count:
            df = df[~df.index.duplicated(keep="last")]
            log.warning("master 중복 인덱스 %d개 제거", dup_count)
        # 날짜 오름차순 정렬
        df = df.sort_index()
        _cached_master = df
        _cached_mtime = mtime
        log.info("master 로드 완료: %s (%d rows x %d cols, latest=%s)",
                 path.name, *df.shape,
                 str(df.index[-1].date()) if not df.empty else "N/A")
        return df
    except Exception as e:
        log.error("master parquet 읽기 실패 (%s): %s", path, e)
        return pd.DataFrame()


def get_master_meta() -> dict:
    """master 데이터 신선도 메타정보."""
    path = _resolve_master_path()
    if path is None:
        return {"status": "no_data", "file": None}

    try:
        import time
        mtime = path.stat().st_mtime
        df = get_master()
        return {
            "status": "ok",
            "file": path.name,
            "rows": len(df),
            "columns": len(df.columns),
            "date_start": str(df.index[0].date()) if not df.empty else None,
            "date_end": str(df.index[-1].date()) if not df.empty else None,
            "file_updated_at": pd.Timestamp(mtime, unit="s").strftime("%Y-%m-%d %H:%M:%S"),
            "age_hours": round((time.time() - mtime) / 3600, 1),
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}


def _resolve_master_path() -> Path | None:
    """사용할 master parquet 경로 결정."""
    if _MASTER_PATH.exists():
        return _MASTER_PATH
    # 폴백: 날짜 기반 파일 중 알파벳 마지막
    files = sorted(glob.glob(str(PROCESSED_DIR / "master_*.parquet")))
    return Path(files[-1]) if files else None
