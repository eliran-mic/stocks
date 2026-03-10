import yfinance as yf
import pandas as pd


def validate_ticker(ticker: str) -> bool:
    try:
        t = yf.Ticker(ticker.upper())
        info = t.fast_info
        return info.last_price is not None and info.last_price > 0
    except Exception:
        return False


def get_current_price(ticker: str) -> float | None:
    try:
        t = yf.Ticker(ticker.upper())
        return t.fast_info.last_price
    except Exception:
        return None


def get_history(ticker: str, period: str = "6mo") -> pd.DataFrame | None:
    try:
        t = yf.Ticker(ticker.upper())
        df = t.history(period=period)
        if df.empty:
            return None
        return df
    except Exception:
        return None


def get_batch_prices(tickers: list[str]) -> dict[str, float | None]:
    results = {}
    for ticker in tickers:
        results[ticker.upper()] = get_current_price(ticker)
    return results


def get_stock_info(ticker: str) -> dict | None:
    try:
        t = yf.Ticker(ticker.upper())
        info = t.info
        return {
            "name": info.get("shortName", ticker.upper()),
            "sector": info.get("sector", "N/A"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "dividend_yield": info.get("dividendYield"),
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "52w_low": info.get("fiftyTwoWeekLow"),
        }
    except Exception:
        return None
