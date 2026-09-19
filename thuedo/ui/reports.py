"""Màn hình Báo cáo: doanh thu theo ngày, đồ thuê nhiều, khách chi tiêu nhiều."""

from datetime import date, timedelta

import streamlit as st

from .. import repo, services
from ..utils import fmt_date, fmt_money, parse_date


def render(conn, settings: dict) -> None:
    late_fee_rate = float(settings.get("late_fee_rate", 1.5))
    st.subheader("📊 Báo cáo kinh doanh")

    today = date.today()
    c1, c2 = st.columns(2)
    start = c1.date_input("Từ ngày", value=today.replace(day=1), format="DD/MM/YYYY")
    end = c2.date_input("Đến ngày", value=today, format="DD/MM/YYYY")
    if end < start:
        st.error("Khoảng thời gian không hợp lệ.")
        return

    rows = services.revenue_by_day(conn, start, end, late_fee_rate)
    tong_dt = sum(r["revenue"] for r in rows)
    don_da_tra = [
        r for r in repo.list_rentals(conn, status="returned")
        if r["return_date"] and start <= parse_date(r["return_date"]) <= end
    ]

    m1, m2, m3 = st.columns(3)
    m1.metric("Doanh thu", fmt_money(tong_dt))
    m2.metric("Đơn hoàn tất", len(don_da_tra))
    m3.metric("Trung bình / đơn", fmt_money(tong_dt / len(don_da_tra)) if don_da_tra else "0đ")

    st.caption("Doanh thu được ghi nhận theo **ngày trả đồ** của đơn đã hoàn tất.")

    if rows:
        st.markdown("##### 📈 Doanh thu theo ngày")
        st.bar_chart(
            {"Doanh thu": {r["date"].strftime("%d/%m"): r["revenue"] for r in rows}},
            width="stretch",
        )
    else:
        st.info("Chưa có đơn nào hoàn tất trong khoảng thời gian này.")

    tab_do, tab_khach, tab_kho = st.tabs(["🏆 Đồ thuê nhiều", "👑 Khách hàng", "📦 Tình trạng kho"])

    with tab_do:
        top = services.top_items(conn)
        if not top:
            st.info("Chưa có dữ liệu.")
        else:
            st.dataframe(
                [{"Món đồ": r["name"], "SKU": r["sku"],
                  "Lượt thuê": r["orders"], "Tổng số cái": r["total_qty"]} for r in top],
                width="stretch", hide_index=True,
            )

    with tab_khach:
        top = services.top_customers(conn, late_fee_rate=late_fee_rate)
        if not top:
            st.info("Chưa có dữ liệu.")
        else:
            st.dataframe(
                [{"Khách hàng": r["name"], "SĐT": r["phone"],
                  "Số đơn": r["orders"], "Tổng chi tiêu": fmt_money(r["revenue"])} for r in top],
                width="stretch", hide_index=True,
            )

    with tab_kho:
        kho = services.items_with_availability(conn, today, today)
        het_hang = [r for r in kho if r["available"] == 0 and r["quantity"] > 0]
        if het_hang:
            st.warning(f"{len(het_hang)} món đang cho thuê hết, không còn cái nào trống hôm nay.")
        st.dataframe(
            [{"Món đồ": r["name"], "Tổng": r["quantity"],
              "Đang thuê": r["rented"], "Còn trống": r["available"]} for r in kho],
            width="stretch", hide_index=True,
        )

    st.divider()
    st.markdown("##### 🗓️ Lịch trả đồ 7 ngày tới")
    sap_toi = services.rentals_due_soon(conn, days_ahead=7, today=today)
    if not sap_toi:
        st.info("Không có đơn nào đến hạn trong 7 ngày tới.")
    else:
        st.dataframe(
            [{"Hạn trả": fmt_date(r["due_date"]), "Mã đơn": r["code"],
              "Khách": r["customer_name"], "SĐT": r["customer_phone"]} for r in sap_toi],
            width="stretch", hide_index=True,
        )
