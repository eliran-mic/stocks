import os
import tempfile

import pytest

os.environ["DATA_DIR"] = tempfile.mkdtemp()

from db import add_stock, remove_stock, get_portfolio, get_all_user_ids


@pytest.fixture(autouse=True)
def clean_db(tmp_path, monkeypatch):
    monkeypatch.setattr("db.DATA_DIR", str(tmp_path))
    yield


def test_add_and_get_portfolio():
    add_stock(1, "AAPL", 10, 150.0, "2024-01-15")
    portfolio = get_portfolio(1)
    assert len(portfolio) == 1
    assert portfolio[0]["ticker"] == "AAPL"
    assert portfolio[0]["quantity"] == 10
    assert portfolio[0]["purchase_price"] == 150.0


def test_add_duplicate_updates():
    add_stock(1, "AAPL", 10, 150.0)
    add_stock(1, "AAPL", 20, 175.0)
    portfolio = get_portfolio(1)
    assert len(portfolio) == 1
    assert portfolio[0]["quantity"] == 20
    assert portfolio[0]["purchase_price"] == 175.0


def test_remove_stock():
    add_stock(1, "AAPL", 10, 150.0)
    assert remove_stock(1, "AAPL") is True
    assert get_portfolio(1) == []


def test_remove_nonexistent():
    assert remove_stock(1, "FAKE") is False


def test_multiple_stocks():
    add_stock(1, "AAPL", 10, 150.0)
    add_stock(1, "GOOGL", 5, 140.0)
    portfolio = get_portfolio(1)
    assert len(portfolio) == 2
    tickers = [p["ticker"] for p in portfolio]
    assert "AAPL" in tickers
    assert "GOOGL" in tickers


def test_per_user_isolation():
    add_stock(1, "AAPL", 10, 150.0)
    add_stock(2, "GOOGL", 5, 140.0)
    assert len(get_portfolio(1)) == 1
    assert len(get_portfolio(2)) == 1
    assert get_portfolio(1)[0]["ticker"] == "AAPL"
    assert get_portfolio(2)[0]["ticker"] == "GOOGL"


def test_get_all_user_ids():
    add_stock(100, "AAPL", 10, 150.0)
    add_stock(200, "GOOGL", 5, 140.0)
    ids = get_all_user_ids()
    assert 100 in ids
    assert 200 in ids


def test_ticker_case_insensitive():
    add_stock(1, "aapl", 10, 150.0)
    portfolio = get_portfolio(1)
    assert portfolio[0]["ticker"] == "AAPL"
