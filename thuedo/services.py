"""Nghiệp vụ cho thuê: kiểm tra tồn kho, tính tiền, lập đơn, trả đồ, báo cáo."""

from datetime import date, timedelta

from . import repo
from .db import transaction
from .utils import billed_days, days_between, parse_date, to_iso

OPEN = repo.RENTAL_OPEN_STATUSES


# ------------------------------------------------------------------ TỒN KHO
def committed_quantity(conn, item_id: int, start, due, exclude_rental_id: int = None) -> int:
    """Số lượng của một món đồ đã bị giữ bởi các đơn chưa trả có khoảng ngày giao nhau."""
    sql = (
        "SELECT COALESCE(SUM(ri.quantity - ri.returned_qty), 0) AS n "
        "FROM rental_items ri JOIN rentals r ON r.id = ri.rental_id "
        "WHERE ri.item_id = ? AND r.status IN (?, ?) "
        "AND date(r.start_date) <= date(?) AND date(?) <= date(r.due_date)"
    )
    params = [item_id, OPEN[0], OPEN[1], to_iso(due), to_iso(start)]
    if exclude_rental_id:
        sql += " AND r.id != ?"
        params.append(exclude_rental_id)
    return int(conn.execute(sql, params).fetchone()["n"])


def available_quantity(conn, item_id: int, start=None, due=None, exclude_rental_id: int = None) -> int:
    """Số lượng còn có thể cho thuê trong khoảng ngày yêu cầu."""
    item = repo.get_item(conn, item_id)
    if not item:
        return 0
    start = start or date.today()
    due = due or start
    used = committed_quantity(conn, item_id, start, due, exclude_rental_id)
    return max(0, int(item["quantity"]) - used)


def items_with_availability(conn, start=None, due=None, keyword: str = "",
                            category_id: int = None, only_active: bool = False) -> list:
    """Danh sách đồ kèm cột 'còn trống' cho khoảng ngày đang xét."""
    start = start or date.today()
    due = due or start
    rows = repo.list_items(conn, keyword=keyword, category_id=category_id, only_active=only_active)
    for row in rows:
        row["rented"] = committed_quantity(conn, row["id"], start, due)
        row["available"] = max(0, int(row["quantity"]) - row["rented"])
    return rows


# ------------------------------------------------------------- TÍNH TIỀN
def price_rental(rental: dict, lines: list, late_fee_rate: float = 1.5, today=None) -> dict:
    """Tính toàn bộ số tiền của một đơn: tiền thuê, cọc, phí trễ, còn phải thu."""
    start, due = parse_date(rental["start_date"]), parse_date(rental["due_date"])
    returned = parse_date(rental.get("return_date"))
    ref_day = returned or parse_date(today) or date.today()

    days = billed_days(start, due)
    per_day = sum(int(l["quantity"]) * int(l["price_per_day"]) for l in lines)
    deposit_total = sum(int(l["quantity"]) * int(l.get("deposit_per_unit", 0)) for l in lines)
    rent_total = per_day * days

    # Đơn đã trả thì dùng phí trễ đã chốt, đơn đang thuê thì ước tính theo hôm nay.
    late_days = days_between(due, ref_day, minimum=0)
    if rental.get("status") == "returned":
        late_fee = int(rental.get("late_fee") or 0)
    elif rental.get("status") == "cancelled":
        late_days, late_fee = 0, 0
    else:
        late_fee = int(round(per_day * late_days * float(late_fee_rate)))

    discount = int(rental.get("discount") or 0)
    extra_fee = int(rental.get("extra_fee") or 0)
    total = max(0, rent_total + late_fee + extra_fee - discount)

    return {
        "days": days,
        "per_day": per_day,
        "rent_total": rent_total,
        "deposit_total": deposit_total,
        "late_days": late_days,
        "late_fee": late_fee,
        "discount": discount,
        "extra_fee": extra_fee,
        "total": total,
    }


def payment_summary(payments: list) -> dict:
    """Gộp các giao dịch thành: đã thu tiền thuê, cọc đang giữ."""
    def total(kind):
        return sum(int(p["amount"]) for p in payments if p["kind"] == kind)

    paid = total("payment") - total("refund")
    deposit_held = total("deposit") - total("deposit_refund")
    return {"paid": paid, "deposit_held": deposit_held}


def rental_summary(conn, rental: dict, late_fee_rate: float = 1.5, today=None) -> dict:
    """Bảng tổng hợp đầy đủ của một đơn, dùng chung cho UI và báo cáo."""
    lines = rental.get("lines") or repo.list_rental_items(conn, rental["id"])
    payments = rental.get("payments") or repo.list_payments(conn, rental["id"])
    money = price_rental(rental, lines, late_fee_rate=late_fee_rate, today=today)
    money.update(payment_summary(payments))
    money["balance"] = money["total"] - money["paid"]
    money["lines"] = lines
    return money


# ------------------------------------------------------------- LẬP ĐƠN
def create_rental(conn, customer_id: int, start, due, lines: list,
                  discount: int = 0, note: str = "", status: str = "renting",
                  deposit_paid: int = 0, prepaid: int = 0) -> int:
    """Tạo đơn thuê mới sau khi kiểm tra tồn kho cho toàn bộ dòng hàng."""
    if not customer_id:
        raise ValueError("Vui lòng chọn khách hàng.")
    if not lines:
        raise ValueError("Đơn thuê phải có ít nhất một món đồ.")
    if parse_date(due) < parse_date(start):
        raise ValueError("Hạn trả phải bằng hoặc sau ngày bắt đầu thuê.")

    # Gộp các dòng trùng món để kiểm tra tồn kho chính xác.
    merged = {}
    for line in lines:
        qty = int(line.get("quantity", 0))
        if qty <= 0:
            continue
        key = int(line["item_id"])
        merged.setdefault(key, 0)
        merged[key] += qty
    if not merged:
        raise ValueError("Số lượng thuê phải lớn hơn 0.")

    prepared = []
    for item_id, qty in merged.items():
        item = repo.get_item(conn, item_id)
        if not item:
            raise ValueError(f"Không tìm thấy món đồ có mã #{item_id}.")
        free = available_quantity(conn, item_id, start, due)
        if qty > free:
            raise ValueError(
                f"'{item['name']}' chỉ còn {free} cái trống trong khoảng ngày này "
                f"(bạn đang chọn {qty})."
            )
        prepared.append(
            {
                "item_id": item_id,
                "quantity": qty,
                "price_per_day": int(item["rental_price"]),
                "deposit_per_unit": int(item["deposit"]),
            }
        )

    with transaction(conn):
        rental_id = repo.insert_rental(
            conn,
            {
                "code": repo.new_rental_code(conn),
                "customer_id": customer_id,
                "start_date": start,
                "due_date": due,
                "status": status,
                "discount": int(discount or 0),
                "note": note,
            },
        )
        for line in prepared:
            repo.insert_rental_item(conn, rental_id, line)

    if int(deposit_paid or 0) > 0:
        repo.add_payment(conn, rental_id, int(deposit_paid), "deposit", note="Nhận cọc khi giao đồ")
    if int(prepaid or 0) > 0:
        repo.add_payment(conn, rental_id, int(prepaid), "payment", note="Thanh toán trước")
    return rental_id


def extend_rental(conn, rental_id: int, new_due) -> None:
    """Gia hạn hạn trả sau khi chắc chắn không đụng đơn đặt trước khác."""
    rental = repo.get_rental(conn, rental_id)
    if not rental:
        raise ValueError("Không tìm thấy đơn thuê.")
    if rental["status"] not in OPEN:
        raise ValueError("Chỉ gia hạn được đơn đang đặt hoặc đang thuê.")
    if parse_date(new_due) < parse_date(rental["due_date"]):
        raise ValueError("Hạn mới phải sau hạn hiện tại.")

    for line in rental["lines"]:
        remaining = int(line["quantity"]) - int(line["returned_qty"])
        if remaining <= 0:
            continue
        free = available_quantity(
            conn, line["item_id"], rental["start_date"], new_due, exclude_rental_id=rental_id
        )
        if remaining > free:
            raise ValueError(
                f"Không gia hạn được: '{line['item_name']}' đã có đơn khác đặt trong khoảng gia hạn."
            )
    repo.update_rental(conn, rental_id, due_date=new_due)


def return_rental(conn, rental_id: int, return_date=None, damaged: dict = None,
                  extra_fee: int = 0, late_fee_rate: float = 1.5,
                  settle_amount: int = 0, refund_deposit: bool = True) -> dict:
    """Nhận đồ về: chốt phí trễ, ghi nhận hư hỏng, thu nốt tiền và hoàn cọc."""
    rental = repo.get_rental(conn, rental_id)
    if not rental:
        raise ValueError("Không tìm thấy đơn thuê.")
    if rental["status"] == "returned":
        raise ValueError("Đơn này đã được trả trước đó.")
    if rental["status"] == "cancelled":
        raise ValueError("Đơn đã huỷ, không thể trả đồ.")

    return_date = parse_date(return_date) or date.today()
    if return_date < parse_date(rental["start_date"]):
        raise ValueError("Ngày trả không thể trước ngày bắt đầu thuê.")

    damaged = damaged or {}
    money = price_rental(rental, rental["lines"], late_fee_rate=late_fee_rate)
    late_days = days_between(rental["due_date"], return_date, minimum=0)
    late_fee = int(round(money["per_day"] * late_days * float(late_fee_rate)))

    with transaction(conn):
        for line in rental["lines"]:
            dmg = int(damaged.get(line["id"], 0) or 0)
            dmg = max(0, min(dmg, int(line["quantity"])))
            conn.execute(
                "UPDATE rental_items SET returned_qty = quantity, damaged_qty = ? WHERE id = ?",
                (dmg, line["id"]),
            )
        conn.execute(
            "UPDATE rentals SET status = 'returned', return_date = ?, late_fee = ?, "
            "extra_fee = ?, updated_at = datetime('now', 'localtime') WHERE id = ?",
            (to_iso(return_date), late_fee, int(extra_fee or 0), rental_id),
        )

    if int(settle_amount or 0) > 0:
        repo.add_payment(conn, rental_id, int(settle_amount), "payment", note="Thanh toán khi trả đồ")

    refreshed = repo.get_rental(conn, rental_id)
    summary = rental_summary(conn, refreshed, late_fee_rate=late_fee_rate)
    if refund_deposit and summary["deposit_held"] > 0:
        repo.add_payment(
            conn, rental_id, summary["deposit_held"], "deposit_refund", note="Hoàn cọc khi trả đồ"
        )
        summary = rental_summary(conn, repo.get_rental(conn, rental_id), late_fee_rate=late_fee_rate)
    return summary


def cancel_rental(conn, rental_id: int, reason: str = "") -> None:
    """Huỷ đơn chưa trả và trả lại số lượng vào kho."""
    rental = repo.get_rental(conn, rental_id)
    if not rental:
        raise ValueError("Không tìm thấy đơn thuê.")
    if rental["status"] == "returned":
        raise ValueError("Đơn đã trả thì không huỷ được.")
    note = (rental["note"] or "").strip()
    if reason:
        note = f"{note}\n[Huỷ] {reason}".strip()
    repo.update_rental(conn, rental_id, status="cancelled", note=note)


# ------------------------------------------------------------- BÁO CÁO
def rentals_due_soon(conn, days_ahead: int = 3, today=None) -> list:
    """Đơn sắp đến hạn trong N ngày tới (chưa quá hạn)."""
    today = parse_date(today) or date.today()
    limit = today + timedelta(days=days_ahead)
    return [
        dict(r)
        for r in conn.execute(
            "SELECT r.*, c.name AS customer_name, c.phone AS customer_phone "
            "FROM rentals r JOIN customers c ON c.id = r.customer_id "
            "WHERE r.status IN (?, ?) AND date(r.due_date) BETWEEN date(?) AND date(?) "
            "ORDER BY date(r.due_date)",
            (OPEN[0], OPEN[1], to_iso(today), to_iso(limit)),
        )
    ]


def rentals_overdue(conn, today=None) -> list:
    """Đơn đã quá hạn trả mà chưa nhận lại đồ."""
    today = parse_date(today) or date.today()
    return [
        dict(r)
        for r in conn.execute(
            "SELECT r.*, c.name AS customer_name, c.phone AS customer_phone "
            "FROM rentals r JOIN customers c ON c.id = r.customer_id "
            "WHERE r.status IN (?, ?) AND date(r.due_date) < date(?) "
            "ORDER BY date(r.due_date)",
            (OPEN[0], OPEN[1], to_iso(today)),
        )
    ]


def dashboard_stats(conn, late_fee_rate: float = 1.5, today=None) -> dict:
    """Số liệu nhanh cho màn hình tổng quan."""
    today = parse_date(today) or date.today()
    month_start = today.replace(day=1)

    open_rentals = repo.list_rentals(conn)
    active = [r for r in open_rentals if r["status"] in OPEN]
    overdue = rentals_overdue(conn, today=today)

    revenue_month = 0
    for rental in open_rentals:
        if rental["status"] != "returned":
            continue
        ret = parse_date(rental["return_date"])
        if ret and month_start <= ret <= today:
            revenue_month += rental_summary(conn, rental, late_fee_rate, today=today)["total"]

    items_out = int(
        conn.execute(
            "SELECT COALESCE(SUM(ri.quantity - ri.returned_qty), 0) AS n "
            "FROM rental_items ri JOIN rentals r ON r.id = ri.rental_id "
            "WHERE r.status IN (?, ?)",
            OPEN,
        ).fetchone()["n"]
    )
    receivable = sum(
        max(0, rental_summary(conn, r, late_fee_rate, today=today)["balance"])
        for r in active
    )

    return {
        "active_count": len(active),
        "overdue_count": len(overdue),
        "revenue_month": revenue_month,
        "items_out": items_out,
        "receivable": receivable,
        "customer_count": int(
            conn.execute("SELECT COUNT(*) AS n FROM customers").fetchone()["n"]
        ),
        "item_count": int(conn.execute("SELECT COUNT(*) AS n FROM items").fetchone()["n"]),
    }


def revenue_by_day(conn, start, end, late_fee_rate: float = 1.5) -> list:
    """Doanh thu ghi nhận theo ngày trả đồ trong khoảng thời gian."""
    start, end = parse_date(start), parse_date(end)
    buckets = {}
    for rental in repo.list_rentals(conn, status="returned"):
        ret = parse_date(rental["return_date"])
        if not ret or not (start <= ret <= end):
            continue
        buckets[ret] = buckets.get(ret, 0) + rental_summary(conn, rental, late_fee_rate)["total"]
    return [{"date": d, "revenue": buckets[d]} for d in sorted(buckets)]


def top_items(conn, limit: int = 10) -> list:
    """Những món đồ được thuê nhiều nhất (không tính đơn đã huỷ)."""
    return [
        dict(r)
        for r in conn.execute(
            "SELECT i.name, i.sku, SUM(ri.quantity) AS total_qty, COUNT(DISTINCT r.id) AS orders "
            "FROM rental_items ri JOIN rentals r ON r.id = ri.rental_id "
            "JOIN items i ON i.id = ri.item_id "
            "WHERE r.status != 'cancelled' "
            "GROUP BY i.id ORDER BY total_qty DESC LIMIT ?",
            (limit,),
        )
    ]


def top_customers(conn, limit: int = 10, late_fee_rate: float = 1.5) -> list:
    """Khách hàng chi tiêu nhiều nhất tính trên các đơn đã trả."""
    totals = {}
    for rental in repo.list_rentals(conn):
        if rental["status"] == "cancelled":
            continue
        key = (rental["customer_name"], rental["customer_phone"])
        entry = totals.setdefault(key, {"name": key[0], "phone": key[1], "orders": 0, "revenue": 0})
        entry["orders"] += 1
        entry["revenue"] += rental_summary(conn, rental, late_fee_rate)["total"]
    return sorted(totals.values(), key=lambda x: x["revenue"], reverse=True)[:limit]
