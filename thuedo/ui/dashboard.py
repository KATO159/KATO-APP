"""Màn hình Tổng quan: số liệu nhanh, cảnh báo quá hạn và lịch trả sắp tới."""

from datetime import date

import streamlit as st

from .. import repo, services
from ..utils import fmt_date, fmt_money, overdue_days
from .common import card, money_rows, status_badge


def _rental_card(conn, rental: dict, late_fee_rate: float, today: date) -> None:
    tre = overdue_days(rental["due_date"], today)
    summary = services.rental_summary(conn, rental, late_fee_rate, today=today)
    mon = ", ".join(f"{l['item_name']} x{l['quantity']}" for l in summary["lines"]) or "—"
    han = fmt_date(rental["due_date"])
    dong_han = f"Hạn trả: {han}" + (f" · trễ {tre} ngày" if tre else "")
    card(
        f"<h4>{rental['code']} {status_badge(rental['status'], overdue=bool(tre))}</h4>"
        f"<div class='kato-row'><span>{rental['customer_name']}</span>"
        f"<span>{rental['customer_phone']}</span></div>"
        f"<div class='kato-muted'>{mon}</div>"
        f"<div class='kato-muted'>{dong_han}</div>"
        + money_rows(
            [("Tổng tiền", summary["total"], "kato-total"),
             ("Còn phải thu", summary["balance"])]
        )
    )


def render(conn, settings: dict) -> None:
    late_fee_rate = float(settings.get("late_fee_rate", 1.5))
    today = date.today()

    st.markdown(
        f"<div class='kato-hero'><h2>👋 {settings.get('shop_name', 'Cửa hàng')}</h2>"
        f"<div class='kato-muted'>Hôm nay {fmt_date(today)}</div></div>",
        unsafe_allow_html=True,
    )

    stats = services.dashboard_stats(conn, late_fee_rate, today=today)
    c1, c2, c3 = st.columns(3)
    c1.metric("Đơn đang mở", stats["active_count"])
    c2.metric("Đơn quá hạn", stats["overdue_count"])
    c3.metric("Đồ đang ở ngoài", stats["items_out"])

    c4, c5, c6 = st.columns(3)
    c4.metric("Doanh thu tháng", fmt_money(stats["revenue_month"]))
    c5.metric("Còn phải thu", fmt_money(stats["receivable"]))
    c6.metric("Khách hàng", stats["customer_count"])

    if stats["item_count"] == 0:
        st.info(
            "Kho đồ đang trống. Vào mục **📦 Kho đồ** để thêm món đầu tiên, "
            "hoặc vào **⚙️ Cài đặt** để nạp dữ liệu mẫu xem thử."
        )
        return

    st.divider()
    qua_han = services.rentals_overdue(conn, today=today)
    sap_han = services.rentals_due_soon(conn, days_ahead=3, today=today)

    tab_qh, tab_sh, tab_moi = st.tabs(
        [f"🚨 Quá hạn ({len(qua_han)})", f"⏰ Sắp đến hạn ({len(sap_han)})", "🆕 Đơn mới nhất"]
    )

    with tab_qh:
        if not qua_han:
            st.success("Không có đơn nào quá hạn. Tuyệt vời!")
        for rental in qua_han:
            _rental_card(conn, rental, late_fee_rate, today)

    with tab_sh:
        if not sap_han:
            st.info("Không có đơn nào đến hạn trong 3 ngày tới.")
        for rental in sap_han:
            _rental_card(conn, rental, late_fee_rate, today)

    with tab_moi:
        gan_day = repo.list_rentals(conn)[:5]
        if not gan_day:
            st.info("Chưa có đơn thuê nào.")
        for rental in gan_day:
            _rental_card(conn, rental, late_fee_rate, today)
