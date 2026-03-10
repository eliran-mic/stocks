from formatting import format_portfolio, format_alerts


def test_format_empty_portfolio():
    result = format_portfolio([], {})
    assert "empty" in result.lower()


def test_format_portfolio_with_holdings():
    holdings = [
        {
            "ticker": "AAPL",
            "quantity": 10,
            "purchase_price": 150.0,
            "purchase_date": "2024-01-15",
        }
    ]
    prices = {"AAPL": 175.0}
    result = format_portfolio(holdings, prices)
    assert "AAPL" in result
    assert "175.00" in result
    assert "Total Value" in result


def test_format_portfolio_missing_price():
    holdings = [
        {
            "ticker": "AAPL",
            "quantity": 10,
            "purchase_price": 150.0,
            "purchase_date": "2024-01-15",
        }
    ]
    prices = {"AAPL": None}
    result = format_portfolio(holdings, prices)
    assert "N/A" in result


def test_format_alerts_empty():
    result = format_alerts([])
    assert "No significant signals" in result
