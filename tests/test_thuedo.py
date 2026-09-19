"""Kiểm thử lõi nghiệp vụ quản lý thuê đồ - chạy bằng: python3 -m unittest discover tests"""

import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from thuedo import repo, services  # noqa: E402
from thuedo.db import get_db  # noqa: E402
from thuedo.utils import billed_days, fmt_money, next_code, normalize_phone, slugify  # noqa: E402


class BaseCase(unittest.TestCase):
    def setUp(self):
        self.conn = get_db(":memory:")
        self.today = date(2026, 9, 19)
        self.cat = repo.add_category(self.conn, "Áo dài")
        self.ao_id = repo.save_item(
            self.conn,
            {"sku": "AO-DAI-DO", "name": "Áo dài đỏ", "category_id": self.cat,
             "quantity": 3, "rental_price": 200_000, "deposit": 500_000},
        )
        self.giay_id = repo.save_item(
            self.conn,
            {"sku": "GIAY-01", "name": "Giày cao gót", "quantity": 1,
             "rental_price": 50_000, "deposit": 100_000},
        )
        self.kh_id = repo.save_customer(
            self.conn, {"name": "Nguyễn Văn A", "phone": "0901 234 567"}
        )

    def tearDown(self):
        self.conn.close()

    def make_rental(self, days=2, qty=1, item_id=None, start=None, **kwargs):
        start = start or self.today
        return services.create_rental(
            self.conn,
            customer_id=self.kh_id,
            start=start,
            due=start + timedelta(days=days),
            lines=[{"item_id": item_id or self.ao_id, "quantity": qty}],
            **kwargs,
        )


class TestUtils(unittest.TestCase):
    def test_fmt_money(self):
        self.assertEqual(fmt_money(1_250_000), "1.250.000đ")
        self.assertEqual(fmt_money(0), "0đ")
        self.assertEqual(fmt_money(-50_000), "-50.000đ")
        self.assertEqual(fmt_money(None), "0đ")

    def test_billed_days_toi_thieu_mot_ngay(self):
        self.assertEqual(billed_days("2026-09-19", "2026-09-19"), 1)
        self.assertEqual(billed_days("2026-09-19", "2026-09-22"), 3)

    def test_slugify_bo_dau_tieng_viet(self):
        self.assertEqual(slugify("Áo dài đỏ"), "AO-DAI-DO")
        self.assertEqual(slugify("Váy cưới #2"), "VAY-CUOI-2")

    def test_next_code_tang_dan(self):
        d = date(2026, 9, 19)
        self.assertEqual(next_code("DT", None, d), "DT260919-0001")
        self.assertEqual(next_code("DT", "DT260919-0007", d), "DT260919-0008")
        # Mã của ngày hôm trước thì đánh số lại từ đầu.
        self.assertEqual(next_code("DT", "DT260918-0009", d), "DT260919-0001")

    def test_normalize_phone(self):
        self.assertEqual(normalize_phone("0901 234 567"), "0901234567")
        self.assertEqual(normalize_phone("+84-90-123-4567"), "+84901234567")


class TestKhoVaKhachHang(BaseCase):
    def test_sku_trung_bi_chan(self):
        with self.assertRaises(ValueError):
            repo.save_item(self.conn, {"sku": "AO-DAI-DO", "name": "Áo khác", "quantity": 1})

    def test_so_dien_thoai_trung_bi_chan(self):
        with self.assertRaises(ValueError):
            repo.save_customer(self.conn, {"name": "Người khác", "phone": "0901234567"})

    def test_suggest_sku_khong_trung(self):
        self.assertEqual(repo.suggest_sku(self.conn, "Áo dài đỏ"), "AO-DAI-DO-2")

    def test_xoa_do_da_cho_thue_thi_chi_ngung_kinh_doanh(self):
        self.make_rental()
        repo.delete_item(self.conn, self.ao_id)
        item = repo.get_item(self.conn, self.ao_id)
        self.assertIsNotNone(item)
        self.assertEqual(item["active"], 0)

    def test_khong_xoa_khach_da_co_don(self):
        self.make_rental()
        self.assertFalse(repo.delete_customer(self.conn, self.kh_id))


class TestTonKho(BaseCase):
    def test_tru_ton_kho_theo_khoang_ngay(self):
        self.make_rental(days=2, qty=2)
        self.assertEqual(services.available_quantity(self.conn, self.ao_id, self.today,
                                                     self.today + timedelta(days=2)), 1)
        # Ngoài khoảng thuê thì hàng vẫn còn trống đủ.
        sau = self.today + timedelta(days=10)
        self.assertEqual(services.available_quantity(self.conn, self.ao_id, sau, sau), 3)

    def test_khong_cho_thue_qua_so_luong(self):
        self.make_rental(days=1, qty=3)
        with self.assertRaises(ValueError) as ctx:
            self.make_rental(days=1, qty=1)
        self.assertIn("chỉ còn 0", str(ctx.exception))

    def test_don_huy_tra_lai_ton_kho(self):
        rid = self.make_rental(days=1, qty=3)
        services.cancel_rental(self.conn, rid, "Khách đổi ý")
        self.assertEqual(
            services.available_quantity(self.conn, self.ao_id, self.today,
                                        self.today + timedelta(days=1)), 3
        )

    def test_gop_dong_trung_mon_khi_kiem_ton(self):
        with self.assertRaises(ValueError):
            services.create_rental(
                self.conn, self.kh_id, self.today, self.today + timedelta(days=1),
                lines=[{"item_id": self.giay_id, "quantity": 1},
                       {"item_id": self.giay_id, "quantity": 1}],
            )

    def test_ngay_tra_truoc_ngay_thue_bi_chan(self):
        with self.assertRaises(ValueError):
            services.create_rental(
                self.conn, self.kh_id, self.today, self.today - timedelta(days=1),
                lines=[{"item_id": self.ao_id, "quantity": 1}],
            )

    def test_don_khong_co_mon_nao_bi_chan(self):
        with self.assertRaises(ValueError):
            services.create_rental(self.conn, self.kh_id, self.today, self.today, lines=[])


class TestTinhTien(BaseCase):
    def test_tien_thue_va_coc(self):
        rid = self.make_rental(days=3, qty=2)
        s = services.rental_summary(self.conn, repo.get_rental(self.conn, rid), today=self.today)
        self.assertEqual(s["days"], 3)
        self.assertEqual(s["per_day"], 400_000)
        self.assertEqual(s["rent_total"], 1_200_000)
        self.assertEqual(s["deposit_total"], 1_000_000)
        self.assertEqual(s["total"], 1_200_000)

    def test_thue_trong_ngay_tinh_mot_ngay(self):
        rid = self.make_rental(days=0, qty=1)
        s = services.rental_summary(self.conn, repo.get_rental(self.conn, rid), today=self.today)
        self.assertEqual(s["days"], 1)
        self.assertEqual(s["total"], 200_000)

    def test_phi_tre_han_uoc_tinh_theo_hom_nay(self):
        rid = self.make_rental(days=1, qty=1)
        tre = self.today + timedelta(days=3)  # trễ 2 ngày so với hạn
        s = services.rental_summary(self.conn, repo.get_rental(self.conn, rid), today=tre)
        self.assertEqual(s["late_days"], 2)
        self.assertEqual(s["late_fee"], 600_000)  # 200k * 2 ngày * hệ số 1.5
        self.assertEqual(s["total"], 200_000 + 600_000)

    def test_giam_gia_khong_lam_tong_tien_am(self):
        rid = self.make_rental(days=1, qty=1, discount=999_999_999)
        s = services.rental_summary(self.conn, repo.get_rental(self.conn, rid), today=self.today)
        self.assertEqual(s["total"], 0)

    def test_theo_doi_thanh_toan_va_coc(self):
        rid = self.make_rental(days=1, qty=1, deposit_paid=500_000, prepaid=100_000)
        s = services.rental_summary(self.conn, repo.get_rental(self.conn, rid), today=self.today)
        self.assertEqual(s["deposit_held"], 500_000)
        self.assertEqual(s["paid"], 100_000)
        self.assertEqual(s["balance"], 200_000 - 100_000)


class TestTraDoVaGiaHan(BaseCase):
    def test_tra_dung_han_hoan_coc_va_mo_ton_kho(self):
        rid = self.make_rental(days=1, qty=3, deposit_paid=1_500_000)
        s = services.return_rental(self.conn, rid, return_date=self.today + timedelta(days=1),
                                   settle_amount=600_000)
        self.assertEqual(s["late_fee"], 0)
        self.assertEqual(s["deposit_held"], 0)      # đã hoàn cọc
        self.assertEqual(s["balance"], 0)           # thu đủ tiền thuê
        self.assertEqual(repo.get_rental(self.conn, rid)["status"], "returned")
        self.assertEqual(
            services.available_quantity(self.conn, self.ao_id, self.today,
                                        self.today + timedelta(days=1)), 3
        )

    def test_tra_tre_chot_phi_tre(self):
        rid = self.make_rental(days=1, qty=1)
        s = services.return_rental(self.conn, rid, return_date=self.today + timedelta(days=4))
        self.assertEqual(s["late_days"], 3)
        self.assertEqual(s["late_fee"], 900_000)
        # Phí trễ đã chốt nên không tăng thêm dù tính lại sau này.
        lai = services.rental_summary(self.conn, repo.get_rental(self.conn, rid),
                                      today=self.today + timedelta(days=30))
        self.assertEqual(lai["late_fee"], 900_000)

    def test_ghi_nhan_hu_hong_va_phi_phat_sinh(self):
        rid = self.make_rental(days=1, qty=2)
        line_id = repo.get_rental(self.conn, rid)["lines"][0]["id"]
        s = services.return_rental(self.conn, rid, return_date=self.today + timedelta(days=1),
                                   damaged={line_id: 1}, extra_fee=300_000)
        self.assertEqual(s["extra_fee"], 300_000)
        self.assertEqual(repo.get_rental(self.conn, rid)["lines"][0]["damaged_qty"], 1)

    def test_khong_tra_don_hai_lan(self):
        rid = self.make_rental(days=1)
        services.return_rental(self.conn, rid, return_date=self.today)
        with self.assertRaises(ValueError):
            services.return_rental(self.conn, rid, return_date=self.today)

    def test_gia_han_thanh_cong(self):
        rid = self.make_rental(days=1, qty=1, item_id=self.giay_id)
        moi = self.today + timedelta(days=5)
        services.extend_rental(self.conn, rid, moi)
        self.assertEqual(repo.get_rental(self.conn, rid)["due_date"], moi.isoformat())

    def test_gia_han_bi_chan_khi_dung_don_khac(self):
        rid = self.make_rental(days=1, qty=1, item_id=self.giay_id)
        # Đơn khác đã giữ đôi giày duy nhất ở tuần sau.
        services.create_rental(
            self.conn, self.kh_id, self.today + timedelta(days=5), self.today + timedelta(days=6),
            lines=[{"item_id": self.giay_id, "quantity": 1}],
        )
        with self.assertRaises(ValueError):
            services.extend_rental(self.conn, rid, self.today + timedelta(days=7))


class TestBaoCao(BaseCase):
    def test_don_qua_han_va_sap_den_han(self):
        self.make_rental(days=1, qty=1, start=self.today - timedelta(days=5))  # quá hạn
        self.make_rental(days=2, qty=1, item_id=self.giay_id)                  # sắp đến hạn
        self.assertEqual(len(services.rentals_overdue(self.conn, today=self.today)), 1)
        self.assertEqual(len(services.rentals_due_soon(self.conn, 3, today=self.today)), 1)

    def test_thong_ke_tong_quan(self):
        rid = self.make_rental(days=1, qty=2)
        services.return_rental(self.conn, rid, return_date=self.today + timedelta(days=1),
                               settle_amount=400_000)
        self.make_rental(days=2, qty=1, item_id=self.giay_id)
        st = services.dashboard_stats(self.conn, today=self.today + timedelta(days=1))
        self.assertEqual(st["active_count"], 1)
        self.assertEqual(st["items_out"], 1)
        self.assertEqual(st["revenue_month"], 400_000)

    def test_top_do_thue_nhieu(self):
        self.make_rental(days=1, qty=2)
        self.make_rental(days=1, qty=1, item_id=self.giay_id)
        top = services.top_items(self.conn)
        self.assertEqual(top[0]["name"], "Áo dài đỏ")
        self.assertEqual(top[0]["total_qty"], 2)

    def test_doanh_thu_theo_ngay(self):
        rid = self.make_rental(days=1, qty=1)
        ngay_tra = self.today + timedelta(days=1)
        services.return_rental(self.conn, rid, return_date=ngay_tra)
        rows = services.revenue_by_day(self.conn, self.today, ngay_tra)
        self.assertEqual(rows, [{"date": ngay_tra, "revenue": 200_000}])


if __name__ == "__main__":
    unittest.main(verbosity=2)
