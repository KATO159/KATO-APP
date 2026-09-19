"""Màn hình Khách hàng: danh bạ, lịch sử thuê và ghi chú."""

import streamlit as st

from .. import repo, services
from ..utils import fmt_date, fmt_money
from .common import confirm_button, flash, status_badge


def _customer_form(conn, cus: dict = None) -> None:
    cus = cus or {}
    with st.form(f"form_cus_{cus.get('id', 'new')}", clear_on_submit=not cus):
        c1, c2 = st.columns(2)
        name = c1.text_input("Họ và tên *", value=cus.get("name", ""))
        phone = c2.text_input("Số điện thoại *", value=cus.get("phone", ""))

        c3, c4 = st.columns(2)
        id_number = c3.text_input("CCCD / CMND", value=cus.get("id_number", ""))
        address = c4.text_input("Địa chỉ", value=cus.get("address", ""))

        note = st.text_area("Ghi chú", value=cus.get("note", ""), height=70)
        blacklisted = st.checkbox("⚠️ Khách cần lưu ý (hạn chế cho thuê)",
                                  value=bool(cus.get("blacklisted", 0)))

        if st.form_submit_button("💾 Lưu khách hàng", width="stretch", type="primary"):
            try:
                repo.save_customer(
                    conn,
                    {
                        "id": cus.get("id"),
                        "name": name,
                        "phone": phone,
                        "id_number": id_number,
                        "address": address,
                        "note": note,
                        "blacklisted": blacklisted,
                    },
                )
                flash(f"Đã lưu khách hàng '{name}'.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))


def render(conn, settings: dict) -> None:
    late_fee_rate = float(settings.get("late_fee_rate", 1.5))
    st.subheader("👥 Khách hàng")

    with st.expander("➕ Thêm khách hàng mới"):
        _customer_form(conn)

    keyword = st.text_input("🔎 Tìm theo tên / số điện thoại / CCCD", key="cus_kw")
    rows = repo.list_customers(conn, keyword)
    if not rows:
        st.info("Chưa có khách hàng nào khớp bộ lọc.")
        return

    st.dataframe(
        [
            {
                "Tên": r["name"],
                "Điện thoại": r["phone"],
                "CCCD": r["id_number"] or "—",
                "Địa chỉ": r["address"] or "—",
                "Lưu ý": "⚠️" if r["blacklisted"] else "",
            }
            for r in rows
        ],
        width="stretch",
        hide_index=True,
    )

    lookup = {f"{r['name']} · {r['phone']}": r["id"] for r in rows}
    pick = st.selectbox("Xem chi tiết khách hàng", ["—"] + list(lookup), key="cus_pick")
    if pick == "—":
        return

    cus_id = lookup[pick]
    cus = repo.get_customer(conn, cus_id)
    tab_ho_so, tab_lich_su = st.tabs(["📝 Hồ sơ", "🧾 Lịch sử thuê"])

    with tab_ho_so:
        _customer_form(conn, cus)
        if confirm_button("🗑️ Xoá khách hàng", key=f"del_cus_{cus_id}"):
            if repo.delete_customer(conn, cus_id):
                flash("Đã xoá khách hàng.")
            else:
                flash("Khách này đã có đơn thuê nên không xoá được (giữ lịch sử).", "warning")
            st.rerun()

    with tab_lich_su:
        rentals = repo.list_rentals(conn, customer_id=cus_id)
        if not rentals:
            st.info("Khách hàng chưa từng thuê đồ.")
            return
        tong = sum(services.rental_summary(conn, r, late_fee_rate)["total"]
                   for r in rentals if r["status"] != "cancelled")
        c1, c2 = st.columns(2)
        c1.metric("Số đơn", len(rentals))
        c2.metric("Tổng chi tiêu", fmt_money(tong))
        for rental in rentals:
            s = services.rental_summary(conn, rental, late_fee_rate)
            st.markdown(
                f"<div class='kato-card'><h4>{rental['code']} "
                f"{status_badge(rental['status'])}</h4>"
                f"<div class='kato-muted'>{fmt_date(rental['start_date'])} → "
                f"{fmt_date(rental['due_date'])}</div>"
                f"<div class='kato-row'><span>Tổng tiền</span>"
                f"<span class='kato-total'>{fmt_money(s['total'])}</span></div></div>",
                unsafe_allow_html=True,
            )
