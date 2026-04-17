"""
analysis/prediction.py

미국 전일 마감 데이터 → 당일 KOSPI 방향/갭 예측 모듈.

시간 관계:
  미국 시장 마감 (T일 오후 4시 ET = 한국 T+1일 오전 6시)
  → 국내 시장 개장 (T+1일 오전 9시 KST) 3시간 전 데이터 확보 가능
  → shift(1) 로 T일 신호 → T+1일 KOSPI 수익률 예측

주의:
  - lag=1 은 룩어헤드 바이어스가 없는 정당한 선행 관계
  - backtest.py 의 signal.shift(1) 과 동일 원리, 목적이 다름
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from collectors.base import get_logger

log = get_logger("analysis.prediction")

# 예측 로그 저장 경로
_PRED_LOG_PATH = Path(__file__).parent.parent / "data" / "processed" / "prediction_log.parquet"

# 기본 선행 변수 컬럼 (마스터에 존재하는 것만 사용)
_DEFAULT_FEATURE_COLS = [
    "us_sp500_close",
    "us_nasdaq_close",
    "rate_spread_10_2",
    "rate_hy_spread",
    "alt_vix_close",
    "fx_krw_usd_close",
    "sent_news_global",
    "crypto_btc_close",
]

_TARGET_COL = "kr_kospi_close"


# ---------------------------------------------------------------------------
# lag_correlation_rank
# ---------------------------------------------------------------------------

def lag_correlation_rank(
    master: pd.DataFrame,
    target: str = _TARGET_COL,
    lag: int = 1,
    top_n: int = 8,
) -> pd.DataFrame:
    """
    lag일 선행 상관관계 순위 반환.

    shift(lag) 를 feature 컬럼에 적용한 뒤 target 수익률과 Spearman 상관 계산.

    Args:
        master : master DataFrame
        target : 타겟 컬럼명
        lag    : 선행 일수 (1 = 전일)
        top_n  : 반환할 상위 n개
    Returns:
        DataFrame (columns: feature, spearman_rho, p_value, lag)
        절대값 기준 내림차순 정렬
    """
    if target not in master.columns:
        log.warning("lag_correlation_rank: target '%s' not in master", target)
        return pd.DataFrame()

    from scipy import stats

    from processors.merger import TARGET_COLS
    target_ret = master[target].pct_change(fill_method=None).dropna()
    candidates = [c for c in _DEFAULT_FEATURE_COLS
                  if c in master.columns and c != target and c not in TARGET_COLS]

    rows = []
    for col in candidates:
        feat_ret = master[col].pct_change(fill_method=None).shift(lag)
        combined = pd.concat([feat_ret.rename("feat"), target_ret.rename("target")], axis=1).dropna()
        if len(combined) < 30:
            continue
        rho, pval = stats.spearmanr(combined["feat"], combined["target"])
        rows.append({"feature": col, "spearman_rho": round(float(rho), 4),
                     "p_value": round(float(pval), 4), "lag": lag})

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["abs_rho"] = df["spearman_rho"].abs()
    df = df.sort_values("abs_rho", ascending=False).drop(columns="abs_rho")
    return df.head(top_n).reset_index(drop=True)


# ---------------------------------------------------------------------------
# majority_vote_signal
# ---------------------------------------------------------------------------

def majority_vote_signal(
    master: pd.DataFrame,
    feature_cols: list[str] | None = None,
    target: str = _TARGET_COL,
    lag: int = 1,
    top_n: int = 5,
) -> pd.Series:
    """
    상위 N개 선행 변수 수익률 부호 다수결 → 방향 신호.

    Returns:
        pd.Series (index=날짜, values: +1=상승, -1=하락, 0=중립)
    """
    if feature_cols is None:
        rank_df = lag_correlation_rank(master, target=target, lag=lag, top_n=top_n)
        if rank_df.empty:
            return pd.Series(dtype=float)
        feature_cols = rank_df["feature"].tolist()

    available = [c for c in feature_cols if c in master.columns]
    if not available:
        return pd.Series(dtype=float)

    # 전일 수익률 부호
    signs = pd.DataFrame({
        col: np.sign(master[col].pct_change(fill_method=None).shift(lag))
        for col in available
    })

    vote = signs.sum(axis=1)
    signal = pd.Series(0, index=vote.index, dtype=float)
    signal[vote > 0] = 1.0
    signal[vote < 0] = -1.0
    return signal


# ---------------------------------------------------------------------------
# rolling_logit_predict
# ---------------------------------------------------------------------------

def rolling_logit_predict(
    master: pd.DataFrame,
    feature_cols: list[str] | None = None,
    target: str = _TARGET_COL,
    lag: int = 1,
    window: int = 60,
) -> pd.DataFrame:
    """
    60일 롤링 LogisticRegression으로 KOSPI 상승 확률 예측.

    Args:
        master      : master DataFrame
        feature_cols: 선행 변수 컬럼 리스트
        target      : 타겟 컬럼
        lag         : 선행 일수
        window      : 롤링 학습 창 (일)
    Returns:
        DataFrame (columns: prob_up, predicted, actual)
        prob_up: 상승 확률 (0~1)
        predicted: +1/-1
        actual: 실제 방향 +1/-1
    """
    if target not in master.columns:
        log.warning("rolling_logit_predict: target '%s' not in master", target)
        return pd.DataFrame()

    if feature_cols is None:
        rank_df = lag_correlation_rank(master, target=target, lag=lag, top_n=5)
        feature_cols = rank_df["feature"].tolist() if not rank_df.empty else []

    available = [c for c in (feature_cols or []) if c in master.columns]
    if not available:
        log.warning("rolling_logit_predict: feature_cols 없음")
        return pd.DataFrame()

    try:
        import statsmodels.api as sm
    except ImportError:
        log.warning("statsmodels 미설치 — pip install statsmodels")
        return pd.DataFrame()

    # 피처 수익률 (lag 적용), 타겟 방향 (0/1)
    feats = pd.DataFrame({col: master[col].pct_change(fill_method=None) for col in available})
    target_ret = master[target].pct_change(fill_method=None)
    target_dir = (target_ret > 0).astype(int)

    # lag 적용: feats를 lag만큼 뒤로 밀어 T+lag 타겟과 정렬
    feats_lagged = feats.shift(lag)

    combined = pd.concat([feats_lagged, target_dir.rename("y"), target_ret.rename("ret")],
                         axis=1).dropna()

    if len(combined) < window + 10:
        log.warning("rolling_logit_predict: 데이터 부족 (%d행, window=%d)", len(combined), window)
        return pd.DataFrame()

    results = []
    for i in range(window, len(combined)):
        train = combined.iloc[i - window:i]
        test_row = combined.iloc[i:i + 1]

        X_train = sm.add_constant(train[available], has_constant="add")
        y_train = train["y"]

        try:
            model = sm.Logit(y_train, X_train).fit(disp=False, maxiter=100)
            X_test = sm.add_constant(test_row[available], has_constant="add")
            prob = float(model.predict(X_test).iloc[0])
        except Exception:
            prob = 0.5

        actual_dir = int(test_row["y"].iloc[0])
        results.append({
            "date": combined.index[i],
            "prob_up": round(prob, 4),
            "predicted": 1 if prob >= 0.5 else -1,
            "actual": 1 if actual_dir == 1 else -1,
        })

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results).set_index("date")
    df["hit"] = (df["predicted"] == df["actual"]).astype(int)
    log.info(
        "rolling_logit_predict: %d건 예측, 누적 적중률=%.1f%%",
        len(df), df["hit"].mean() * 100,
    )
    return df


# ---------------------------------------------------------------------------
# rolling_ols_gap
# ---------------------------------------------------------------------------

def rolling_ols_gap(
    master: pd.DataFrame,
    x_cols: list[str] | None = None,
    target: str = _TARGET_COL,
    lag: int = 1,
    window: int = 60,
) -> pd.DataFrame:
    """
    OLS 회귀로 KOSPI 갭(오버나이트 수익률) 예측.

    갭 = 당일 수익률 (open-to-open 없을 시 close-to-close 사용).

    Returns:
        DataFrame (columns: predicted_gap, actual_gap, r_squared)
    """
    if target not in master.columns:
        return pd.DataFrame()

    if x_cols is None:
        x_cols = ["us_sp500_close", "fx_krw_usd_close"]

    available = [c for c in x_cols if c in master.columns]
    if not available:
        return pd.DataFrame()

    try:
        import statsmodels.api as sm
    except ImportError:
        return pd.DataFrame()

    feats = pd.DataFrame({col: master[col].pct_change(fill_method=None) for col in available})
    target_ret = master[target].pct_change(fill_method=None)

    feats_lagged = feats.shift(lag)
    combined = pd.concat([feats_lagged, target_ret.rename("y")], axis=1).dropna()

    if len(combined) < window + 10:
        return pd.DataFrame()

    results = []
    for i in range(window, len(combined)):
        train = combined.iloc[i - window:i]
        test_row = combined.iloc[i:i + 1]

        X_train = sm.add_constant(train[available], has_constant="add")
        y_train = train["y"]

        try:
            model = sm.OLS(y_train, X_train).fit()
            X_test = sm.add_constant(test_row[available], has_constant="add")
            pred = float(model.predict(X_test).iloc[0])
            r2 = float(model.rsquared)
        except Exception:
            pred, r2 = 0.0, 0.0

        results.append({
            "date": combined.index[i],
            "predicted_gap": round(pred, 6),
            "actual_gap": round(float(test_row["y"].iloc[0]), 6),
            "r_squared": round(r2, 4),
        })

    if not results:
        return pd.DataFrame()

    return pd.DataFrame(results).set_index("date")


# ---------------------------------------------------------------------------
# 예측 로그 저장/불러오기
# ---------------------------------------------------------------------------

def save_prediction_log(
    date_str: str,
    prob_up: float,
    predicted: int,
    actual: int | None = None,
) -> None:
    """
    일별 예측 결과를 parquet 로그에 추가 저장.

    Args:
        date_str : 'YYYY-MM-DD'
        prob_up  : 상승 확률 (0~1)
        predicted: +1/-1
        actual   : 실제 방향 (+1/-1), 당일엔 None, 다음날 채움
    """
    _PRED_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    new_row = pd.DataFrame([{
        "date": pd.Timestamp(date_str),
        "prob_up": prob_up,
        "predicted": predicted,
        "actual": actual,
        "hit": int(predicted == actual) if actual is not None else None,
    }]).set_index("date")

    if _PRED_LOG_PATH.exists():
        existing = pd.read_parquet(_PRED_LOG_PATH)
        combined = pd.concat([existing, new_row])
        combined = combined[~combined.index.duplicated(keep="last")]
    else:
        combined = new_row

    combined.to_parquet(_PRED_LOG_PATH)
    log.info("예측 로그 저장: %s (prob_up=%.2f, predicted=%+d)", date_str, prob_up, predicted)


def load_prediction_log() -> pd.DataFrame:
    """
    예측 로그 불러오기 + 누적 적중률 컬럼 추가.

    Returns:
        DataFrame (index=date, columns: prob_up, predicted, actual, hit, cumulative_hit_rate)
    """
    if not _PRED_LOG_PATH.exists():
        return pd.DataFrame()

    df = pd.read_parquet(_PRED_LOG_PATH).sort_index()
    valid = df.dropna(subset=["hit"])
    if not valid.empty:
        df.loc[valid.index, "cumulative_hit_rate"] = (
            valid["hit"].expanding().mean()
        )
    return df


# ---------------------------------------------------------------------------
# 예측 빌드 (리포트에서 호출)
# ---------------------------------------------------------------------------

def build_today_prediction(
    master: pd.DataFrame,
    target: str = _TARGET_COL,
    lag: int = 1,
) -> dict:
    """
    오늘 날짜 기준 KOSPI 방향 예측 종합.

    Returns:
        {
            'signal'      : +1/-1/0  (다수결),
            'prob_up'     : float    (로지스틱, 없으면 None),
            'top_features': DataFrame (상관 순위),
            'vote_detail' : dict     (각 변수별 부호),
            'ref_date'    : str,
        }
    """
    ref_date = master.index[-1].strftime("%Y-%m-%d")

    top_features = lag_correlation_rank(master, target=target, lag=lag)
    signal = majority_vote_signal(master, target=target, lag=lag)
    today_signal = int(signal.iloc[-1]) if not signal.empty else 0

    # 로지스틱 확률 (마지막 값만 사용)
    prob_up = None
    try:
        logit_df = rolling_logit_predict(master, target=target, lag=lag, window=60)
        if not logit_df.empty:
            prob_up = float(logit_df["prob_up"].iloc[-1])
    except Exception as e:
        log.warning("로지스틱 예측 실패: %s", e)

    # 개별 변수 부호 상세 (표시 전용 — 신호 생성에 사용 금지)
    from processors.merger import TARGET_COLS
    vote_detail = {}
    feat_cols = top_features["feature"].tolist() if not top_features.empty else []
    for col in feat_cols:
        if col in TARGET_COLS:
            continue
        if col in master.columns:
            s = master[col].pct_change(fill_method=None).dropna()
            if not s.empty:
                vote_detail[col] = int(np.sign(s.iloc[-1]))

    return {
        "signal": today_signal,
        "prob_up": prob_up,
        "top_features": top_features,
        "vote_detail": vote_detail,
        "ref_date": ref_date,
    }
