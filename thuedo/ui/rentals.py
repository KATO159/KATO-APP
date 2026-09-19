"""Màn hình Đơn thuê: lập đơn mới, tra cứu, trả đồ, gia hạn, thu tiền và huỷ đơn."""

from datetime import date, timedelta

import streamlit as st

from .. import repo, services
from ..repo import PAYMENT_LABELS, STATUS_LABELS
from ..utils import fmt_date, fmt_money, overdue_days, parse_date
from .common import confirm_button, flash, money_rows, status_badge

CART_KEY = "rental_cart"


def _cart() -> list:
    return st.session_state.setdefault(CART_KEY, [])


# ------------------------------------------------------------- LẬP ĐƠN MỚI
def _tab_tao_don(conn, settings: dict) -> None:
    customers = repo.list_customers(conn)
    if not customers:
        st.warning("Cần có ít nhất một khách hàng. Vào mục **👥 Khách hàng** để thêm.")
        return

    c1, c2 = st.columns(2)
    start = c1.date_input("Ngày bắt đầu thuê", value=date.today(),
                          format="DD/MM/YYYY", key="new_start")
    due = c2.date_input("Hạn trả", value=date.today() + timedelta(days=2),
                        format="DD/MM/YYYY", key="new_due")
    if due < start:
        st.error("Hạn trả phải bằng hoặc sau ngày bắt đầu thuê.")
        return

    cus_map = {f"{c['name']} · {c['phone']}": c["id"] for c in customers}
    cus_pick = st.selectbox("Khách hàng", list(cus_map), key="new_cus")
    cus = repo.get_customer(conn, cus_map[cus_pick])
    if cus["blacklisted"]:
        st.warning(f"⚠️ Khách này được đánh dấu cần lưu ý. {cus['note'] or ''}")

    st.markdown("##### 🛒 Chọn đồ cho thuê")
    kho = services.items_with_availability(conn, start, due, only_active=True)
    con_trong = [r for r in kho if r["available"] > 0]
    if not con_trong:
        st.info("Không còn món nào trống trong khoảng ngày này.")
    else:
        item_map = {
            f"{r['name']} ({r['sku']}) · còn {r['available']} · {fmt_money(r['rental_price'])}/ngày": r
            for r in con_trong
        }
        pick = st.selectbox("Món đồ", list(item_map), key="new_item")
        chosen = item_map[pick]
        # Trừ đi phần đã nằm sẵn trong giỏ để không chọn vượt tồn kho.
        da_chon = sum(l["quantity"] for l in _cart() if l["item_id"] == chosen["id"])
        con_lai = max(0, chosen["available"] - da_chon)

        q1, q2 = st.columns([1, 2])
        qty = q1.number_input("Số lượng", min_value=1, max_value=max(1, con_lai),
                              value=1, step=1, key="new_qty", disabled=con_lai == 0)
        q2.markdown(f"<div class='kato-muted' style='padding-top:32px'>"
                    f"Còn có thể thêm: <b>{con_lai}</b></div>", unsafe_allow_html=True)

        if st.button("➕ Thêm vào đơn", width="stretch", disabled=con_lai == 0):
            for line in _cart():
                if line["item_id"] == chosen["id"]:
                    line["quantity"] += int(qty)
                    break
            else:
                _cart().append(
                    {
                        "item_id": chosen["id"],
                        "name": chosen["name"],
                        "sku": chosen["sku"],
                        "quantity": int(qty),
                        "price_per_day": int(chosen["rental_price"]),
                        "deposit_per_unit": int(chosen["deposit"]),
                    }
                )
            st.rerun()

    cart = _cart()
    if not cart:
        st.info("Giỏ đơn đang trống — hãy thêm ít nhất một món đồ.")
        return

    st.markdown("##### 🧾 Các món trong đơn")
    for idx, line in enumerate(cart):
        col_a, col_b = st.columns([5, 1])
        col_a.markdown(
            f"**{line['name']}** ×{line['quantity']} — "
            f"{fmt_money(line['price_per_day'])}/ngày · cọc {fmt_money(line['deposit_per_unit'])}"
        )
        if col_b.button("✕", key=f"rm_{idx}", help="Bỏ món này khỏi đơn"):
            cart.pop(idx)
            st.rerun()

    so_ngay = max(1, (due - start).days)
    tien_ngay = sum(l["quantity"] * l["price_per_day"] for l in cart)
    coc = sum(l["quantity"] * l["deposit_per_unit"] for l in cart)

    d1, d2 = st.columns(2)
    discount = d1.number_input("Giảm giá (đ)", min_value=0, step=50_000, value=0, key="new_disc")
    status = d2.selectbox("Trạng thái đơn", ["renting", "booked"],
                          format_func=lambda s: STATUS_LABELS[s], key="new_status")

    tong = max(0, tien_ngay * so_ngay - int(discount))
    st.markdown(
        "<div class='kato-card'>"
        + money_rows(
            [
                ("Số ngày thuê", f"{so_ngay} ngày"),
                ("Tiền thuê mỗi ngày", tien_ngay),
                ("Tổng tiền thuê", tien_ngay * so_ngay),
                ("Giảm giá", -int(discount)),
                ("Tiền cọc cần thu", coc),
                ("TỔNG THANH TOÁN", tong, "kato-total"),
            ]
        )
        + "</div>",
        unsafe_allow_html=True,
    )

    p1, p2 = st.columns(2)
    deposit_paid = p1.number_input("Nhận cọc (đ)", min_value=0, step=100_000,
                                   value=int(coc), key="new_dep")
    prepaid = p2.number_input("Khách trả trước (đ)", min_value=0, step=100_000,
                              value=0, key="new_pre")
    note = st.text_area("Ghi chú đơn", height=70, key="new_note")

    b1, b2 = st.columns([3, 1])
    if b1.button("✅ Tạo đơn thuê", width="stretch", type="primary"):
        try:
            rental_id = services.create_rental(
                conn,
                customer_id=cus["id"],
                start=start,
                due=due,
                lines=cart,
                discount=int(discount),
                note=note,
                status=status,
                deposit_paid=int(deposit_paid),
                prepaid=int(prepaid),
            )
            st.session_state[CART_KEY] = []
            st.session_state["focus_rental_id"] = rental_id
            flash(f"Đã tạo đơn {repo.get_rental(conn, rental_id)['code']}.")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
    if b2.button("🗑️ Xoá giỏ", width="stretch"):
        st.session_state[CART_KEY] = []
        st.rerun()


# ------------------------------------------------------------ CHI TIẾT ĐƠN
def _chi_tiet_don(conn, rental: dict, late_fee_rate: float) -> None:
    today = date.today()
    tre = overdue_days(rental["due_date"], today) if rental["status"] in services.OPEN else 0
    s = services.rental_summary(conn, rental, late_fee_rate, today=today)

    st.markdown(
        f"### {rental['code']} {status_badge(rental['status'], overdue=bool(tre))}",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"**{rental['customer_name']}** · {rental['customer_phone']}"
        + (f" · CCCD {rental['customer_id_number']}" if rental["customer_id_number"] else "")
    )
    st.caption(
        f"Thuê {fmt_date(rental['start_date'])} → hạn {fmt_date(rental['due_date'])}"
        + (f" · đã trả {fmt_date(rental['return_date'])}" if rental["return_date"] else "")
        + (f" · **trễ {tre} ngày**" if tre else "")
    )
    if rental["note"]:
        st.caption(f"📝 {rental['note']}")

    st.dataframe(
        [
            {
                "Món đồ": l["item_name"],
                "SKU": l["sku"],
                "SL": l["quantity"],
                "Giá/ngày": fmt_money(l["price_per_day"]),
                "Cọc/cái": fmt_money(l["deposit_per_unit"]),
                "Đã trả": l["returned_qty"],
                "Hư hỏng": l["damaged_qty"],
            }
            for l in s["lines"]
        ],
        width="stretch",
        hide_index=True,
    )

    st.markdown(
        "<div class='kato-card'>"
        + money_rows(
            [
                ("Số ngày tính tiền", f"{s['days']} ngày"),
                ("Tiền thuê", s["rent_total"]),
                ("Phí trễ hạn" + (f" ({s['late_days']} ngày)" if s["late_days"] else ""),
                 s["late_fee"]),
                ("Phí phát sinh", s["extra_fee"]),
                ("Giảm giá", -s["discount"]),
                ("TỔNG TIỀN", s["total"], "kato-total"),
                ("Đã thanh toán", s["paid"]),
                ("Còn phải thu", s["balance"]),
                ("Cọc đang giữ", s["deposit_held"]),
            ]
        )
        + "</div>",
        unsafe_allow_html=True,
    )

    if rental["status"] in services.OPEN:
        _hanh_dong_don_mo(conn, rental, s, late_fee_rate, today)

    with st.expander(f"💳 Lịch sử thanh toán ({len(rental['payments'])})"):
        for p in rental["payments"]:
            st.markdown(
                f"- {p['created_at'][:16]} · **{PAYMENT_LABELS.get(p['kind'], p['kind'])}** "
                f"{fmt_money(p['amount'])} ({p['method']}) {p['note']}"
            )
        with st.form(f"pay_{rental['id']}"):
            pc1, pc2 = st.columns(2)
            amount = pc1.number_input("Số tiền (đ)", min_value=0, step=100_000, value=0)
            kind = pc2.selectbox("Loại", list(PAYMENT_LABELS),
                                 format_func=lambda k: PAYMENT_LABELS[k])
            method = st.selectbox("Hình thức", ["cash", "transfer", "card"],
                                  format_func=lambda m: {"cash": "Tiền mặt",
                                                         "transfer": "Chuyển khoản",
                                                         "card": "Quẹt thẻ"}[m])
            if st.form_submit_button("➕ Ghi nhận giao dịch", width="stretch"):
                try:
                    repo.add_payment(conn, rental["id"], int(amount), kind, method)
                    flash("Đã ghi nhận giao dịch.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))


def _hanh_dong_don_mo(conn, rental: dict, s: dict, late_fee_rate: float, today: date) -> None:
    """Các thao tác chỉ áp dụng cho đơn đang đặt hoặc đang thuê."""
    tab_tra, tab_gia_han, tab_huy = st.tabs(["📥 Trả đồ", "📅 Gia hạn", "❌ Huỷ đơn"])

    with tab_tra:
        with st.form(f"ret_{rental['id']}"):
            return_date = st.date_input("Ngày trả thực tế", value=today, format="DD/MM/YYYY")
            st.caption("Phí trễ hạn được chốt theo ngày trả và hệ số trong phần Cài đặt.")

            damaged = {}
            for line in s["lines"]:
                damaged[line["id"]] = st.number_input(
                    f"Số cái hư hỏng — {line['item_name']}",
                    min_value=0, max_value=int(line["quantity"]), value=0, step=1,
                    key=f"dmg_{line['id']}",
                )
            extra_fee = st.number_input("Phí phát sinh: hư hỏng, giặt ủi… (đ)",
                                        min_value=0, step=100_000, value=0)
            settle = st.number_input("Khách thanh toán thêm (đ)", min_value=0, step=100_000,
                                     value=max(0, int(s["balance"])))
            refund = st.checkbox("Hoàn lại tiền cọc đang giữ", value=True)

            if st.form_submit_button("✅ Xác nhận đã nhận đồ về",
                                     width="stretch", type="primary"):
                try:
                    ket_qua = services.return_rental(
                        conn, rental["id"], return_date=return_date, damaged=damaged,
                        extra_fee=int(extra_fee), late_fee_rate=late_fee_rate,
                        settle_amount=int(settle), refund_deposit=refund,
                    )
                    flash(
                        f"Đã nhận đồ về. Tổng tiền {fmt_money(ket_qua['total'])}, "
                        f"còn phải thu {fmt_money(ket_qua['balance'])}."
                    )
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))

    with tab_gia_han:
        with st.form(f"ext_{rental['id']}"):
            han_moi = st.date_input(
                "Hạn trả mới",
                value=max(today, parse_date(rental["due_date"]) + timedelta(days=1)),
                format="DD/MM/YYYY",
            )
            if st.form_submit_button("📅 Gia hạn đơn", width="stretch"):
                try:
                    services.extend_rental(conn, rental["id"], han_moi)
                    flash(f"Đã gia hạn đến {fmt_date(han_moi)}.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))

    with tab_huy:
        ly_do = st.text_input("Lý do huỷ", key=f"cancel_reason_{rental['id']}")
        st.caption("Huỷ đơn sẽ trả toàn bộ số lượng về lại kho.")
        if confirm_button("❌ Huỷ đơn này", key=f"cancel_{rental['id']}"):
            try:
                services.cancel_rental(conn, rental["id"], ly_do)
                flash("Đã huỷ đơn và trả đồ về kho.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))


# ------------------------------------------------------------ DANH SÁCH ĐƠN
def _tab_danh_sach(conn, settings: dict) -> None:
    late_fee_rate = float(settings.get("late_fee_rate", 1.5))
    f1, f2 = st.columns([2, 1])
    keyword = f1.text_input("🔎 Tìm theo mã đơn / tên khách / SĐT", key="rental_kw")
    status_map = {"Tất cả": None, **{v: k for k, v in STATUS_LABELS.items()}}
    status_pick = f2.selectbox("Trạng thái", list(status_map), key="rental_status")

    rentals = repo.list_rentals(conn, status=status_map[status_pick], keyword=keyword)
    if not rentals:
        st.info("Chưa có đơn thuê nào khớp bộ lọc.")
        return

    today = date.today()
    st.dataframe(
        [
            {
                "Mã đơn": r["code"],
                "Khách": r["customer_name"],
                "SĐT": r["customer_phone"],
                "Bắt đầu": fmt_date(r["start_date"]),
                "Hạn trả": fmt_date(r["due_date"]),
                "Trạng thái": (
                    "Quá hạn"
                    if r["status"] in services.OPEN and overdue_days(r["due_date"], today)
                    else STATUS_LABELS[r["status"]]
                ),
                "Tổng tiền": fmt_money(
                    services.rental_summary(conn, r, late_fee_rate, today=today)["total"]
                ),
            }
            for r in rentals
        ],
        width="stretch",
        hide_index=True,
    )

    lookup = {f"{r['code']} · {r['customer_name']}": r["id"] for r in rentals}
    default_idx = 0
    focus = st.session_state.pop("focus_rental_id", None)
    if focus:
        for i, rid in enumerate(lookup.values(), start=1):
            if rid == focus:
                default_idx = i
                break

    pick = st.selectbox("Mở chi tiết đơn", ["—"] + list(lookup),
                        index=default_idx, key="rental_pick")
    if pick != "—":
        st.divider()
        _chi_tiet_don(conn, repo.get_rental(conn, lookup[pick]), late_fee_rate)


def render(conn, settings: dict) -> None:
    st.subheader("🧾 Đơn thuê")
    tab_ds, tab_moi = st.tabs(["📋 Danh sách đơn", "➕ Lập đơn mới"])
    with tab_ds:
        _tab_danh_sach(conn, settings)
    with tab_moi:
        _tab_tao_don(conn, settings)
