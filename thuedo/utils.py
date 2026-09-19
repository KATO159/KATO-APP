"""Hàm tiện ích dùng chung: định dạng tiền tệ, ngày tháng, sinh mã đơn."""

import re
import unicodedata
from datetime import date, datetime, timedelta

DATE_FMT = "%Y-%m-%d"
DISPLAY_DATE_FMT = "%d/%m/%Y"


def parse_date(value) -> date:
    """Nhận date/datetime/chuỗi ISO và luôn trả về đối tượng date."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not value:
        return None
    return datetime.strptime(str(value)[:10], DATE_FMT).date()


def to_iso(value) -> str:
    """Chuẩn hoá ngày về chuỗi YYYY-MM-DD để lưu xuống SQLite."""
    d = parse_date(value)
    return d.strftime(DATE_FMT) if d else None


def fmt_date(value) -> str:
    """Hiển thị ngày theo định dạng Việt Nam dd/mm/yyyy."""
    d = parse_date(value)
    return d.strftime(DISPLAY_DATE_FMT) if d else "—"


def fmt_money(amount, suffix: str = "đ") -> str:
    """Định dạng số tiền VND: 1250000 -> '1.250.000đ'."""
    try:
        amount = int(round(float(amount or 0)))
    except (TypeError, ValueError):
        amount = 0
    sign = "-" if amount < 0 else ""
    return f"{sign}{abs(amount):,}".replace(",", ".") + suffix


def days_between(start, end, minimum: int = 0) -> int:
    """Số ngày giữa hai mốc, không nhỏ hơn `minimum`."""
    s, e = parse_date(start), parse_date(end)
    if not s or not e:
        return minimum
    return max(minimum, (e - s).days)


def billed_days(start, due) -> int:
    """Số ngày tính tiền theo hợp đồng - thuê trong ngày vẫn tính 1 ngày."""
    return days_between(start, due, minimum=1) or 1


def overdue_days(due, today=None) -> int:
    """Số ngày trễ hạn so với hôm nay (hoặc so với ngày trả thực tế)."""
    return days_between(due, today or date.today(), minimum=0)


def ranges_overlap(a_start, a_end, b_start, b_end) -> bool:
    """Hai khoảng ngày có giao nhau hay không (dùng để kiểm tra đặt trùng)."""
    a_start, a_end = parse_date(a_start), parse_date(a_end)
    b_start, b_end = parse_date(b_start), parse_date(b_end)
    return a_start <= b_end and b_start <= a_end


def slugify(text: str) -> str:
    """Bỏ dấu tiếng Việt và viết hoa, dùng để gợi ý mã SKU."""
    text = unicodedata.normalize("NFD", str(text or ""))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.replace("đ", "d").replace("Đ", "D")
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").upper()
    return text[:20] or "SP"


def next_code(prefix: str, last_code: str = None, today=None) -> str:
    """Sinh mã tăng dần theo ngày, ví dụ DT250919-0003."""
    stamp = (today or date.today()).strftime("%y%m%d")
    seq = 1
    if last_code and last_code.startswith(f"{prefix}{stamp}-"):
        try:
            seq = int(last_code.rsplit("-", 1)[1]) + 1
        except (ValueError, IndexError):
            seq = 1
    return f"{prefix}{stamp}-{seq:04d}"


def normalize_phone(phone: str) -> str:
    """Chỉ giữ chữ số và dấu + để so khớp số điện thoại nhất quán."""
    return re.sub(r"[^\d+]", "", str(phone or "")).strip()


def date_range(start, end):
    """Sinh từng ngày trong khoảng [start, end] - phục vụ báo cáo theo ngày."""
    s, e = parse_date(start), parse_date(end)
    while s <= e:
        yield s
        s += timedelta(days=1)
