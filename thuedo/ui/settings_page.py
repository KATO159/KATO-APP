"""Màn hình Cài đặt: thông tin cửa hàng, hệ số phí trễ, dữ liệu mẫu, xuất CSV."""

import csv
import io

import streamlit as st

from .. import repo, seed
from .common import confirm_button, flash


def _csv_bytes(rows: list) -> bytes:
    if not rows:
        return b""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")  # BOM để Excel đọc đúng tiếng Việt


def render(conn, settings: dict) -> None:
    st.subheader("⚙️ Cài đặt")

    with st.form("form_settings"):
        st.markdown("##### 🏪 Thông tin cửa hàng")
        shop_name = st.text_input("Tên cửa hàng", value=settings.get("shop_name", ""))
        c1, c2 = st.columns(2)
        shop_phone = c1.text_input("Điện thoại", value=settings.get("shop_phone", ""))
        shop_address = c2.text_input("Địa chỉ", value=settings.get("shop_address", ""))

        st.markdown("##### 💰 Quy tắc tính tiền")
        late_rate = st.number_input(
            "Hệ số phí trễ hạn (nhân với giá thuê mỗi ngày)",
            min_value=0.0, max_value=10.0, step=0.5,
            value=float(settings.get("late_fee_rate", 1.5)),
            help="Ví dụ hệ số 1.5: trễ 1 ngày thì tính thêm 150% giá thuê một ngày.",
        )

        if st.form_submit_button("💾 Lưu cài đặt", width="stretch", type="primary"):
            repo.set_setting(conn, "shop_name", shop_name)
            repo.set_setting(conn, "shop_phone", shop_phone)
            repo.set_setting(conn, "shop_address", shop_address)
            repo.set_setting(conn, "late_fee_rate", late_rate)
            flash("Đã lưu cài đặt.")
            st.rerun()

    st.divider()
    st.markdown("##### 🗂️ Danh mục")
    cats = repo.list_categories(conn)
    cc1, cc2 = st.columns([2, 1])
    ten_moi = cc1.text_input("Thêm danh mục mới", key="cat_new")
    if cc2.button("➕ Thêm", width="stretch"):
        try:
            repo.add_category(conn, ten_moi)
            flash(f"Đã thêm danh mục '{ten_moi}'.")
            st.rerun()
        except Exception:
            st.error("Danh mục đã tồn tại hoặc tên không hợp lệ.")
    if cats:
        xoa = st.selectbox("Xoá danh mục", ["—"] + [c["name"] for c in cats], key="cat_del")
        if xoa != "—" and st.button("🗑️ Xoá danh mục này"):
            cat_id = next(c["id"] for c in cats if c["name"] == xoa)
            repo.delete_category(conn, cat_id)
            flash(f"Đã xoá danh mục '{xoa}'. Các món đồ liên quan được chuyển về 'không danh mục'.")
            st.rerun()

    st.divider()
    st.markdown("##### 📤 Xuất dữ liệu ra CSV")
    e1, e2, e3 = st.columns(3)
    e1.download_button(
        "📦 Kho đồ", _csv_bytes(repo.list_items(conn)), "kho_do.csv",
        "text/csv", width="stretch",
    )
    e2.download_button(
        "👥 Khách hàng", _csv_bytes(repo.list_customers(conn)), "khach_hang.csv",
        "text/csv", width="stretch",
    )
    e3.download_button(
        "🧾 Đơn thuê", _csv_bytes(repo.list_rentals(conn)), "don_thue.csv",
        "text/csv", width="stretch",
    )

    st.divider()
    st.markdown("##### 🧪 Dữ liệu mẫu")
    if seed.has_data(conn):
        st.caption("Cơ sở dữ liệu đã có dữ liệu. Nạp mẫu sẽ thêm chồng lên dữ liệu hiện có.")
    if st.button("🌱 Nạp dữ liệu mẫu", width="stretch"):
        try:
            ket_qua = seed.seed_demo(conn)
            flash(
                f"Đã nạp {ket_qua['items']} món đồ, {ket_qua['customers']} khách hàng "
                f"và {ket_qua['rentals']} đơn thuê mẫu."
            )
            st.rerun()
        except Exception as exc:
            st.error(f"Không nạp được dữ liệu mẫu: {exc}")

    st.markdown("##### ⚠️ Vùng nguy hiểm")
    st.caption("Xoá toàn bộ đồ, khách hàng, đơn thuê và thanh toán. Cài đặt cửa hàng được giữ lại.")
    if confirm_button("🔥 Xoá sạch dữ liệu", key="wipe_all"):
        seed.reset_all(conn)
        flash("Đã xoá toàn bộ dữ liệu nghiệp vụ.", "warning")
        st.rerun()

    st.divider()
    tong = {
        "Món đồ": len(repo.list_items(conn)),
        "Khách hàng": len(repo.list_customers(conn)),
        "Đơn thuê": len(repo.list_rentals(conn)),
    }
    st.caption(" · ".join(f"{k}: **{v}**" for k, v in tong.items()))
