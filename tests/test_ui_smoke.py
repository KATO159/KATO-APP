"""Kiểm thử khói giao diện: mở từng trang bằng AppTest của Streamlit, đảm bảo không vỡ."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app_thue_do.py")


class TestGiaoDien(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from streamlit.testing.v1 import AppTest  # noqa: F401

        cls.tmpdir = tempfile.TemporaryDirectory()
        os.environ["KATO_THUEDO_DB"] = os.path.join(cls.tmpdir.name, "test.db")

        # Nạp dữ liệu mẫu để các trang có nội dung thật để dựng.
        from thuedo import seed
        from thuedo.db import get_db

        conn = get_db(os.environ["KATO_THUEDO_DB"])
        seed.seed_demo(conn)
        conn.close()

    @classmethod
    def tearDownClass(cls):
        cls.tmpdir.cleanup()

    def _run(self, trang: str = None):
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(APP, default_timeout=60)
        at.run()
        self.assertFalse(at.exception, f"Lỗi khi mở ứng dụng: {at.exception}")
        if trang:
            at.pills[0].set_value(trang).run()
            self.assertFalse(at.exception, f"Lỗi ở trang {trang}: {at.exception}")
        return at

    def test_mo_ung_dung(self):
        at = self._run()
        self.assertTrue(at.pills, "Không tìm thấy thanh điều hướng.")

    def test_trang_tong_quan(self):
        at = self._run("🏠 Tổng quan")
        nhan = [m.label for m in at.metric]
        self.assertIn("Đơn đang mở", nhan)
        self.assertIn("Đơn quá hạn", nhan)

    def test_trang_don_thue(self):
        self._run("🧾 Đơn thuê")

    def test_trang_kho_do(self):
        self._run("📦 Kho đồ")

    def test_trang_khach_hang(self):
        self._run("👥 Khách hàng")

    def test_trang_bao_cao(self):
        at = self._run("📊 Báo cáo")
        self.assertIn("Doanh thu", [m.label for m in at.metric])

    def test_trang_cai_dat(self):
        self._run("⚙️ Cài đặt")


if __name__ == "__main__":
    unittest.main(verbosity=2)
