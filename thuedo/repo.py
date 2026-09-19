"""Lớp truy xuất dữ liệu: CRUD cho danh mục, đồ, khách hàng, đơn thuê, thanh toán."""

import sqlite3

from .db import now_iso
from .utils import next_code, normalize_phone, to_iso

RENTAL_OPEN_STATUSES = ("booked", "renting")
STATUS_LABELS = {
    "booked": "Đã đặt",
    "renting": "Đang thuê",
    "returned": "Đã trả",
    "cancelled": "Đã huỷ",
}
PAYMENT_LABELS = {
    "deposit": "Nhận cọc",
    "deposit_refund": "Hoàn cọc",
    "payment": "Thu tiền thuê",
    "refund": "Hoàn tiền",
}


def _rows(cur) -> list:
    return [dict(r) for r in cur.fetchall()]


def _row(cur):
    r = cur.fetchone()
    return dict(r) if r else None


# ---------------------------------------------------------------- DANH MỤC
def list_categories(conn) -> list:
    return _rows(conn.execute("SELECT * FROM categories ORDER BY name COLLATE NOCASE"))


def add_category(conn, name: str) -> int:
    name = (name or "").strip()
    if not name:
        raise ValueError("Tên danh mục không được để trống.")
    cur = conn.execute(
        "INSERT INTO categories(name, created_at) VALUES(?, ?)", (name, now_iso())
    )
    conn.commit()
    return cur.lastrowid


def get_or_create_category(conn, name: str) -> int:
    name = (name or "").strip()
    if not name:
        return None
    row = _row(conn.execute("SELECT id FROM categories WHERE name = ?", (name,)))
    return row["id"] if row else add_category(conn, name)


def delete_category(conn, category_id: int) -> None:
    conn.execute("UPDATE items SET category_id = NULL WHERE category_id = ?", (category_id,))
    conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    conn.commit()


# -------------------------------------------------------------------- ĐỒ
def list_items(conn, keyword: str = "", category_id: int = None, only_active: bool = False) -> list:
    sql = [
        "SELECT i.*, c.name AS category_name",
        "FROM items i LEFT JOIN categories c ON c.id = i.category_id",
        "WHERE 1 = 1",
    ]
    params = []
    if keyword:
        sql.append("AND (i.name LIKE ? OR i.sku LIKE ? OR i.color LIKE ? OR i.size LIKE ?)")
        params += [f"%{keyword}%"] * 4
    if category_id:
        sql.append("AND i.category_id = ?")
        params.append(category_id)
    if only_active:
        sql.append("AND i.active = 1")
    sql.append("ORDER BY i.name COLLATE NOCASE")
    return _rows(conn.execute(" ".join(sql), params))


def get_item(conn, item_id: int) -> dict:
    return _row(
        conn.execute(
            "SELECT i.*, c.name AS category_name FROM items i "
            "LEFT JOIN categories c ON c.id = i.category_id WHERE i.id = ?",
            (item_id,),
        )
    )


def save_item(conn, data: dict) -> int:
    """Thêm mới khi thiếu id, ngược lại cập nhật đồ đang có."""
    name = (data.get("name") or "").strip()
    sku = (data.get("sku") or "").strip().upper()
    if not name:
        raise ValueError("Tên món đồ không được để trống.")
    if not sku:
        raise ValueError("Mã SKU không được để trống.")
    if int(data.get("quantity", 0)) < 0:
        raise ValueError("Số lượng không được âm.")

    fields = dict(
        sku=sku,
        name=name,
        category_id=data.get("category_id") or None,
        size=(data.get("size") or "").strip(),
        color=(data.get("color") or "").strip(),
        quantity=int(data.get("quantity", 1)),
        rental_price=int(data.get("rental_price", 0)),
        deposit=int(data.get("deposit", 0)),
        active=1 if data.get("active", True) else 0,
        note=(data.get("note") or "").strip(),
    )
    try:
        if data.get("id"):
            sets = ", ".join(f"{k} = ?" for k in fields)
            conn.execute(
                f"UPDATE items SET {sets} WHERE id = ?", list(fields.values()) + [data["id"]]
            )
            conn.commit()
            return int(data["id"])
        cols = ", ".join(list(fields) + ["created_at"])
        marks = ", ".join(["?"] * (len(fields) + 1))
        cur = conn.execute(
            f"INSERT INTO items({cols}) VALUES({marks})", list(fields.values()) + [now_iso()]
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError as exc:
        raise ValueError(f"Mã SKU '{sku}' đã tồn tại.") from exc


def delete_item(conn, item_id: int) -> bool:
    """Xoá hẳn nếu món chưa từng nằm trong đơn nào; ngược lại chỉ ngưng kinh doanh.

    Trả về True khi đã xoá hẳn khỏi kho.
    """
    used = conn.execute(
        "SELECT COUNT(*) AS n FROM rental_items WHERE item_id = ?", (item_id,)
    ).fetchone()["n"]
    if used:
        conn.execute("UPDATE items SET active = 0 WHERE id = ?", (item_id,))
    else:
        conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()
    return not used


def suggest_sku(conn, name: str) -> str:
    """Gợi ý SKU duy nhất từ tên món đồ."""
    from .utils import slugify

    base = slugify(name)
    candidate, n = base, 1
    while _row(conn.execute("SELECT id FROM items WHERE sku = ?", (candidate,))):
        n += 1
        candidate = f"{base}-{n}"
    return candidate


# ------------------------------------------------------------- KHÁCH HÀNG
def list_customers(conn, keyword: str = "") -> list:
    sql = "SELECT * FROM customers WHERE 1 = 1"
    params = []
    if keyword:
        sql += " AND (name LIKE ? OR phone LIKE ? OR id_number LIKE ?)"
        params += [f"%{keyword}%"] * 3
    sql += " ORDER BY name COLLATE NOCASE"
    return _rows(conn.execute(sql, params))


def get_customer(conn, customer_id: int) -> dict:
    return _row(conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)))


def save_customer(conn, data: dict) -> int:
    name = (data.get("name") or "").strip()
    phone = normalize_phone(data.get("phone"))
    if not name:
        raise ValueError("Tên khách hàng không được để trống.")
    if not phone:
        raise ValueError("Số điện thoại không được để trống.")

    fields = dict(
        name=name,
        phone=phone,
        id_number=(data.get("id_number") or "").strip(),
        address=(data.get("address") or "").strip(),
        note=(data.get("note") or "").strip(),
        blacklisted=1 if data.get("blacklisted") else 0,
    )
    try:
        if data.get("id"):
            sets = ", ".join(f"{k} = ?" for k in fields)
            conn.execute(
                f"UPDATE customers SET {sets} WHERE id = ?",
                list(fields.values()) + [data["id"]],
            )
            conn.commit()
            return int(data["id"])
        cols = ", ".join(list(fields) + ["created_at"])
        marks = ", ".join(["?"] * (len(fields) + 1))
        cur = conn.execute(
            f"INSERT INTO customers({cols}) VALUES({marks})",
            list(fields.values()) + [now_iso()],
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError as exc:
        raise ValueError(f"Số điện thoại '{phone}' đã có trong danh sách khách hàng.") from exc


def delete_customer(conn, customer_id: int) -> bool:
    """Không cho xoá khách đã có đơn thuê để giữ toàn vẹn lịch sử."""
    used = conn.execute(
        "SELECT COUNT(*) AS n FROM rentals WHERE customer_id = ?", (customer_id,)
    ).fetchone()["n"]
    if used:
        return False
    conn.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
    conn.commit()
    return True


# ---------------------------------------------------------------- ĐƠN THUÊ
def new_rental_code(conn) -> str:
    last = _row(conn.execute("SELECT code FROM rentals ORDER BY id DESC LIMIT 1"))
    return next_code("DT", last["code"] if last else None)


def list_rentals(conn, status: str = None, keyword: str = "", customer_id: int = None) -> list:
    sql = [
        "SELECT r.*, c.name AS customer_name, c.phone AS customer_phone",
        "FROM rentals r JOIN customers c ON c.id = r.customer_id",
        "WHERE 1 = 1",
    ]
    params = []
    if status:
        sql.append("AND r.status = ?")
        params.append(status)
    if customer_id:
        sql.append("AND r.customer_id = ?")
        params.append(customer_id)
    if keyword:
        sql.append("AND (r.code LIKE ? OR c.name LIKE ? OR c.phone LIKE ?)")
        params += [f"%{keyword}%"] * 3
    sql.append("ORDER BY r.created_at DESC, r.id DESC")
    return _rows(conn.execute(" ".join(sql), params))


def get_rental(conn, rental_id: int) -> dict:
    rental = _row(
        conn.execute(
            "SELECT r.*, c.name AS customer_name, c.phone AS customer_phone, "
            "c.id_number AS customer_id_number, c.address AS customer_address "
            "FROM rentals r JOIN customers c ON c.id = r.customer_id WHERE r.id = ?",
            (rental_id,),
        )
    )
    if rental:
        rental["lines"] = list_rental_items(conn, rental_id)
        rental["payments"] = list_payments(conn, rental_id)
    return rental


def list_rental_items(conn, rental_id: int) -> list:
    return _rows(
        conn.execute(
            "SELECT ri.*, i.name AS item_name, i.sku, i.size, i.color "
            "FROM rental_items ri JOIN items i ON i.id = ri.item_id "
            "WHERE ri.rental_id = ? ORDER BY ri.id",
            (rental_id,),
        )
    )


def insert_rental(conn, data: dict) -> int:
    ts = now_iso()
    cur = conn.execute(
        "INSERT INTO rentals(code, customer_id, start_date, due_date, status, discount, "
        "extra_fee, late_fee, note, created_at, updated_at) "
        "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            data["code"],
            data["customer_id"],
            to_iso(data["start_date"]),
            to_iso(data["due_date"]),
            data.get("status", "renting"),
            int(data.get("discount", 0)),
            int(data.get("extra_fee", 0)),
            int(data.get("late_fee", 0)),
            (data.get("note") or "").strip(),
            ts,
            ts,
        ),
    )
    return cur.lastrowid


def insert_rental_item(conn, rental_id: int, line: dict) -> int:
    cur = conn.execute(
        "INSERT INTO rental_items(rental_id, item_id, quantity, price_per_day, deposit_per_unit) "
        "VALUES(?, ?, ?, ?, ?)",
        (
            rental_id,
            line["item_id"],
            int(line["quantity"]),
            int(line["price_per_day"]),
            int(line.get("deposit_per_unit", 0)),
        ),
    )
    return cur.lastrowid


def update_rental(conn, rental_id: int, **fields) -> None:
    if not fields:
        return
    if "start_date" in fields:
        fields["start_date"] = to_iso(fields["start_date"])
    if "due_date" in fields:
        fields["due_date"] = to_iso(fields["due_date"])
    if "return_date" in fields and fields["return_date"]:
        fields["return_date"] = to_iso(fields["return_date"])
    fields["updated_at"] = now_iso()
    sets = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(
        f"UPDATE rentals SET {sets} WHERE id = ?", list(fields.values()) + [rental_id]
    )
    conn.commit()


def delete_rental(conn, rental_id: int) -> None:
    conn.execute("DELETE FROM rentals WHERE id = ?", (rental_id,))
    conn.commit()


# -------------------------------------------------------------- THANH TOÁN
def list_payments(conn, rental_id: int) -> list:
    return _rows(
        conn.execute(
            "SELECT * FROM payments WHERE rental_id = ? ORDER BY id", (rental_id,)
        )
    )


def add_payment(conn, rental_id: int, amount: int, kind: str, method: str = "cash", note: str = "") -> int:
    if kind not in PAYMENT_LABELS:
        raise ValueError(f"Loại giao dịch không hợp lệ: {kind}")
    if int(amount) <= 0:
        raise ValueError("Số tiền phải lớn hơn 0.")
    cur = conn.execute(
        "INSERT INTO payments(rental_id, amount, kind, method, note, created_at) "
        "VALUES(?, ?, ?, ?, ?, ?)",
        (rental_id, int(amount), kind, method, (note or "").strip(), now_iso()),
    )
    conn.commit()
    return cur.lastrowid


def delete_payment(conn, payment_id: int) -> None:
    conn.execute("DELETE FROM payments WHERE id = ?", (payment_id,))
    conn.commit()


# ---------------------------------------------------------------- CẤU HÌNH
def get_settings(conn) -> dict:
    return {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM settings")}


def set_setting(conn, key: str, value) -> None:
    conn.execute(
        "INSERT INTO settings(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, str(value)),
    )
    conn.commit()
