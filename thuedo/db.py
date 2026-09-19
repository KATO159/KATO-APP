"""Kết nối SQLite và khởi tạo lược đồ dữ liệu cho ứng dụng quản lý thuê đồ."""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

DEFAULT_DB_PATH = os.environ.get("KATO_THUEDO_DB", "thuedo.db")

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS categories (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    sku          TEXT NOT NULL UNIQUE,
    name         TEXT NOT NULL,
    category_id  INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    size         TEXT NOT NULL DEFAULT '',
    color        TEXT NOT NULL DEFAULT '',
    quantity     INTEGER NOT NULL DEFAULT 1,   -- tổng số lượng cửa hàng sở hữu
    rental_price INTEGER NOT NULL DEFAULT 0,   -- giá thuê mỗi ngày (VND)
    deposit      INTEGER NOT NULL DEFAULT 0,   -- tiền cọc cho mỗi đơn vị (VND)
    active       INTEGER NOT NULL DEFAULT 1,
    note         TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS customers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    phone       TEXT NOT NULL UNIQUE,
    id_number   TEXT NOT NULL DEFAULT '',
    address     TEXT NOT NULL DEFAULT '',
    note        TEXT NOT NULL DEFAULT '',
    blacklisted INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rentals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT NOT NULL UNIQUE,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    start_date  TEXT NOT NULL,                 -- ngày bắt đầu thuê (YYYY-MM-DD)
    due_date    TEXT NOT NULL,                 -- hạn trả theo hợp đồng
    return_date TEXT,                          -- ngày trả thực tế
    status      TEXT NOT NULL DEFAULT 'renting', -- booked | renting | returned | cancelled
    discount    INTEGER NOT NULL DEFAULT 0,
    extra_fee   INTEGER NOT NULL DEFAULT 0,    -- phí phát sinh: hư hỏng, giặt ủi...
    late_fee    INTEGER NOT NULL DEFAULT 0,    -- phí trễ hạn chốt khi trả đồ
    note        TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rental_items (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    rental_id        INTEGER NOT NULL REFERENCES rentals(id) ON DELETE CASCADE,
    item_id          INTEGER NOT NULL REFERENCES items(id),
    quantity         INTEGER NOT NULL,
    price_per_day    INTEGER NOT NULL,         -- chốt giá tại thời điểm lập đơn
    deposit_per_unit INTEGER NOT NULL,
    returned_qty     INTEGER NOT NULL DEFAULT 0,
    damaged_qty      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS payments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    rental_id  INTEGER NOT NULL REFERENCES rentals(id) ON DELETE CASCADE,
    amount     INTEGER NOT NULL,
    kind       TEXT NOT NULL,                  -- deposit | deposit_refund | payment | refund
    method     TEXT NOT NULL DEFAULT 'cash',   -- cash | transfer | card
    note       TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_rentals_status ON rentals(status);
CREATE INDEX IF NOT EXISTS idx_rentals_due ON rentals(due_date);
CREATE INDEX IF NOT EXISTS idx_rental_items_rental ON rental_items(rental_id);
CREATE INDEX IF NOT EXISTS idx_rental_items_item ON rental_items(item_id);
CREATE INDEX IF NOT EXISTS idx_payments_rental ON payments(rental_id);
"""

DEFAULT_SETTINGS = {
    "shop_name": "KATO - Cho Thuê Đồ",
    "shop_phone": "",
    "shop_address": "",
    "late_fee_rate": "1.5",      # hệ số nhân giá thuê/ngày khi trả trễ
    "currency_suffix": "đ",
}


def now_iso() -> str:
    """Mốc thời gian ISO dùng chung cho mọi bản ghi."""
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def connect(db_path: str = None) -> sqlite3.Connection:
    """Mở kết nối SQLite đã bật khoá ngoại và trả về row dạng dict."""
    path = db_path or DEFAULT_DB_PATH
    folder = os.path.dirname(os.path.abspath(path))
    if folder:
        os.makedirs(folder, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # WAL cho phép đọc trong khi đang ghi - tránh lỗi khoá khi mở nhiều tab.
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init_db(conn: sqlite3.Connection) -> sqlite3.Connection:
    """Tạo bảng nếu chưa có và nạp cấu hình mặc định."""
    conn.executescript(SCHEMA)
    for key, value in DEFAULT_SETTINGS.items():
        conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO NOTHING",
            (key, value),
        )
    conn.commit()
    return conn


def get_db(db_path: str = None) -> sqlite3.Connection:
    """Kết nối + khởi tạo lược đồ trong một bước."""
    return init_db(connect(db_path))


@contextmanager
def transaction(conn: sqlite3.Connection):
    """Bọc một nhóm thao tác ghi: commit khi thành công, rollback khi lỗi."""
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
