"""回测引擎（Stage 6.3，numpy 向量化，对齐 PRD §5.6.3）。

性能目标：1 年 1h 级别（8760 条 K 线）≤ 10s（单进程）。

支持 3 类模板策略：
1. double_ma: 双均线金叉死叉
2. rsi_reversal: RSI 超买超卖反转
3. turtle_breakout: 海龟突破（唐奇安通道 + ATR 止损 + 加仓）

输入：K 线 DataFrame + 策略参数 + 初始资金 + 手续费 + 滑点
输出：BacktestResult（核心指标 + 权益曲线 + 回撤曲线 + 开平仓明细 + 每日快照）
"""

import datetime
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


# ---------- 回测结果数据结构 ----------

@dataclass
class BacktestMetrics:
    """回测核心指标。"""

    total_return: float = 0.0  # 总收益率
    annual_return: float = 0.0  # 年化收益率
    max_drawdown: float = 0.0  # 最大回撤
    sharpe_ratio: float = 0.0  # 夏普比率
    sortino_ratio: float = 0.0  # Sortino 比率
    win_rate: float = 0.0  # 胜率
    profit_loss_ratio: float = 0.0  # 盈亏比
    trade_count: int = 0  # 交易次数
    profit_count: int = 0  # 盈利笔数
    loss_count: int = 0  # 亏损笔数
    max_single_profit: float = 0.0  # 最大单笔盈利
    max_single_loss: float = 0.0  # 最大单笔亏损
    avg_holding_bars: int = 0  # 平均持仓周期数
    final_value: float = 0.0  # 最终资金
    buy_hold_return: float = 0.0  # 买入持有收益率
    volatility: float = 0.0  # 年化波动率

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_return": round(self.total_return, 6),
            "annual_return": round(self.annual_return, 6),
            "max_drawdown": round(self.max_drawdown, 6),
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "sortino_ratio": round(self.sortino_ratio, 4),
            "win_rate": round(self.win_rate, 4),
            "profit_loss_ratio": round(self.profit_loss_ratio, 4),
            "trade_count": self.trade_count,
            "profit_count": self.profit_count,
            "loss_count": self.loss_count,
            "max_single_profit": round(self.max_single_profit, 4),
            "max_single_loss": round(self.max_single_loss, 4),
            "avg_holding_bars": self.avg_holding_bars,
            "final_value": round(self.final_value, 4),
            "buy_hold_return": round(self.buy_hold_return, 6),
            "volatility": round(self.volatility, 4),
        }


@dataclass
class BacktestTrade:
    """回测单笔交易（开平仓配对）。"""

    entry_time: str  # 开仓时间 ISO
    exit_time: str  # 平仓时间 ISO
    entry_price: float
    exit_price: float
    quantity: float
    side: str  # long / short
    pnl: float  # 盈亏（USDT）
    pnl_pct: float  # 盈亏比例
    holding_bars: int  # 持仓周期数
    exit_reason: str  # 平仓原因：signal / stop_loss / take_profit / time_stop / trailing_stop

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_time": self.entry_time,
            "exit_time": self.exit_time,
            "entry_price": round(self.entry_price, 6),
            "exit_price": round(self.exit_price, 6),
            "quantity": round(self.quantity, 8),
            "side": self.side,
            "pnl": round(self.pnl, 4),
            "pnl_pct": round(self.pnl_pct, 6),
            "holding_bars": self.holding_bars,
            "exit_reason": self.exit_reason,
        }


@dataclass
class BacktestResult:
    """回测完整结果。"""

    metrics: BacktestMetrics
    equity_curve: List[Dict[str, Any]] = field(default_factory=list)  # 权益曲线
    drawdown_curve: List[Dict[str, Any]] = field(default_factory=list)  # 回撤曲线
    trades: List[Dict[str, Any]] = field(default_factory=list)  # 开平仓明细
    daily_snapshots: List[Dict[str, Any]] = field(default_factory=list)  # 每日快照
    bars: int = 0  # K 线数量
    start_date: Optional[str] = None
    end_date: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metrics": self.metrics.to_dict(),
            "equity_curve": self.equity_curve,
            "drawdown_curve": self.drawdown_curve,
            "trades": self.trades,
            "daily_snapshots": self.daily_snapshots,
            "bars": self.bars,
            "start_date": self.start_date,
            "end_date": self.end_date,
        }


# ---------- 指标计算辅助函数 ----------

def _calc_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """计算 ATR。"""
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period).mean()


def _calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """计算 RSI。"""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


# ---------- 策略信号生成 ----------

def _signals_double_ma(
    df: pd.DataFrame, fast: int = 5, slow: int = 20
) -> pd.Series:
    """双均线金叉死叉信号。

    返回：1=持仓，0=空仓
    """
    ma_fast = df["close"].rolling(fast).mean()
    ma_slow = df["close"].rolling(slow).mean()
    signal = (ma_fast > ma_slow).astype(int)
    # 信号延迟 1 根（下一根开盘执行）
    return signal.shift(1).fillna(0)


def _signals_rsi_reversal(
    df: pd.DataFrame, period: int = 14, oversold: int = 30, overbought: int = 70
) -> pd.Series:
    """RSI 超买超卖反转信号。

    RSI < oversold 买入，RSI > overbought 卖出。
    """
    rsi = _calc_rsi(df["close"], period)
    signal = pd.Series(0, index=df.index)
    holding = False
    for i in range(len(df)):
        if pd.isna(rsi.iloc[i]):
            signal.iloc[i] = 0
            continue
        if not holding and rsi.iloc[i] < oversold:
            holding = True
        elif holding and rsi.iloc[i] > overbought:
            holding = False
        signal.iloc[i] = 1 if holding else 0
    return signal.shift(1).fillna(0)


def _signals_turtle_breakout(
    df: pd.DataFrame,
    entry_period: int = 20,
    exit_period: int = 10,
    atr_period: int = 20,
) -> pd.Series:
    """海龟突破信号。

    价格突破 entry_period 日高点买入，跌破 exit_period 日低点卖出。
    """
    high = df["high"]
    low = df["low"]
    # 唐奇安通道（前 N 日，不含当日）
    entry_high = high.rolling(entry_period).max().shift(1)
    exit_low = low.rolling(exit_period).min().shift(1)

    signal = pd.Series(0, index=df.index)
    holding = False
    for i in range(len(df)):
        if pd.isna(entry_high.iloc[i]) or pd.isna(exit_low.iloc[i]):
            signal.iloc[i] = 0
            continue
        if not holding and df["close"].iloc[i] > entry_high.iloc[i]:
            holding = True
        elif holding and df["close"].iloc[i] < exit_low.iloc[i]:
            holding = False
        signal.iloc[i] = 1 if holding else 0
    return signal.shift(1).fillna(0)


def _generate_signals(
    df: pd.DataFrame, strategy_type: str, params: Dict[str, Any]
) -> pd.Series:
    """根据策略类型生成持仓信号。"""
    if strategy_type == "double_ma":
        return _signals_double_ma(
            df,
            fast=int(params.get("fast_period", 5)),
            slow=int(params.get("slow_period", 20)),
        )
    elif strategy_type == "rsi_reversal":
        return _signals_rsi_reversal(
            df,
            period=int(params.get("rsi_period", 14)),
            oversold=int(params.get("oversold", 30)),
            overbought=int(params.get("overbought", 70)),
        )
    elif strategy_type == "turtle_breakout":
        return _signals_turtle_breakout(
            df,
            entry_period=int(params.get("entry_period", 20)),
            exit_period=int(params.get("exit_period", 10)),
            atr_period=int(params.get("atr_period", 20)),
        )
    elif strategy_type == "buy_hold":
        return pd.Series(1, index=df.index)
    else:
        # 默认 buy_hold
        return pd.Series(1, index=df.index)


# ---------- 回测主引擎 ----------

def run_backtest(
    df: pd.DataFrame,
    strategy_type: str = "double_ma",
    params: Optional[Dict[str, Any]] = None,
    initial_capital: float = 10000.0,
    fee_rate: float = 0.001,  # 0.1% 手续费（买卖双向）
    slippage: float = 0.0,  # 滑点比例
    risk_control: Optional[Dict[str, Any]] = None,
) -> BacktestResult:
    """执行向量化回测。

    Args:
        df: K 线数据，必须包含列 timestamp/open/high/low/close/volume
        strategy_type: 策略类型（double_ma / rsi_reversal / turtle_breakout / buy_hold）
        params: 策略参数
        initial_capital: 初始资金（USDT）
        fee_rate: 手续费率（单边，如 0.001 = 0.1%）
        slippage: 滑点比例（如 0.0005 = 0.05%）
        risk_control: 风控参数（max_drawdown_pct 等触发后停止交易）

    Returns:
        BacktestResult 完整回测结果
    """
    params = params or {}
    risk_control = risk_control or {}

    if df.empty:
        return BacktestResult(
            metrics=BacktestMetrics(final_value=initial_capital),
            bars=0,
        )

    df = df.copy().reset_index(drop=True)
    close = df["close"].values.astype(float)
    n = len(df)

    # 1. 生成持仓信号
    signal = _generate_signals(df, strategy_type, params).values.astype(int)

    # 2. 计算收益率
    returns = np.diff(close, prepend=close[0]) / close

    # 3. 滑点调整（入场时多付、出场时少收）
    if slippage > 0:
        # 信号变化时扣滑点
        signal_change = np.abs(np.diff(signal, prepend=signal[0]))
        slippage_cost = signal_change * slippage
    else:
        slippage_cost = np.zeros(n)

    # 4. 手续费（信号变化时扣双边手续费）
    signal_change = np.abs(np.diff(signal, prepend=signal[0]))
    fee_cost = signal_change * fee_rate

    # 5. 策略收益率 = 持仓信号 × 市场收益 - 手续费 - 滑点
    strategy_returns = signal * returns - fee_cost - slippage_cost

    # 6. 风控：最大回撤触发停止
    max_dd_limit = float(risk_control.get("max_drawdown_pct", 1.0))  # 默认不限制
    nav = np.zeros(n)
    nav[0] = initial_capital
    stopped = False
    peak = initial_capital

    for i in range(1, n):
        if stopped:
            nav[i] = nav[i - 1]
            continue
        nav[i] = nav[i - 1] * (1 + strategy_returns[i])
        peak = max(peak, nav[i])
        dd = (nav[i] - peak) / peak if peak > 0 else 0
        if dd < -max_dd_limit:
            stopped = True
            # 平仓
            signal[i:] = 0
            strategy_returns[i + 1 :] = 0

    # 7. 买入持有基准
    buy_hold_nav = initial_capital * np.cumprod(1 + returns)

    # 8. 回撤曲线
    peak_curve = np.maximum.accumulate(nav)
    drawdown = (nav - peak_curve) / peak_curve

    # 9. 提取交易明细（信号变化点）
    trades = _extract_trades(df, signal, close, nav, initial_capital, fee_rate, slippage)

    # 10. 计算指标
    metrics = _calc_metrics(
        nav, buy_hold_nav, strategy_returns, returns, trades, initial_capital, n, df
    )

    # 11. 权益曲线（按时间）
    timestamps = df["timestamp"].tolist() if "timestamp" in df.columns else list(range(n))
    equity_curve = []
    drawdown_curve = []
    for i in range(n):
        ts = timestamps[i]
        if isinstance(ts, (pd.Timestamp, datetime.datetime)):
            ts_str = ts.isoformat()
        else:
            ts_str = str(ts)
        equity_curve.append({"timestamp": ts_str, "nav": round(float(nav[i]), 4), "buy_hold": round(float(buy_hold_nav[i]), 4)})
        drawdown_curve.append({"timestamp": ts_str, "drawdown": round(float(drawdown[i]), 6)})

    # 12. 每日快照（按日聚合）
    daily_snapshots = _build_daily_snapshots(df, nav)

    start_date = equity_curve[0]["timestamp"] if equity_curve else None
    end_date = equity_curve[-1]["timestamp"] if equity_curve else None

    return BacktestResult(
        metrics=metrics,
        equity_curve=equity_curve,
        drawdown_curve=drawdown_curve,
        trades=[t.to_dict() for t in trades],
        daily_snapshots=daily_snapshots,
        bars=n,
        start_date=start_date,
        end_date=end_date,
    )


def _extract_trades(
    df: pd.DataFrame,
    signal: np.ndarray,
    close: np.ndarray,
    nav: np.ndarray,
    initial_capital: float,
    fee_rate: float,
    slippage: float,
) -> List[BacktestTrade]:
    """从信号变化提取开平仓配对。"""
    trades: List[BacktestTrade] = []
    n = len(signal)

    # 找信号变化点
    changes = np.diff(signal, prepend=signal[0])
    entry_idx = None
    entry_price = 0.0
    entry_nav = 0.0
    quantity = 0.0

    timestamps = df["timestamp"].tolist() if "timestamp" in df.columns else list(range(n))

    for i in range(n):
        if changes[i] > 0:  # 开仓（0→1）
            entry_idx = i
            entry_price = close[i] * (1 + slippage)
            entry_nav = nav[i]
            # 简化：全仓买入
            quantity = entry_nav / entry_price * (1 - fee_rate)
        elif changes[i] < 0 and entry_idx is not None:  # 平仓（1→0）
            exit_price = close[i] * (1 - slippage)
            exit_nav = quantity * exit_price * (1 - fee_rate)
            pnl = exit_nav - entry_nav
            pnl_pct = pnl / entry_nav if entry_nav > 0 else 0.0
            holding_bars = i - entry_idx

            ts_entry = timestamps[entry_idx]
            ts_exit = timestamps[i]
            ts_entry_str = ts_entry.isoformat() if hasattr(ts_entry, "isoformat") else str(ts_entry)
            ts_exit_str = ts_exit.isoformat() if hasattr(ts_exit, "isoformat") else str(ts_exit)

            trades.append(
                BacktestTrade(
                    entry_time=ts_entry_str,
                    exit_time=ts_exit_str,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    quantity=quantity,
                    side="long",
                    pnl=float(pnl),
                    pnl_pct=float(pnl_pct),
                    holding_bars=holding_bars,
                    exit_reason="signal",
                )
            )
            entry_idx = None

    # 如果最后还在持仓，按最后收盘价平仓
    if entry_idx is not None and n > 0:
        i = n - 1
        exit_price = close[i]
        exit_nav = quantity * exit_price * (1 - fee_rate)
        pnl = exit_nav - entry_nav
        pnl_pct = pnl / entry_nav if entry_nav > 0 else 0.0
        ts_entry = timestamps[entry_idx]
        ts_exit = timestamps[i]
        trades.append(
            BacktestTrade(
                entry_time=ts_entry.isoformat() if hasattr(ts_entry, "isoformat") else str(ts_entry),
                exit_time=ts_exit.isoformat() if hasattr(ts_exit, "isoformat") else str(ts_exit),
                entry_price=entry_price,
                exit_price=exit_price,
                quantity=quantity,
                side="long",
                pnl=float(pnl),
                pnl_pct=float(pnl_pct),
                holding_bars=i - entry_idx,
                exit_reason="end_of_data",
            )
        )

    return trades


def _calc_metrics(
    nav: np.ndarray,
    buy_hold_nav: np.ndarray,
    strategy_returns: np.ndarray,
    market_returns: np.ndarray,
    trades: List[BacktestTrade],
    initial_capital: float,
    n_bars: int,
    df: pd.DataFrame,
) -> BacktestMetrics:
    """计算回测核心指标。"""
    if n_bars == 0:
        return BacktestMetrics()

    final_value = float(nav[-1])
    total_return = (final_value - initial_capital) / initial_capital
    buy_hold_return = (float(buy_hold_nav[-1]) - initial_capital) / initial_capital

    # 年化收益率（根据 K 线数量估算年化因子）
    annual_factor = _estimate_annual_factor(df)
    if n_bars > 0 and total_return > -1:
        years = n_bars / annual_factor if annual_factor > 0 else 1
        annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else total_return
    else:
        annual_return = 0.0

    # 最大回撤
    peak = np.maximum.accumulate(nav)
    drawdown = (nav - peak) / peak
    max_drawdown = float(np.min(drawdown)) if len(drawdown) > 0 else 0.0

    # 波动率（年化）
    valid_returns = strategy_returns[strategy_returns != 0]
    if len(valid_returns) > 1:
        volatility = float(np.std(valid_returns) * np.sqrt(annual_factor))
    else:
        volatility = 0.0

    # 夏普比率
    if len(valid_returns) > 1 and np.std(valid_returns) > 0:
        sharpe = float(np.mean(valid_returns) / np.std(valid_returns) * np.sqrt(annual_factor))
    else:
        sharpe = 0.0

    # Sortino 比率（仅用下行波动率）
    downside_returns = valid_returns[valid_returns < 0]
    if len(downside_returns) > 0 and np.std(downside_returns) > 0:
        sortino = float(np.mean(valid_returns) / np.std(downside_returns) * np.sqrt(annual_factor))
    else:
        sortino = 0.0

    # 交易统计
    trade_count = len(trades)
    profits = [t.pnl for t in trades if t.pnl > 0]
    losses = [t.pnl for t in trades if t.pnl < 0]
    profit_count = len(profits)
    loss_count = len(losses)
    win_rate = profit_count / trade_count if trade_count > 0 else 0.0
    avg_profit = np.mean(profits) if profits else 0.0
    avg_loss = abs(np.mean(losses)) if losses else 0.0
    profit_loss_ratio = avg_profit / avg_loss if avg_loss > 0 else 0.0
    max_single_profit = max(profits) if profits else 0.0
    max_single_loss = min(losses) if losses else 0.0
    avg_holding = int(np.mean([t.holding_bars for t in trades])) if trades else 0

    return BacktestMetrics(
        total_return=total_return,
        annual_return=annual_return,
        max_drawdown=max_drawdown,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        win_rate=win_rate,
        profit_loss_ratio=profit_loss_ratio,
        trade_count=trade_count,
        profit_count=profit_count,
        loss_count=loss_count,
        max_single_profit=float(max_single_profit),
        max_single_loss=float(max_single_loss),
        avg_holding_bars=avg_holding,
        final_value=final_value,
        buy_hold_return=buy_hold_return,
        volatility=volatility,
    )


def _estimate_annual_factor(df: pd.DataFrame) -> int:
    """根据 K 线时间间隔估算年化因子。"""
    if "timestamp" not in df.columns or len(df) < 2:
        return 365  # 默认按日
    ts = df["timestamp"]
    if not pd.api.types.is_datetime64_any_dtype(ts):
        try:
            ts = pd.to_datetime(ts)
        except Exception:
            return 365
    if len(ts) >= 2:
        delta = (ts.iloc[1] - ts.iloc[0]).total_seconds()
        if delta > 0:
            return int(365 * 24 * 3600 / delta)
    return 365


def _build_daily_snapshots(df: pd.DataFrame, nav: np.ndarray) -> List[Dict[str, Any]]:
    """按日聚合权益快照。"""
    if "timestamp" not in df.columns or len(df) == 0:
        return []
    ts = df["timestamp"]
    if not pd.api.types.is_datetime64_any_dtype(ts):
        try:
            ts = pd.to_datetime(ts)
        except Exception:
            return []

    df_snap = pd.DataFrame(
        {"date": ts.dt.date, "nav": nav[: len(df)]}
    )
    daily = df_snap.groupby("date").last().reset_index()
    return [
        {"date": str(row["date"]), "nav": round(float(row["nav"]), 4)}
        for _, row in daily.iterrows()
    ]


# ---------- 回测对比 ----------

def compare_backtests(
    result_a: BacktestResult, result_b: BacktestResult
) -> Dict[str, Any]:
    """对比两次回测结果。"""
    m_a = result_a.metrics.to_dict()
    m_b = result_b.metrics.to_dict()

    # 指标差异
    metrics_diff = {}
    for key in m_a:
        if key in m_b:
            try:
                diff = float(m_b[key]) - float(m_a[key])
                metrics_diff[key] = round(diff, 6)
            except (TypeError, ValueError):
                metrics_diff[key] = None

    # 合并权益曲线
    equity_combined = []
    len_a = len(result_a.equity_curve)
    len_b = len(result_b.equity_curve)
    max_len = max(len_a, len_b)
    for i in range(max_len):
        point = {}
        if i < len_a:
            point["timestamp"] = result_a.equity_curve[i]["timestamp"]
            point["nav_a"] = result_a.equity_curve[i]["nav"]
        if i < len_b and not point.get("timestamp"):
            point["timestamp"] = result_b.equity_curve[i]["timestamp"]
        if i < len_b:
            point["nav_b"] = result_b.equity_curve[i]["nav"]
        equity_combined.append(point)

    return {
        "metrics_a": m_a,
        "metrics_b": m_b,
        "metrics_diff": metrics_diff,
        "equity_curve_combined": equity_combined,
    }
