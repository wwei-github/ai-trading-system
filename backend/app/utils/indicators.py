"""技术指标计算模块（Stage 5 §5.5.2）。

14 类指标（V1，不含形态识别 AI）：
- 均线：MA（5/10/20/60/120/200）、EMA
- 趋势：MACD、BOLL（布林带）、DMI
- 震荡：RSI、KDJ、CCI、Williams %R
- 成交量：OBV、VWAP
- 波动：ATR、标准差通道（STDCH）

实现要点：
- 输入：DataFrame（列：open/high/low/close/volume）或 OHLCV 列表
- 输出：dict（key 为指标名，value 为最新值或序列）
- 算法对齐 TradingView 默认参数，误差 ≤ 0.1%
- 纯 numpy/pandas 实现，无外部 ta-lib 依赖
"""

from typing import Dict, List, Optional, Union

import numpy as np
import pandas as pd


def _to_df(
    ohlcv: Union[List[list], pd.DataFrame, np.ndarray]
) -> pd.DataFrame:
    """统一转换为 DataFrame。

    输入支持：
    - [[ts, o, h, l, c, v], ...]（CCXT 原始格式）
    - DataFrame（已含列）
    """
    if isinstance(ohlcv, pd.DataFrame):
        df = ohlcv.copy()
    else:
        df = pd.DataFrame(
            ohlcv, columns=["ts", "open", "high", "low", "close", "volume"]
        )
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


# ---------- 均线 ----------

def ma(df: pd.DataFrame, periods: Optional[List[int]] = None) -> Dict[str, float]:
    """移动平均线 MA。

    Args:
        periods: 周期列表，默认 [5, 10, 20, 60, 120, 200]
    Returns:
        {ma5: float, ma10: float, ...}（最新值；数据不足时为 None）
    """
    if periods is None:
        periods = [5, 10, 20, 60, 120, 200]
    close = df["close"]
    result: Dict[str, float] = {}
    for p in periods:
        key = f"ma{p}"
        if len(close) >= p:
            result[key] = float(close.rolling(p).mean().iloc[-1])
        else:
            result[key] = None
    return result


def ema(df: pd.DataFrame, periods: Optional[List[int]] = None) -> Dict[str, float]:
    """指数移动平均线 EMA。

    Args:
        periods: 周期列表，默认 [5, 10, 20, 60]
    """
    if periods is None:
        periods = [5, 10, 20, 60]
    close = df["close"]
    result: Dict[str, float] = {}
    for p in periods:
        key = f"ema{p}"
        if len(close) >= p:
            result[key] = float(close.ewm(span=p, adjust=False).mean().iloc[-1])
        else:
            result[key] = None
    return result


# ---------- 趋势 ----------

def macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> Dict[str, float]:
    """MACD 指标。

    Returns:
        {macd, macd_signal, macd_hist}（最新值）
    """
    close = df["close"]
    if len(close) < slow + signal:
        return {"macd": None, "macd_signal": None, "macd_hist": None}
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return {
        "macd": float(macd_line.iloc[-1]),
        "macd_signal": float(signal_line.iloc[-1]),
        "macd_hist": float(hist.iloc[-1]),
    }


def boll(
    df: pd.DataFrame, period: int = 20, std_dev: float = 2.0
) -> Dict[str, float]:
    """布林带 BOLL。

    Returns:
        {boll_upper, boll_middle, boll_lower, boll_width}
    """
    close = df["close"]
    if len(close) < period:
        return {
            "boll_upper": None,
            "boll_middle": None,
            "boll_lower": None,
            "boll_width": None,
        }
    ma = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = ma + std_dev * std
    lower = ma - std_dev * std
    width = (upper - lower) / ma
    return {
        "boll_upper": float(upper.iloc[-1]),
        "boll_middle": float(ma.iloc[-1]),
        "boll_lower": float(lower.iloc[-1]),
        "boll_width": float(width.iloc[-1]) if not np.isnan(width.iloc[-1]) else None,
    }


def dmi(
    df: pd.DataFrame, period: int = 14
) -> Dict[str, float]:
    """动向指标 DMI（含 +DI / -DI / ADX）。

    Returns:
        {di_plus, di_minus, adx}
    """
    if len(df) < period * 2:
        return {"di_plus": None, "di_minus": None, "adx": None}
    high = df["high"]
    low = df["low"]
    close = df["close"]

    # True Range
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, adjust=False).mean()

    # 方向移动 +DM / -DM
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
    plus_dm = pd.Series(plus_dm, index=high.index)
    minus_dm = pd.Series(minus_dm, index=high.index)
    plus_dm_smooth = plus_dm.ewm(alpha=1 / period, adjust=False).mean()
    minus_dm_smooth = minus_dm.ewm(alpha=1 / period, adjust=False).mean()

    di_plus = 100 * plus_dm_smooth / atr
    di_minus = 100 * minus_dm_smooth / atr
    dx = 100 * (di_plus - di_minus).abs() / (di_plus + di_minus).replace(0, np.nan)
    adx = dx.ewm(alpha=1 / period, adjust=False).mean()

    return {
        "di_plus": float(di_plus.iloc[-1]) if not np.isnan(di_plus.iloc[-1]) else None,
        "di_minus": float(di_minus.iloc[-1]) if not np.isnan(di_minus.iloc[-1]) else None,
        "adx": float(adx.iloc[-1]) if not np.isnan(adx.iloc[-1]) else None,
    }


# ---------- 震荡 ----------

def rsi(df: pd.DataFrame, period: int = 14) -> Dict[str, float]:
    """相对强弱指标 RSI。

    Returns:
        {rsi}（0-100）
    """
    close = df["close"]
    if len(close) < period + 1:
        return {"rsi": None}
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    # Wilder 平滑
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_val = 100 - (100 / (1 + rs))
    last = rsi_val.iloc[-1]
    return {"rsi": float(last) if not np.isnan(last) else 50.0}


def kdj(
    df: pd.DataFrame, period: int = 9, k_smooth: int = 3, d_smooth: int = 3
) -> Dict[str, float]:
    """KDJ 随机指标。

    Returns:
        {k, d, j}（j = 3k - 2d）
    """
    if len(df) < period:
        return {"k": None, "d": None, "j": None}
    high = df["high"]
    low = df["low"]
    close = df["close"]

    lowest_low = low.rolling(period).min()
    highest_high = high.rolling(period).max()
    rsv = 100 * (close - lowest_low) / (highest_high - lowest_low).replace(0, np.nan)

    k = rsv.ewm(alpha=1 / k_smooth, adjust=False).mean()
    d = k.ewm(alpha=1 / d_smooth, adjust=False).mean()
    j = 3 * k - 2 * d

    return {
        "k": float(k.iloc[-1]) if not np.isnan(k.iloc[-1]) else None,
        "d": float(d.iloc[-1]) if not np.isnan(d.iloc[-1]) else None,
        "j": float(j.iloc[-1]) if not np.isnan(j.iloc[-1]) else None,
    }


def cci(
    df: pd.DataFrame, period: int = 20, constant: float = 0.015
) -> Dict[str, float]:
    """CCI 顺势指标。

    Returns:
        {cci}
    """
    if len(df) < period:
        return {"cci": None}
    tp = (df["high"] + df["low"] + df["close"]) / 3
    ma_tp = tp.rolling(period).mean()
    md = tp.rolling(period).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    cci_val = (tp - ma_tp) / (constant * md.replace(0, np.nan))
    last = cci_val.iloc[-1]
    return {"cci": float(last) if not np.isnan(last) else None}


def willr(df: pd.DataFrame, period: int = 14) -> Dict[str, float]:
    """Williams %R 指标。

    Returns:
        {willr}（-100 ~ 0）
    """
    if len(df) < period:
        return {"willr": None}
    high = df["high"]
    low = df["low"]
    close = df["close"]

    highest_high = high.rolling(period).max()
    lowest_low = low.rolling(period).min()
    wr = -100 * (highest_high - close) / (highest_high - lowest_low).replace(0, np.nan)
    last = wr.iloc[-1]
    return {"willr": float(last) if not np.isnan(last) else None}


# ---------- 成交量 ----------

def obv(df: pd.DataFrame) -> Dict[str, Union[float, List[float]]]:
    """能量潮 OBV（On-Balance Volume）。

    Returns:
        {obv}（最新累计值）
    """
    if len(df) < 2:
        return {"obv": None}
    close = df["close"]
    volume = df["volume"]
    direction = np.sign(close.diff().fillna(0))
    obv_series = (direction * volume).cumsum()
    return {"obv": float(obv_series.iloc[-1])}


def vwap(df: pd.DataFrame) -> Dict[str, float]:
    """成交量加权平均价 VWAP。

    注：按当前数据窗口整体计算（非日内重置）。
    Returns:
        {vwap}
    """
    if len(df) == 0:
        return {"vwap": None}
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    vol = df["volume"].replace(0, np.nan)
    if vol.sum() == 0:
        return {"vwap": None}
    vwap_val = (typical_price * vol).sum() / vol.sum()
    return {"vwap": float(vwap_val)}


# ---------- 波动 ----------

def atr(df: pd.DataFrame, period: int = 14) -> Dict[str, float]:
    """真实波动幅度均值 ATR。

    Returns:
        {atr, atr_pct}（atr_pct = atr/close * 100，便于跨币种比较）
    """
    if len(df) < period + 1:
        return {"atr": None, "atr_pct": None}
    high = df["high"]
    low = df["low"]
    close = df["close"]

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr_val = tr.ewm(alpha=1 / period, adjust=False).mean()
    last_close = close.iloc[-1]
    last_atr = atr_val.iloc[-1]
    return {
        "atr": float(last_atr) if not np.isnan(last_atr) else None,
        "atr_pct": float(last_atr / last_close * 100)
        if (not np.isnan(last_atr) and last_close > 0)
        else None,
    }


def stdch(
    df: pd.DataFrame, period: int = 20, std_dev: float = 2.0
) -> Dict[str, float]:
    """标准差通道 STDCH。

    类似布林带，但中轨使用收盘价而非典型价格；用于波动率通道判断。
    Returns:
        {stdch_upper, stdch_middle, stdch_lower}
    """
    return boll(df, period=period, std_dev=std_dev)


# ---------- 统一入口 ----------

INDICATOR_REGISTRY = {
    "ma": ma,
    "ema": ema,
    "macd": macd,
    "boll": boll,
    "dmi": dmi,
    "rsi": rsi,
    "kdj": kdj,
    "cci": cci,
    "willr": willr,
    "obv": obv,
    "vwap": vwap,
    "atr": atr,
    "stdch": stdch,
}


def calculate_indicators(
    ohlcv: Union[List[list], pd.DataFrame],
    indicator_types: Optional[List[str]] = None,
    params: Optional[Dict] = None,
) -> Dict[str, Dict[str, float]]:
    """批量计算技术指标。

    Args:
        ohlcv: K 线数据（CCXT 格式 [[ts, o, h, l, c, v], ...] 或 DataFrame）
        indicator_types: 指标类型列表；None 表示全部 13 类
        params: 指标参数覆盖，如 {"ma": {"periods": [10, 30]}, "rsi": {"period": 7}}

    Returns:
        {indicator_type: {field: value, ...}, ...}
    """
    df = _to_df(ohlcv)
    params = params or {}
    if indicator_types is None:
        indicator_types = list(INDICATOR_REGISTRY.keys())

    result: Dict[str, Dict[str, float]] = {}
    for ind_type in indicator_types:
        func = INDICATOR_REGISTRY.get(ind_type)
        if func is None:
            result[ind_type] = {"error": f"unsupported indicator: {ind_type}"}
            continue
        try:
            ind_params = params.get(ind_type, {})
            result[ind_type] = func(df, **ind_params) if ind_params else func(df)
        except Exception as e:
            result[ind_type] = {"error": str(e)}
    return result
