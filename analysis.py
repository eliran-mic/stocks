from dataclasses import dataclass
from enum import Enum

import pandas as pd
import ta

from config import STOP_LOSS_PCT, TAKE_PROFIT_PCT
from stock_data import get_history


class Action(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class Strength(Enum):
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"


@dataclass
class Signal:
    name: str
    action: Action
    strength: Strength
    detail: str


@dataclass
class AnalysisResult:
    ticker: str
    current_price: float
    sma_20: float | None
    sma_50: float | None
    rsi_14: float | None
    signals: list[Signal]

    @property
    def overall_action(self) -> Action:
        if not self.signals:
            return Action.HOLD
        sell_count = sum(1 for s in self.signals if s.action == Action.SELL)
        buy_count = sum(1 for s in self.signals if s.action == Action.BUY)
        strong_sells = sum(
            1
            for s in self.signals
            if s.action == Action.SELL and s.strength == Strength.STRONG
        )
        if strong_sells > 0:
            return Action.SELL
        if sell_count > buy_count:
            return Action.SELL
        if buy_count > sell_count:
            return Action.BUY
        return Action.HOLD


def compute_indicators(df: pd.DataFrame) -> dict:
    close = df["Close"]
    sma_20 = ta.trend.sma_indicator(close, window=20)
    sma_50 = ta.trend.sma_indicator(close, window=50)
    rsi_14 = ta.momentum.rsi(close, window=14)

    return {
        "sma_20": sma_20.iloc[-1] if not sma_20.empty else None,
        "sma_50": sma_50.iloc[-1] if not sma_50.empty else None,
        "rsi_14": rsi_14.iloc[-1] if not rsi_14.empty else None,
        "prev_sma_20": sma_20.iloc[-2] if len(sma_20) >= 2 else None,
        "prev_sma_50": sma_50.iloc[-2] if len(sma_50) >= 2 else None,
    }


def generate_signals(
    current_price: float,
    indicators: dict,
    purchase_price: float | None = None,
) -> list[Signal]:
    signals = []

    sma_20 = indicators.get("sma_20")
    sma_50 = indicators.get("sma_50")
    prev_sma_20 = indicators.get("prev_sma_20")
    prev_sma_50 = indicators.get("prev_sma_50")
    rsi = indicators.get("rsi_14")

    # SMA crossover
    if all(v is not None for v in [sma_20, sma_50, prev_sma_20, prev_sma_50]):
        if prev_sma_20 <= prev_sma_50 and sma_20 > sma_50:
            signals.append(
                Signal(
                    "SMA Crossover",
                    Action.BUY,
                    Strength.STRONG,
                    "Golden cross: SMA-20 crossed above SMA-50",
                )
            )
        elif prev_sma_20 >= prev_sma_50 and sma_20 < sma_50:
            signals.append(
                Signal(
                    "SMA Crossover",
                    Action.SELL,
                    Strength.STRONG,
                    "Death cross: SMA-20 crossed below SMA-50",
                )
            )
        elif sma_20 > sma_50:
            signals.append(
                Signal(
                    "SMA Trend",
                    Action.BUY,
                    Strength.WEAK,
                    f"SMA-20 ({sma_20:.2f}) above SMA-50 ({sma_50:.2f})",
                )
            )
        else:
            signals.append(
                Signal(
                    "SMA Trend",
                    Action.SELL,
                    Strength.WEAK,
                    f"SMA-20 ({sma_20:.2f}) below SMA-50 ({sma_50:.2f})",
                )
            )

    # RSI
    if rsi is not None:
        if rsi > 70:
            strength = Strength.STRONG if rsi > 80 else Strength.MODERATE
            signals.append(
                Signal("RSI", Action.SELL, strength, f"RSI at {rsi:.1f} (overbought)")
            )
        elif rsi < 30:
            strength = Strength.STRONG if rsi < 20 else Strength.MODERATE
            signals.append(
                Signal("RSI", Action.BUY, strength, f"RSI at {rsi:.1f} (oversold)")
            )
        else:
            signals.append(
                Signal("RSI", Action.HOLD, Strength.WEAK, f"RSI at {rsi:.1f} (neutral)")
            )

    # Stop-loss / Take-profit
    if purchase_price is not None and purchase_price > 0:
        pct_change = ((current_price - purchase_price) / purchase_price) * 100
        if pct_change <= -STOP_LOSS_PCT:
            signals.append(
                Signal(
                    "Stop-Loss",
                    Action.SELL,
                    Strength.STRONG,
                    f"Price dropped {pct_change:.1f}% from purchase",
                )
            )
        elif pct_change >= TAKE_PROFIT_PCT:
            signals.append(
                Signal(
                    "Take-Profit",
                    Action.SELL,
                    Strength.MODERATE,
                    f"Price up {pct_change:.1f}% from purchase",
                )
            )

    return signals


def analyze_stock(
    ticker: str, purchase_price: float | None = None
) -> AnalysisResult | None:
    df = get_history(ticker)
    if df is None or len(df) < 50:
        return None

    current_price = df["Close"].iloc[-1]
    indicators = compute_indicators(df)
    signals = generate_signals(current_price, indicators, purchase_price)

    return AnalysisResult(
        ticker=ticker.upper(),
        current_price=current_price,
        sma_20=indicators.get("sma_20"),
        sma_50=indicators.get("sma_50"),
        rsi_14=indicators.get("rsi_14"),
        signals=signals,
    )
