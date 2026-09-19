"""Màn hình Kho đồ: xem tồn kho theo ngày, thêm/sửa/ngưng kinh doanh món đồ."""

from datetime import date, timedelta

import streamlit as st

from .. import repo, services
from ..utils import fmt_money
from .common import confirm_button, flash


def _item_form(conn, item: dict = None) -> None:
    """Biểu mẫu dùng chung cho thêm mới và chỉnh sửa món đồ."""
    item = item or {}
    cats = repo.list_categories(conn)
    cat_names = ["(Không có)"] + [c["name"] for c in cats]
    cat_index = 0
    if item.get("category_id"):
        ten = next((c["name"] for c in cats if c["id"] == item["category_id"]), None)
        cat_index = cat_names.index(ten) if ten in cat_names else 0

    with st.form(f"form_item_{item.get('id', 'new')}", clear_on_submit=not item):
        c1, c2 = st.columns(2)
        name = c1.text_input("Tên món đồ *", value=item.get("name", ""))
        sku = c2.text_input("Mã SKU *", value=item.get("sku", ""),
                            help="Để trống khi thêm mới thì hệ thống tự sinh mã.")

        c3, c4 = st.columns(2)
        cat_choice = c3.selectbox("Danh mục", cat_names, index=cat_index)
        cat_new = c4.text_input("…hoặc tạo danh mục mới", value="")

        c5, c6, c7 = st.columns(3)
        size = c5.text_input("Size", value=item.get("size", ""))
        color = c6.text_input("Màu", value=item.get("color", ""))
        quantity = c7.number_input("Số lượng *", min_value=0, step=1,
                                   value=int(item.get("quantity", 1)))

        c8, c9 = st.columns(2)
        price = c8.number_input("Giá thuê / ngày (đ) *", min_value=0, step=10_000,
                                value=int(item.get("rental_price", 0)))
        deposit = c9.number_input("Tiền cọc / cái (đ)", min_value=0, step=50_000,
                                  value=int(item.get("deposit", 0)))

        note = st.text_area("Ghi chú", value=item.get("note", ""), height=70)
        active = st.checkbox("Đang kinh doanh", value=bool(item.get("active", 1)))

        if st.form_submit_button("💾 Lưu món đồ", width="stretch", type="primary"):
            try:
                cat_id = (
                    repo.get_or_create_category(conn, cat_new)
                    if cat_new.strip()
                    else next((c["id"] for c in cats if c["name"] == cat_choice), None)
                )
                repo.save_item(
                    conn,
                    {
                        "id": item.get("id"),
                        "sku": sku.strip() or repo.suggest_sku(conn, name),
                        "name": name,
                        "category_id": cat_id,
                        "size": size,
                        "color": color,
                        "quantity": quantity,
                        "rental_price": price,
                        "deposit": deposit,
                        "note": note,
                        "active": active,
                    },
                )
                flash(f"Đã lưu '{name}'.")
                st.session_state.pop("edit_item_id", None)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))


def render(conn, settings: dict) -> None:
    st.subheader("📦 Kho đồ cho thuê")

    with st.expander("➕ Thêm món đồ mới"):
        _item_form(conn)

    cats = repo.list_categories(conn)
    f1, f2 = st.columns([2, 1])
    keyword = f1.text_input("🔎 Tìm theo tên / SKU / màu / size", key="item_kw")
    cat_map = {"Tất cả danh mục": None, **{c["name"]: c["id"] for c in cats}}
    cat_pick = f2.selectbox("Danh mục", list(cat_map), key="item_cat")

    f3, f4 = st.columns(2)
    start = f3.date_input("Kiểm tra còn trống từ", value=date.today(), format="DD/MM/YYYY")
    due = f4.date_input("đến ngày", value=date.today() + timedelta(days=1), format="DD/MM/YYYY")
    if due < start:
        st.warning("Ngày kết thúc đang trước ngày bắt đầu, tạm tính theo một ngày.")
        due = start

    rows = services.items_with_availability(
        conn, start, due, keyword=keyword, category_id=cat_map[cat_pick]
    )
    if not rows:
        st.info("Chưa có món đồ nào khớp bộ lọc.")
        return

    st.caption(f"Tìm thấy {len(rows)} món · cột **Còn trống** tính theo khoảng ngày ở trên.")
    st.dataframe(
        [
            {
                "SKU": r["sku"],
                "Tên": r["name"],
                "Danh mục": r["category_name"] or "—",
                "Size": r["size"] or "—",
                "Màu": r["color"] or "—",
                "Tổng": r["quantity"],
                "Đang thuê": r["rented"],
                "Còn trống": r["available"],
                "Giá/ngày": fmt_money(r["rental_price"]),
                "Cọc": fmt_money(r["deposit"]),
                "Trạng thái": "Đang bán" if r["active"] else "Ngưng",
            }
            for r in rows
        ],
        width="stretch",
        hide_index=True,
    )

    st.markdown("##### ✏️ Sửa một món đồ")
    lookup = {f"{r['sku']} · {r['name']}": r["id"] for r in rows}
    pick = st.selectbox("Chọn món cần sửa", ["—"] + list(lookup), key="item_edit_pick")
    if pick != "—":
        item_id = lookup[pick]
        _item_form(conn, repo.get_item(conn, item_id))
        if confirm_button("🗑️ Xoá / ngưng kinh doanh", key=f"del_item_{item_id}",
                          help_text="Món đã từng cho thuê sẽ được chuyển sang trạng thái Ngưng."):
            xoa_han = repo.delete_item(conn, item_id)
            flash("Đã xoá khỏi kho." if xoa_han else
                  "Món đồ đã có lịch sử thuê nên được chuyển sang trạng thái Ngưng kinh doanh.")
            st.rerun()
