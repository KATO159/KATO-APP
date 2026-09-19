"""Thành phần giao diện dùng chung: CSS, thẻ số liệu, nhãn trạng thái."""

import streamlit as st

from ..repo import STATUS_LABELS
from ..utils import fmt_money

STATUS_COLORS = {
    "booked": ("#f0ad4e", "rgba(240,173,78,.15)"),
    "renting": ("#4da3ff", "rgba(77,163,255,.15)"),
    "returned": ("#28a745", "rgba(40,167,69,.15)"),
    "cancelled": ("#8a8f98", "rgba(138,143,152,.15)"),
    "overdue": ("#ff4b4b", "rgba(255,75,75,.15)"),
}

CSS = """
<style>
    /* Thu gọn lề để dùng thoải mái trên màn hình điện thoại */
    /* Chừa chỗ cho thanh header cố định của Streamlit, tránh che mất điều hướng */
    .block-container { padding-top: 4.5rem; padding-bottom: 3rem; max-width: 1200px; }
    div[data-testid="stMetricValue"] { font-size: 1.35rem; }
    div[data-testid="stMetricLabel"] { font-size: .78rem; opacity: .85; }

    .kato-card {
        border: 1px solid rgba(140,140,160,.25); border-radius: 14px;
        padding: 14px 16px; margin-bottom: 10px; background: rgba(130,130,150,.06);
    }
    .kato-card h4 { margin: 0 0 6px 0; font-size: 1rem; }
    .kato-row { display: flex; justify-content: space-between; gap: 10px;
                font-size: .88rem; padding: 2px 0; }
    .kato-row span:last-child { font-weight: 600; text-align: right; }
    .kato-muted { opacity: .7; font-size: .82rem; }
    .kato-total { font-size: 1.15rem; font-weight: 800; color: #28a745; }
    .kato-badge {
        display: inline-block; padding: 2px 10px; border-radius: 999px;
        font-size: .74rem; font-weight: 700; white-space: nowrap;
    }
    .kato-hero {
        border-radius: 16px; padding: 16px 18px; margin-bottom: 14px;
        background: linear-gradient(135deg, rgba(40,167,69,.18), rgba(77,163,255,.12));
        border: 1px solid rgba(40,167,69,.3);
    }
    .kato-hero h2 { margin: 0; font-size: 1.25rem; }

    /* Thanh điều hướng dạng viên thuốc: tự xuống dòng thay vì tràn ngang */
    div[data-testid="stButtonGroup"] { flex-wrap: wrap; gap: 6px; }
    /* Nút Deploy chỉ gây rối trên điện thoại */
    div[data-testid="stToolbar"] button[data-testid="stBaseButton-header"] { display: none; }

    @media (max-width: 640px) {
        .block-container { padding-left: .8rem; padding-right: .8rem; }

        /* Giữ hàng số liệu nằm ngang thay vì kéo dài thành một cột dọc */
        div[data-testid="stHorizontalBlock"]:has(div[data-testid="stMetric"]) {
            flex-wrap: nowrap !important; gap: .4rem !important;
        }
        div[data-testid="stHorizontalBlock"]:has(div[data-testid="stMetric"])
            > div[data-testid="stColumn"] {
            min-width: 0 !important; width: auto !important; flex: 1 1 0 !important;
        }
        div[data-testid="stMetric"] { padding: 0; }
        div[data-testid="stMetricValue"] { font-size: .92rem !important; }
        div[data-testid="stMetricLabel"] p { font-size: .66rem !important; }
        .kato-hero h2 { font-size: 1.05rem; }
        button[data-testid="stBaseButton-pills"],
        button[data-testid="stBaseButton-pillsActive"] { font-size: .8rem; padding: 4px 10px; }
    }
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def status_badge(status: str, overdue: bool = False) -> str:
    """Nhãn màu cho trạng thái đơn; đơn quá hạn luôn hiển thị màu đỏ."""
    key = "overdue" if overdue else status
    label = "Quá hạn" if overdue else STATUS_LABELS.get(status, status)
    color, bg = STATUS_COLORS.get(key, STATUS_COLORS["cancelled"])
    return f'<span class="kato-badge" style="color:{color};background:{bg}">{label}</span>'


def money_rows(pairs) -> str:
    """Dựng các dòng 'nhãn — số tiền' trong thẻ thông tin."""
    out = []
    for label, value, *rest in pairs:
        cls = rest[0] if rest else ""
        text = value if isinstance(value, str) else fmt_money(value)
        out.append(f'<div class="kato-row"><span>{label}</span>'
                   f'<span class="{cls}">{text}</span></div>')
    return "".join(out)


def card(html: str) -> None:
    st.markdown(f'<div class="kato-card">{html}</div>', unsafe_allow_html=True)


def flash(message: str, kind: str = "success") -> None:
    """Ghi thông báo vào state để hiển thị sau khi rerun."""
    st.session_state["_flash"] = (kind, message)


def show_flash() -> None:
    data = st.session_state.pop("_flash", None)
    if not data:
        return
    kind, message = data
    {"success": st.success, "error": st.error, "warning": st.warning, "info": st.info}.get(
        kind, st.info
    )(message)


def confirm_button(label: str, key: str, help_text: str = None) -> bool:
    """Nút hai bước: bấm lần đầu để hỏi lại, lần hai mới thực thi."""
    state_key = f"_confirm_{key}"
    if st.session_state.get(state_key):
        c1, c2 = st.columns(2)
        if c1.button("✅ Xác nhận", key=f"{key}_yes", width="stretch", type="primary"):
            st.session_state.pop(state_key, None)
            return True
        if c2.button("↩️ Bỏ qua", key=f"{key}_no", width="stretch"):
            st.session_state.pop(state_key, None)
            st.rerun()
        return False
    if st.button(label, key=f"{key}_ask", width="stretch", help=help_text):
        st.session_state[state_key] = True
        st.rerun()
    return False
