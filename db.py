import os
import sqlite3
from datetime import datetime

from config import DATA_DIR

SCHEMA = """
CREATE TABLE IF NOT EXISTS portfolio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL UNIQUE,
    quantity REAL NOT NULL,
    purchase_price REAL NOT NULL,
    purchase_date TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS alert_settings (
    chat_id INTEGER PRIMARY KEY,
    is_active INTEGER DEFAULT 1
);
"""


def get_db(user_id: int) -> sqlite3.Connection:
    os.makedirs(DATA_DIR, exist_ok=True)
    db_path = os.path.join(DATA_DIR, f"user_{user_id}.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.executescript(SCHEMA)
    return conn


def add_stock(
    user_id: int, ticker: str, quantity: float, price: float, date: str | None = None
) -> None:
    date = date or datetime.now().strftime("%Y-%m-%d")
    conn = get_db(user_id)
    try:
        conn.execute(
            "INSERT INTO portfolio (ticker, quantity, purchase_price, purchase_date) VALUES (?, ?, ?, ?)"
            " ON CONFLICT(ticker) DO UPDATE SET quantity=?, purchase_price=?, purchase_date=?",
            (ticker.upper(), quantity, price, date, quantity, price, date),
        )
        conn.commit()
    finally:
        conn.close()


def remove_stock(user_id: int, ticker: str) -> bool:
    conn = get_db(user_id)
    try:
        cur = conn.execute("DELETE FROM portfolio WHERE ticker = ?", (ticker.upper(),))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_portfolio(user_id: int) -> list[dict]:
    conn = get_db(user_id)
    try:
        rows = conn.execute(
            "SELECT ticker, quantity, purchase_price, purchase_date FROM portfolio ORDER BY ticker"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def set_alert(user_id: int, chat_id: int, is_active: bool = True) -> None:
    conn = get_db(user_id)
    try:
        conn.execute(
            "INSERT INTO alert_settings (chat_id, is_active) VALUES (?, ?)"
            " ON CONFLICT(chat_id) DO UPDATE SET is_active=?",
            (chat_id, int(is_active), int(is_active)),
        )
        conn.commit()
    finally:
        conn.close()


def get_alert_chat_ids(user_id: int) -> list[int]:
    conn = get_db(user_id)
    try:
        rows = conn.execute(
            "SELECT chat_id FROM alert_settings WHERE is_active = 1"
        ).fetchall()
        return [r["chat_id"] for r in rows]
    finally:
        conn.close()


def get_all_user_ids() -> list[int]:
    os.makedirs(DATA_DIR, exist_ok=True)
    user_ids = []
    for f in os.listdir(DATA_DIR):
        if f.startswith("user_") and f.endswith(".db"):
            try:
                uid = int(f[5:-3])
                user_ids.append(uid)
            except ValueError:
                continue
    return user_ids
