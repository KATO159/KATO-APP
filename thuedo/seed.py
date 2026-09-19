"""Nạp dữ liệu mẫu để xem thử ứng dụng ngay khi mới cài."""

from datetime import date, timedelta

from . import repo, services


def has_data(conn) -> bool:
    return bool(conn.execute("SELECT COUNT(*) AS n FROM items").fetchone()["n"])


def seed_demo(conn, today=None) -> dict:
    """Tạo danh mục, đồ, khách và vài đơn thuê mẫu ở các trạng thái khác nhau."""
    today = today or date.today()

    danh_muc = {
        ten: repo.get_or_create_category(conn, ten)
        for ten in ["Áo dài", "Váy cưới", "Vest nam", "Phụ kiện", "Máy ảnh"]
    }

    mau_do = [
        ("Áo dài đỏ thêu rồng", "Áo dài", "M", "Đỏ", 3, 250_000, 500_000),
        ("Áo dài vàng hoàng gia", "Áo dài", "L", "Vàng", 2, 300_000, 600_000),
        ("Váy cưới đuôi cá", "Váy cưới", "S", "Trắng", 1, 800_000, 2_000_000),
        ("Váy cưới công chúa", "Váy cưới", "M", "Trắng kem", 2, 700_000, 2_000_000),
        ("Vest nam đen", "Vest nam", "L", "Đen", 4, 350_000, 700_000),
        ("Vest nam xanh navy", "Vest nam", "M", "Xanh navy", 2, 400_000, 700_000),
        ("Giày cao gót 7cm", "Phụ kiện", "38", "Bạc", 5, 80_000, 150_000),
        ("Vương miện đá pha lê", "Phụ kiện", "", "Bạc", 3, 120_000, 300_000),
        ("Máy ảnh Canon 5D IV", "Máy ảnh", "", "Đen", 1, 600_000, 5_000_000),
        ("Đèn flash Godox", "Máy ảnh", "", "Đen", 2, 150_000, 800_000),
    ]
    ids = {}
    for ten, cat, size, mau, sl, gia, coc in mau_do:
        ids[ten] = repo.save_item(
            conn,
            {
                "sku": repo.suggest_sku(conn, ten),
                "name": ten,
                "category_id": danh_muc[cat],
                "size": size,
                "color": mau,
                "quantity": sl,
                "rental_price": gia,
                "deposit": coc,
            },
        )

    khach = [
        ("Nguyễn Thị Mai", "0901234567", "079300001111", "12 Lê Lợi, Q.1, TP.HCM"),
        ("Trần Văn Hùng", "0912345678", "079300002222", "45 Nguyễn Huệ, Q.1, TP.HCM"),
        ("Lê Thu Hà", "0923456789", "079300003333", "7 Hai Bà Trưng, Q.3, TP.HCM"),
        ("Phạm Minh Tuấn", "0934567890", "", "89 Cách Mạng Tháng 8, Q.10, TP.HCM"),
    ]
    kh_ids = [
        repo.save_customer(conn, {"name": n, "phone": p, "id_number": cc, "address": dc})
        for n, p, cc, dc in khach
    ]

    # Đơn 1: đang thuê, còn trong hạn.
    services.create_rental(
        conn, kh_ids[0], today - timedelta(days=1), today + timedelta(days=2),
        lines=[{"item_id": ids["Áo dài đỏ thêu rồng"], "quantity": 1},
               {"item_id": ids["Giày cao gót 7cm"], "quantity": 1}],
        deposit_paid=650_000, prepaid=300_000, note="Chụp ảnh kỷ yếu",
    )

    # Đơn 2: đã quá hạn để thấy cảnh báo trên màn hình tổng quan.
    services.create_rental(
        conn, kh_ids[1], today - timedelta(days=8), today - timedelta(days=3),
        lines=[{"item_id": ids["Vest nam đen"], "quantity": 2}],
        deposit_paid=1_400_000, note="Đám cưới bạn thân",
    )

    # Đơn 3: đặt trước cho tuần sau.
    services.create_rental(
        conn, kh_ids[2], today + timedelta(days=6), today + timedelta(days=8),
        lines=[{"item_id": ids["Váy cưới đuôi cá"], "quantity": 1},
               {"item_id": ids["Vương miện đá pha lê"], "quantity": 1}],
        status="booked", deposit_paid=2_300_000, note="Đặt cọc giữ đồ",
    )

    # Đơn 4: đã hoàn tất, có doanh thu ghi nhận trong tháng.
    rid = services.create_rental(
        conn, kh_ids[3], today - timedelta(days=10), today - timedelta(days=8),
        lines=[{"item_id": ids["Máy ảnh Canon 5D IV"], "quantity": 1},
               {"item_id": ids["Đèn flash Godox"], "quantity": 1}],
        deposit_paid=5_800_000,
    )
    services.return_rental(conn, rid, return_date=today - timedelta(days=8),
                           settle_amount=1_500_000)

    return {"items": len(ids), "customers": len(kh_ids), "rentals": 4}


def reset_all(conn) -> None:
    """Xoá sạch dữ liệu nghiệp vụ, giữ nguyên phần cấu hình cửa hàng."""
    for bang in ["payments", "rental_items", "rentals", "items", "customers", "categories"]:
        conn.execute(f"DELETE FROM {bang}")
    conn.execute("DELETE FROM sqlite_sequence")
    conn.commit()
