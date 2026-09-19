# KATO APP

Kho mã chứa hai ứng dụng Streamlit độc lập:

| Ứng dụng | Tệp khởi chạy | Mô tả |
|---|---|---|
| **Quản lý thuê đồ** | `app_thue_do.py` | Quản lý kho đồ cho thuê, khách hàng, đơn thuê, thu chi và báo cáo |
| KATO AI Vision Prompt Generator | `app.py` | Sinh prompt ảnh kiến trúc/nội thất từ ảnh phác thảo bằng Gemini |

---

## 👗 Ứng dụng quản lý thuê đồ

Dành cho cửa hàng cho thuê áo dài, váy cưới, vest, phụ kiện, thiết bị chụp ảnh…
Giao diện tiếng Việt, tối ưu cho cả điện thoại lẫn máy tính, dữ liệu lưu trong một
tệp SQLite duy nhất nên không cần cài đặt máy chủ cơ sở dữ liệu.

### Cách chạy nhanh nhất trên Windows

Tải tệp `KHOI_DONG.bat` về thư mục bạn muốn cài rồi **bấm đúp chuột**. Tệp này tự
kiểm tra Python, tự tải mã nguồn, tự cài thư viện và tự mở ứng dụng — không cần gõ
lệnh nào. Những lần sau cũng bấm đúp tệp đó để mở ứng dụng.

Nếu máy chưa có Python hoặc Git, tệp sẽ dừng lại và chỉ rõ cần tải ở đâu.

### Cài đặt thủ công (Windows / macOS / Linux)

```bash
pip install -r requirements.txt
streamlit run app_thue_do.py
```

Mở trình duyệt tại địa chỉ hiện ra (mặc định http://localhost:8501).

Lần đầu chạy, vào **⚙️ Cài đặt → 🌱 Nạp dữ liệu mẫu** để xem thử với dữ liệu giả lập.

### Nơi lưu dữ liệu

Mặc định là tệp `thuedo.db` nằm cạnh mã nguồn. Đổi chỗ lưu bằng biến môi trường:

```bash
# Windows PowerShell
$env:KATO_THUEDO_DB="D:\du-lieu\thuedo.db"; streamlit run app_thue_do.py

# macOS / Linux
KATO_THUEDO_DB=~/du-lieu/thuedo.db streamlit run app_thue_do.py
```

> Nhớ sao lưu tệp `.db` định kỳ — đó là toàn bộ dữ liệu kinh doanh của bạn.
> Tệp này đã được `.gitignore` bỏ qua nên sẽ không bị đẩy lên GitHub.

### Tính năng

**🏠 Tổng quan** — số đơn đang mở, đơn quá hạn, đồ đang ở ngoài, doanh thu tháng,
công nợ phải thu; kèm danh sách đơn quá hạn và sắp đến hạn.

**🧾 Đơn thuê**
- Lập đơn theo kiểu giỏ hàng, tự kiểm tra tồn kho theo đúng khoảng ngày thuê
- Chốt giá và tiền cọc ngay tại thời điểm lập đơn (đổi bảng giá sau không ảnh hưởng đơn cũ)
- Trả đồ: tự tính phí trễ hạn, ghi nhận số cái hư hỏng, thu nốt tiền và hoàn cọc
- Gia hạn có kiểm tra xem món đồ đã bị đơn khác đặt trước hay chưa
- Huỷ đơn và trả số lượng về kho
- Sổ thanh toán riêng cho từng đơn: nhận cọc, hoàn cọc, thu tiền, hoàn tiền

**📦 Kho đồ** — thêm/sửa món đồ (SKU, danh mục, size, màu, số lượng, giá thuê ngày,
tiền cọc); xem **số còn trống theo khoảng ngày bất kỳ**. Món đã từng cho thuê sẽ được
chuyển sang trạng thái *Ngưng kinh doanh* thay vì xoá, để giữ nguyên lịch sử.

**👥 Khách hàng** — danh bạ kèm CCCD, địa chỉ, đánh dấu khách cần lưu ý, lịch sử thuê
và tổng chi tiêu của từng người.

**📊 Báo cáo** — doanh thu theo ngày (ghi nhận theo ngày trả đồ), đồ được thuê nhiều
nhất, khách chi tiêu nhiều nhất, tình trạng kho và lịch trả đồ 7 ngày tới.

**⚙️ Cài đặt** — thông tin cửa hàng, hệ số phí trễ hạn, quản lý danh mục,
xuất CSV (mở được bằng Excel, đúng font tiếng Việt) và nạp dữ liệu mẫu.

### Cách tính tiền

| Khoản | Công thức |
|---|---|
| Số ngày thuê | `hạn trả − ngày bắt đầu`, tối thiểu 1 ngày |
| Tiền thuê | `tổng (số lượng × giá thuê/ngày) × số ngày` |
| Phí trễ hạn | `tiền thuê một ngày × số ngày trễ × hệ số` (mặc định 1.5, đổi trong Cài đặt) |
| Tổng tiền | `tiền thuê + phí trễ + phí phát sinh − giảm giá` (không âm) |
| Còn phải thu | `tổng tiền − đã thanh toán` |

Tiền cọc được theo dõi tách riêng khỏi tiền thuê và hoàn lại khi khách trả đồ.

### Cấu trúc mã nguồn

```
app_thue_do.py        điểm khởi chạy và thanh điều hướng
thuedo/
  db.py               kết nối SQLite, lược đồ bảng, cấu hình mặc định
  repo.py             CRUD: danh mục, đồ, khách hàng, đơn, thanh toán
  services.py         nghiệp vụ: tồn kho, tính tiền, lập đơn, trả đồ, báo cáo
  utils.py            định dạng tiền/ngày, sinh mã đơn, bỏ dấu tiếng Việt
  seed.py             dữ liệu mẫu
  ui/                 các màn hình Streamlit
tests/                kiểm thử (38 bài)
```

Toàn bộ nghiệp vụ nằm trong `thuedo/` và không phụ thuộc Streamlit, nên có thể tái
sử dụng cho giao diện khác (web, API, ứng dụng di động) về sau.

### Chạy kiểm thử

```bash
python -m unittest discover -s tests -v
```

---

## 🎨 KATO AI Vision Prompt Generator

```bash
streamlit run app.py
```

Cần Gemini API key, nhập trực tiếp trong phần *Cấu hình hệ thống* của ứng dụng.
