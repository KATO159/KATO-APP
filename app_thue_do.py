"""KATO - Ứng dụng quản lý cho thuê đồ.

Chạy bằng:  streamlit run app_thue_do.py
Dữ liệu lưu trong tệp SQLite `thuedo.db` cạnh mã nguồn (đổi qua biến môi trường
KATO_THUEDO_DB nếu muốn để nơi khác).
"""

import streamlit as st

from thuedo import repo
from thuedo.db import DEFAULT_DB_PATH, get_db
from thuedo.ui import common, customers, dashboard, items, rentals, reports, settings_page

st.set_page_config(
    page_title="KATO - Quản Lý Thuê Đồ",
    page_icon="👗",
    layout="wide",
    initial_sidebar_state="collapsed",  # gọn hơn khi mở trên điện thoại
)

TRANG = {
    "🏠 Tổng quan": dashboard.render,
    "🧾 Đơn thuê": rentals.render,
    "📦 Kho đồ": items.render,
    "👥 Khách hàng": customers.render,
    "📊 Báo cáo": reports.render,
    "⚙️ Cài đặt": settings_page.render,
}


@st.cache_resource(show_spinner=False)
def _connection(db_path: str):
    """Một kết nối SQLite dùng chung cho cả phiên chạy Streamlit."""
    return get_db(db_path)


def main() -> None:
    common.inject_css()
    conn = _connection(DEFAULT_DB_PATH)
    settings = repo.get_settings(conn)

    with st.sidebar:
        st.markdown(f"### 👗 {settings.get('shop_name', 'KATO Thuê Đồ')}")
        if settings.get("shop_phone"):
            st.caption(f"☎️ {settings['shop_phone']}")
        if settings.get("shop_address"):
            st.caption(f"📍 {settings['shop_address']}")
        st.divider()
        st.caption(f"🗄️ Dữ liệu: `{DEFAULT_DB_PATH}`")

    # Dạng viên thuốc tự xuống dòng nên không bị tràn ngang trên điện thoại.
    chon = st.pills(
        "Điều hướng", list(TRANG), default=list(TRANG)[0],
        label_visibility="collapsed", key="nav",
    ) or list(TRANG)[0]
    common.show_flash()
    TRANG[chon](conn, settings)


if __name__ == "__main__":
    main()
