import base64
import html
import io
import os
import re
from PIL import Image
import google.generativeai as genai
import streamlit as st
import streamlit.components.v1 as components

# Cấu hình trang Streamlit
st.set_page_config(page_title="KATO AI - Vision Prompt Generator", layout="wide")

# Khởi tạo session_state cho cả Ngoại thất và Nội thất
for key in ["p1_res_ext", "p2_res_ext", "p1_res_int", "p2_res_int"]:
  if key not in st.session_state:
    st.session_state[key] = None

if "uploader_key_ext" not in st.session_state:
  st.session_state.uploader_key_ext = 0
if "uploader_key_int" not in st.session_state:
  st.session_state.uploader_key_int = 0
if "show_dog_modal" not in st.session_state:
  st.session_state.show_dog_modal = False


# Hàm làm sạch văn bản
def clean_prompt_text(text: str) -> str:
  if not text:
    return ""
  lines = [line.rstrip() for line in text.splitlines()]
  return "\n".join(lines).strip()


# CACHE HÀM CHUYỂN ĐỔI ẢNH SANG BASE64
@st.cache_data(show_spinner=False)
def file_bytes_to_b64(file_bytes: bytes) -> str:
  img = Image.open(io.BytesIO(file_bytes))
  buffered = io.BytesIO()
  if img.mode in ("RGBA", "P"):
    img_conv = img.convert("RGBA")
    img_conv.save(buffered, format="PNG")
  else:
    img_conv = img.convert("RGB")
    img_conv.save(buffered, format="JPEG", quality=85)
  return base64.b64encode(buffered.getvalue()).decode()


# CACHE HÀM TẠO ẢNH CHÚ CHÓ
@st.cache_data(show_spinner=False)
def get_transparent_dog_b64():
  target_file = None
  explicit_files = [
      "image_45819f.png",
      "image_45819f.jpg",
      "image_45819f.jpeg",
      "dog.png",
      "dog.jpg",
      "dog.jpeg",
      "chihuahua.png",
      "chihuahua.jpg",
  ]
  for f in explicit_files:
    if os.path.exists(f):
      target_file = f
      break

  if not target_file:
    for f in os.listdir("."):
      if f.lower().endswith((".png", ".jpg", ".jpeg")):
        if (
            "458" in f.lower()
            or "dog" in f.lower()
            or "chihuahua" in f.lower()
            or f.startswith("image_")
        ):
          target_file = f
          break

  if not target_file:
    return None

  try:
    img = Image.open(target_file).convert("RGBA")
    datas = img.getdata()
    new_data = []
    for item in datas:
      r, g, b, a = item
      if g > 100 and g > r * 1.1 and g > b * 1.1:
        new_data.append((0, 0, 0, 0))
      elif g > 140 and g > r and g > b:
        new_data.append((0, 0, 0, 0))
      else:
        new_data.append(item)
    img.putdata(new_data)
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()
  except Exception:
    return None


# Hiển thị khung Prompt chuẩn 50-50 khóa bằng đúng đáy Panel trái
def render_prompt_card(title: str, text: str, box_id: str):
  escaped_text = html.escape(text) if text else ""
  html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            * {{ box-sizing: border-box; }}
            body {{ margin: 0; padding: 0; background-color: transparent; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; color: #e0e0e0; overflow: hidden; }}
            .header-row {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }}
            .title-text {{ font-weight: 600; color: #ffffff; font-size: 0.88rem; }}
            .copy-btn {{ background-color: #363945; color: #e0e0e0; border: 1px solid #484c5a; padding: 2px 8px; border-radius: 6px; cursor: pointer; font-size: 0.78rem; font-weight: 600; transition: all 0.2s ease; outline: none; }}
            .copy-btn:hover {{ background-color: #484c5a; color: #ffffff; }}
            .prompt-box {{ background-color: #1e1e24; border: 1px solid #363945; border-radius: 8px; padding: 0.65rem 0.75rem; height: 270px; min-height: 270px; max-height: 270px; overflow-y: auto; font-family: monospace, Consolas, "Courier New"; font-size: 0.85rem; line-height: 1.45; color: #e0e0e0; white-space: pre-wrap; word-wrap: break-word; word-break: break-word; }}
            .prompt-box::-webkit-scrollbar {{ width: 5px; }}
            .prompt-box::-webkit-scrollbar-track {{ background: #1e1e24; }}
            .prompt-box::-webkit-scrollbar-thumb {{ background: #363945; border-radius: 3px; }}
        </style>
    </head>
    <body>
        <div class="header-row">
            <span class="title-text">{title}</span>
            <button id="btn_{box_id}" class="copy-btn" onclick="copyText()">📋 Copy Prompt</button>
        </div>
        <div id="text_{box_id}" class="prompt-box">{escaped_text}</div>
        <script>
        function copyText() {{
            var el = document.getElementById("text_{box_id}");
            if (!el) return;
            var text = el.innerText || el.textContent;
            var btn = document.getElementById("btn_{box_id}");
            function onSuccess() {{
                btn.innerHTML = "✅ Đã chép!"; btn.style.backgroundColor = "#28a745"; btn.style.borderColor = "#28a745"; btn.style.color = "#ffffff";
                setTimeout(function() {{ btn.innerHTML = "📋 Copy Prompt"; btn.style.backgroundColor = "#363945"; btn.style.borderColor = "#484c5a"; btn.style.color = "#e0e0e0"; }}, 2000);
            }}
            if (navigator.clipboard && window.isSecureContext) {{ navigator.clipboard.writeText(text).then(onSuccess).catch(function() {{ fallbackCopy(text, onSuccess); }}); }}
            else {{ fallbackCopy(text, onSuccess); }}
        }}
        function fallbackCopy(text, callback) {{
            var ta = document.createElement("textarea"); ta.value = text; ta.style.position = "fixed"; ta.style.left = "-9999px"; ta.style.top = "-9999px"; document.body.appendChild(ta); ta.focus(); ta.select();
            try {{ document.execCommand('copy'); callback(); }} catch (e) {{ alert('Vui lòng bôi đen thủ công để chép!'); }}
            document.body.removeChild(ta);
        }}
        </script>
    </body>
    </html>
    """
  components.html(html_code, height=310)


# Hiển thị ảnh xem trước
def render_clickable_image(img_b64, caption, uploader_index):
  html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            * {{ box-sizing: border-box; }}
            body {{ margin: 0; padding: 0; background-color: transparent; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
            .img-container {{ position: relative; width: 100%; height: 135px; cursor: pointer; border-radius: 8px; overflow: hidden; border: 1.5px dashed #484c5a; transition: all 0.25s ease; background-color: #1e1e24; display: flex; justify-content: center; align-items: center; }}
            .img-container:hover {{ border-color: #28a745; box-shadow: 0 0 12px rgba(40, 167, 69, 0.35); }}
            .img-container img {{ max-height: 125px; width: 100%; object-fit: contain; display: block; transition: filter 0.25s ease, transform 0.25s ease; }}
            .img-container:hover img {{ filter: brightness(0.45); transform: scale(1.01); }}
            .overlay-text {{ position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); color: #ffffff; font-weight: 700; font-size: 0.82rem; background: rgba(38, 39, 48, 0.92); padding: 6px 12px; border-radius: 16px; opacity: 0; transition: opacity 0.25s ease; pointer-events: none; white-space: nowrap; border: 1px solid #28a745; box-shadow: 0 4px 12px rgba(0,0,0,0.5); }}
            .img-container:hover .overlay-text {{ opacity: 1; }}
            .delete-x-btn {{ position: absolute; top: 6px; right: 6px; width: 24px; height: 24px; background-color: #dc3545; color: #ffffff; border: 1px solid #ff6b6b; border-radius: 50%; font-size: 12px; font-weight: bold; display: flex; align-items: center; justify-content: center; cursor: pointer; z-index: 99; box-shadow: 0 2px 8px rgba(0,0,0,0.6); transition: all 0.2s ease; outline: none; }}
            .delete-x-btn:hover {{ background-color: #bd2130; transform: scale(1.15); }}
            .caption-text {{ text-align: center; color: #a0a0a0; font-size: 0.75rem; margin-top: 3px; font-weight: 500; }}
        </style>
    </head>
    <body>
        <div class="img-container" title="Nhấp vào ảnh để chọn ảnh khác" onclick="changeImage()">
            <button class="delete-x-btn" title="Xóa ảnh này" onclick="deleteImage(event)">✖</button>
            <img src="data:image/png;base64,{img_b64}" />
            <div class="overlay-text">📷 Nhấp để thay đổi</div>
        </div>
        <div class="caption-text">{caption}</div>
        <script>
        function changeImage() {{
            try {{
                var inputs = window.parent.document.querySelectorAll('input[type=file]');
                if (inputs && inputs[{uploader_index}]) {{ inputs[{uploader_index}].click(); }}
            }} catch(e) {{ console.error(e); }}
        }}
        function deleteImage(e) {{
            if (e) e.stopPropagation();
            try {{
                var uploaders = window.parent.document.querySelectorAll('div[data-testid="stFileUploader"]');
                if (uploaders && uploaders[{uploader_index}]) {{
                    var btn = uploaders[{uploader_index}].querySelector('button[title*="Remove"], button[aria-label*="Remove"], button[aria-label*="Delete"], button[data-testid*="clear"]');
                    if (!btn) {{ btn = uploaders[{uploader_index}].querySelector('button'); }}
                    if (btn) {{ btn.click(); }}
                }}
            }} catch(err) {{ console.error(err); }}
        }}
        </script>
    </body>
    </html>
    """
  components.html(html_code, height=160)


# CSS GIAO DIỆN HỆ THỐNG
st.markdown(
    """
<style>
/* Cho phép cuộn mượt mà toàn trang khi màn hình nhỏ */
html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
    overflow-x: hidden !important;
    overflow-y: auto !important;
}

div[data-testid="stHeader"], header[data-testid="stHeader"] {
    display: flex !important;
    background: transparent !important;
    z-index: 1000 !important;
    pointer-events: none !important;
    height: 2.8rem !important;
}
div[data-testid="stHeader"] *, header[data-testid="stHeader"] * {
    pointer-events: auto !important;
}

section[data-testid="stSidebar"] { display: none !important; }

/* Căn chỉnh block container gọn gàng */
.block-container {
    padding-top: 2.8rem !important;
    padding-bottom: 1.0rem !important;
    padding-left: 0.8rem !important;
    padding-right: 0.8rem !important;
    max-width: 100% !important;
}

div[data-baseweb="tab-list"] {
    z-index: 999999 !important;
    position: relative !important;
    pointer-events: auto !important;
}
button[data-baseweb="tab"] {
    font-size: 1.0rem !important;
    font-weight: 700 !important;
    padding: 0.4rem 1.5rem !important;
    border-radius: 8px 8px 0 0 !important;
    cursor: pointer !important;
    pointer-events: auto !important;
    z-index: 999999 !important;
    position: relative !important;
}
button[aria-selected="true"] {
    background-color: #262730 !important;
    color: #28a745 !important;
    border-bottom: 3px solid #28a745 !important;
}

/* Đảm bảo iframe Prompt luôn đầy đủ chiều cao 310px */
iframe[data-testid="stCustomComponentV1"], iframe {
    width: 100% !important;
    min-height: 310px !important;
    display: block !important;
}

/* BẮT BUỘC TẤT CẢ 3 CỘT CÙNG CHIỀU CAO VÀ CÙNG ĐƯỜNG ĐÁY */
div[data-testid="stHorizontalBlock"] {
    display: flex !important;
    align-items: stretch !important;
}

div[data-testid="stColumn"] {
    display: flex !important;
    flex-direction: column !important;
    justify-content: space-between !important;
}

div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] {
    height: 100% !important;
    display: flex !important;
    flex-direction: column !important;
    justify-content: space-between !important;
}

/* Khung Expander Cột 1 và Cột 3 tự động giãn 100% chiều cao bằng đáy Cột 2 */
div[data-testid="stExpander"] {
    background-color: #1e1e24 !important;
    border: 1px solid #363945 !important;
    border-radius: 10px !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15) !important;
    height: 100% !important;
    display: flex !important;
    flex-direction: column !important;
}
div[data-testid="stExpander"] details {
    display: flex !important;
    flex-direction: column !important;
    height: 100% !important;
    flex: 1 !important;
}
div[data-testid="stExpander"] details summary {
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    color: #e0e0e0 !important;
    padding: 0.35rem 0.7rem !important;
}
div[data-testid="stExpander"] details > div[role="region"] {
    overflow-y: auto !important;
    flex: 1 !important;
    padding: 0.3rem 0.4rem !important;
}

/* Tối ưu khoảng cách các container bên trong expander */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 8px !important;
    background-color: #262730 !important;
    border: 1px solid #363945 !important;
    margin-bottom: 0.3rem !important;
    padding: 0.35rem 0.5rem !important;
}

div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stMarkdownContainer"] p {
    font-size: 0.85rem !important;
    margin-bottom: 0.1rem !important;
}
div[data-testid="stVerticalBlockBorderWrapper"] .stCaption p {
    font-size: 0.75rem !important;
    margin-top: -0.2rem !important;
    margin-bottom: 0.2rem !important;
}

.custom-header-title { white-space: nowrap !important; font-size: 1.2rem !important; font-weight: 700 !important; color: #ffffff !important; margin: 0 !important; line-height: 32px !important; }

div[data-testid="stFileUploader"]:has(div[data-testid="stFileUploaderFileData"]),
div[data-testid="stFileUploader"]:has(span[data-testid="stFileUploaderFileName"]),
div[data-testid="stFileUploader"]:has(button[title="Remove file"]),
div[data-testid="stFileUploader"]:has(button[aria-label*="Remove"]),
div[data-testid="stFileUploader"]:has(ul) { position: absolute !important; opacity: 0 !important; height: 0 !important; width: 0 !important; max-height: 0 !important; margin: 0 !important; padding: 0 !important; overflow: hidden !important; pointer-events: none !important; }

div[data-testid="stTextArea"] textarea { height: 75px !important; max-height: 75px !important; font-size: 0.82rem !important; }

button[kind="primary"] { background-color: #28a745 !important; color: #ffffff !important; border: none !important; height: 34px !important; border-radius: 6px !important; font-weight: 600 !important; font-size: 0.88rem !important; }
button[kind="primary"]:hover { background-color: #218838 !important; }
button[kind="secondary"] { background-color: #dc3545 !important; color: #ffffff !important; border: none !important; height: 34px !important; border-radius: 6px !important; font-weight: 600 !important; font-size: 0.88rem !important; }
button[kind="secondary"]:hover { background-color: #c82333 !important; }

div[data-testid="stColumn"] div[data-testid="stColumn"]:nth-child(4) button { background-color: #495057 !important; color: #ffffff !important; border: none !important; height: 36px !important; border-radius: 6px !important; font-weight: 600 !important; font-size: 0.88rem !important; }
div[data-testid="stColumn"] div[data-testid="stColumn"]:nth-child(4) button:hover { background-color: #343a40 !important; }
</style>
""",
    unsafe_allow_html=True,
)

# THÔNG BÁO CHÚ CHÓ
if st.session_state.get("show_dog_modal", False):
  st.session_state.show_dog_modal = False
  dog_b64 = get_transparent_dog_b64()
  img_src = f"data:image/png;base64,{dog_b64}" if dog_b64 else ""

  components.html(
      f"""
        <script>
        (function() {{
            var parentDoc = window.parent.document;
            var oldModal = parentDoc.getElementById('autoCloseDogModal');
            if (oldModal) oldModal.remove();

            var modal = parentDoc.createElement('div');
            modal.id = 'autoCloseDogModal';
            modal.style.position = 'fixed'; modal.style.top = '0'; modal.style.left = '0'; modal.style.width = '100vw'; modal.style.height = '100vh'; modal.style.backgroundColor = 'rgba(0, 0, 0, 0.78)'; modal.style.zIndex = '9999999'; modal.style.display = 'flex'; modal.style.justifyContent = 'center'; modal.style.alignItems = 'center'; modal.style.pointerEvents = 'none'; modal.style.transition = 'opacity 0.3s ease';

            var card = parentDoc.createElement('div');
            card.style.backgroundColor = '#262730'; card.style.border = '2px solid #28a745'; card.style.borderRadius = '16px'; card.style.padding = '25px 35px'; card.style.textAlign = 'center'; card.style.boxShadow = '0 16px 40px rgba(0,0,0,0.8)'; card.style.maxWidth = '380px'; card.style.width = '85%';

            var imgStr = '{img_src}';
            if (imgStr) {{
                var img = parentDoc.createElement('img'); img.src = imgStr; img.style.maxHeight = '220px'; img.style.objectFit = 'contain'; img.style.margin = '0 auto 12px auto'; img.style.display = 'block'; card.appendChild(img);
            }}

            var txt = parentDoc.createElement('div'); txt.style.fontSize = '1.3rem'; txt.style.fontWeight = '800'; txt.style.color = '#28a745'; txt.style.letterSpacing = '0.5px'; txt.style.textTransform = 'uppercase'; txt.innerText = 'XONG RỒI CON VỢ!!'; card.appendChild(txt);
            modal.appendChild(card); parentDoc.body.appendChild(modal);

            setTimeout(function() {{
                modal.style.opacity = '0';
                setTimeout(function() {{ if (modal && modal.parentNode) modal.parentNode.removeChild(modal); }}, 300);
            }}, 2000);
        }})();
        </script>
    """,
      height=0,
  )

# ==================== DANH SÁCH TÙY CHỌN ====================
# Kịch bản ánh sáng Ngoại thất (7 tùy chọn)
lighting_ext_options = [
    "A1 - Nắng sáng sớm trong trẻo (Bright Early Morning Sun)",
    (
        "A2 - Nắng trưa rực rỡ & Bóng đổ sắc nét (High Noon Direct Sun & Sharp"
        " Shadows)"
    ),
    (
        "A3 - Ngày mây / Ánh sáng tán xạ (Overcast Diffused Light - True"
        " Material Focus)"
    ),
    "A4 - Hoàng hôn rực rỡ / Giờ vàng (Golden Hour Warm Sunset)",
    "A5 - Chạng vạng lên đèn kiến trúc (Blue Hour & Facade Lighting)",
    (
        "A6 - Đêm huyền bí & Điểm nhấn cảnh quan (Moody Night & Landscape"
        " Spotlights)"
    ),
    "A7 - Sau mưa / Sân ướt phản chiếu (Post-Rain Wet Surface Reflections)",
]

# Bối cảnh Môi trường Ngoại thất (4 tùy chọn)
context_ext_options = [
    "C1 - Phố thị hiện đại (Urban Street & Paved Sidewalk - Natural Layout)",
    (
        "C2 - Biệt thự sân vườn nhiệt đới (Tropical Villa Garden & Pool - Gentle"
        " Greenery)"
    ),
    (
        "C3 - Ngoại ô / Khu nghỉ dưỡng (Suburban Resort & Nature Greenery -"
        " Balanced Surroundings)"
    ),
    (
        "C4 - Mặt đường sau mưa (Post-Rain Wet Asphalt Reflections - Realistic"
        " Night Reflections)"
    ),
]

# Hiệu ứng hình ảnh & Nhiếp ảnh Ngoại thất (6 tùy chọn)
film_ext_options = [
    "B0 - None (Màu nguyên bản công trình)",
    (
        "B1 - Tạp chí Kiến trúc Cao cấp (Architectural Digest - Clean & High"
        " Contrast)"
    ),
    (
        "B2 - Nhiếp ảnh Tạp chí Hiện đại (Fujifilm Classic Chrome - Architectural"
        " Tone)"
    ),
    "B3 - Tông Ấm Cổ điển (Kodak Portra 400 - Warm Vintage Vibe)",
    "B4 - Đêm Điện ảnh Đô thị (CineStill 800T - Night Halation & Glow)",
    (
        "B5 - Khóa Góc Đứng Chuyên dụng (Hasselblad Tilt-Shift - Zero"
        " Perspective Distortion)"
    ),
]

# Kịch bản ánh sáng Nội thất (10 tùy chọn)
lighting_int_options = [
    "I1 - Nắng sáng sớm qua rèm voan (Soft Morning Sun & Sheer Curtains)",
    "I2 - Nắng trưa tương phản cao (High Noon & Crisp Shadows)",
    "I3 - Luồng nắng xuyên khe (Volumetric God Rays)",
    (
        "I4 - Trời u uất / Ánh sáng tán xạ đều (Overcast Ambient Light -"
        " Material Focus)"
    ),
    "I5 - Đèn ấm thư giãn (Warm Cozy Mood 2700K - 3000K)",
    "I6 - Đèn trung tính hiện đại (Neutral Daylight 4000K - 4500K)",
    (
        "I7 - Đèn LED hắt khe & Ray âm trần (Modern Cove LED & Magnetic Track"
        " Lights)"
    ),
    (
        "I8 - Hỗn hợp Hoàng hôn & Đèn trong nhà (Golden Hour & Indoor Warm"
        " Lights)"
    ),
    "I9 - Tối nghệ thuật & Đèn rọi điểm nhấn (Moody Dark & Accent Spotlights)",
    "I10 - Đèn dải màu / Gaming / Bar (RGB Linear Strip & Modern Accent Light)",
]

# Bối cảnh Môi trường Nội thất (4 tùy chọn)
context_int_options = [
    (
        "C1 - View sân vườn nhiệt đới qua kính (Glass Wall to Tropical Garden"
        " View - Soft Ambient Green)"
    ),
    (
        "C2 - View thành phố trên cao (High-Rise City Skyline View - Natural"
        " High-Rise Light)"
    ),
    (
        "C3 - Vệt nắng & Hạt bụi vờn nhẹ (Volumetric Sunlight & Floating Dust"
        " Motes - Atmospheric Depth)"
    ),
    (
        "C4 - Dấu vết sinh hoạt tự nhiên (Lived-in Natural Details - Fresh Flora"
        " & Balanced Decor)"
    ),
]

# Hiệu ứng hình ảnh & Nhiếp ảnh Nội thất (8 tùy chọn)
film_int_options = [
    "F0 - None (Màu nguyên bản chất liệu)",
    (
        "F1 - Tạp chí Sáng trong (Architectural Digest - Clean & Bright"
        " Showcase)"
    ),
    (
        "F2 - Tông Gỗ & Đất Ấm áp (Kodak Portra 400 - Warm Wood & Earth Tones)"
    ),
    "F3 - Mộc mạc & Creamy (Fuji Pro 400H - Soft & Airy Pastel)",
    "F4 - Sang trọng Điện ảnh (Cinematic Moody - Deep Shadows & Contrast)",
    "F5 - Ấm áp Cổ điển (Kodak Gold 200 - Vintage Warm Gold Tone)",
    "F6 - Kính lọc Tán mờ Đèn (Black Pro-Mist 1/4 - Soft Glow Lights)",
    (
        "F7 - Chi tiết Siêu nét Medium Format (Hasselblad - Zero Distortion &"
        " High Texture)"
    ),
]


# HÀM XỬ LÝ GỌI API AI GEMINI
def process_gemini_analysis(
    api_key,
    selected_model,
    light_opt1,
    context_opt1,
    film_opt1,
    light_opt2,
    context_opt2,
    film_opt2,
    sketch_img,
    ref_img,
    extra_notes,
    only_light_mode,
    is_interior=False,
):
  genai.configure(api_key=api_key)
  model = genai.GenerativeModel(selected_model)

  ref_instruction = ""
  if ref_img:
    if only_light_mode:
      ref_instruction = (
          "LƯU Ý ĐẶC BIỆT CHO @ảnh tham chiếu: CHỈ TRÍCH XUẤT duy nhất kịch bản"
          " ánh sáng, góc nắng đổ bóng, nhiệt độ màu và không khí ánh sáng từ"
          " **@ảnh tham chiếu**. BẢO TỒN HOÀN TOÀN toàn bộ vật liệu, màu sắc bề"
          " mặt và bối cảnh từ **@ảnh phác thảo**."
      )
    else:
      ref_instruction = (
          "Đối với **@ảnh tham chiếu**, trích xuất toàn bộ bối cảnh môi trường"
          " xung quanh, kịch bản ánh sáng và các bề mặt vật liệu/bảng màu chính"
          " để áp lên khung nét của **@ảnh phác thảo**."
      )

  clean_light2 = (
      light_opt2.split(" - ")[1] if " - " in light_opt2 else light_opt2
  )
  clean_context2 = (
      context_opt2.split(" - ")[1] if " - " in context_opt2 else context_opt2
  )
  clean_film2 = film_opt2.split(" - ")[1] if " - " in film_opt2 else film_opt2
  film_text2 = (
      f"kết hợp hiệu ứng {clean_film2}"
      if ("B0 - None" not in film_opt2 and "F0 - None" not in film_opt2)
      else "giữ màu sắc tự nhiên chân thực, không áp hiệu ứng màu phim"
  )

  domain_str = "NỘI THẤT" if is_interior else "KIẾN TRÚC NGOẠI THẤT"
  detail_str = (
      "bố cục không gian nội thất, góc chụp (toàn cảnh/góc trung), đồ nội thất"
      " (bàn, ghế, sofa, tủ, đèn trang trí), từng chất liệu bề mặt (gỗ, đá, vải,"
      " kim loại, kính, rèm...) và ánh sáng môi trường trong phòng"
      if is_interior
      else (
          "hình khối kiến trúc, số tầng, góc quay (mặt tiền, góc chéo 3/4...),"
          " từng chất liệu bề mặt các tầng và bối cảnh cây xanh đô thị"
      )
  )

  system_instruction = f"""
    Bạn là một chuyên gia phân tích {domain_str} và nhiếp ảnh kiến trúc thương mại cao cấp. 
    Hãy nhìn vào hình ảnh phác thảo được cung cấp và tạo ra CÁC CÂU LỆNH (prompt) mô tả chi tiết bằng TIẾNG VIỆT để đưa vào phần mềm sinh ảnh Flow.

    Nhiệm vụ của bạn là tạo ra 2 PHƯƠNG ÁN PROMPT (Phương án 1 và Phương án 2) để so sánh kịch bản ánh sáng, bối cảnh môi trường và hiệu ứng màu sắc:

    QUY TẮC TỐI CAO VỀ TỰ ĐỘNG NHẬN DIỆN VÀ KHÓA GÓC CAMERA (Áp dụng cho CẢ 2 PHƯƠNG ÁN):
    - TỰ ĐỘNG PHÂN TÍCH GÓC CAMERA: Hãy TỰ ĐỘNG soi kỹ **@ảnh phác thảo** để nhận diện chính xác góc chụp camera vật lý (ví dụ: Chụp chính diện toàn cảnh mặt tiền, Góc nhìn tầm mắt bên trong khuôn viên sân vườn/hiên, Góc chéo 3/4, Góc rộng không gian, Góc cận cảnh tả thực vật liệu...).
    - KHÓA 100% BỐ CỤC KHUNG HÌNH: Bạn BẮT BUỘC miêu tả đúng góc máy, khoảng cách tiêu cự và tỉ lệ khung hình hệt như trong **@ảnh phác thảo**. Tuyệt đối KHÔNG tự ý phóng to (zoom in), thu nhỏ (zoom out), hay đẩy lùi vị trí camera làm mất đi ý đồ thiết kế ban đầu.
    - CẢNH QUAN NỀN TỰ NHIÊN & NHÃ NHẶN: Bối cảnh xung quanh chỉ xuất hiện nhã nhặn ở vị trí dư thừa tự nhiên của khung hình phác thảo, bố cục thoáng đãng, hài hòa để TÔN CÔNG TRÌNH CHÍNH LÊN LÀM TÂM ĐIỂM, tránh các vật thể rác làm xao nhãng thị giác. BẮT BUỘC KHÔNG DÙNG các từ ngữ tiệt trùng 3D như "sạch sẽ", "hoàn hảo", "không chi tiết thừa".

    - PHƯƠNG ÁN 1 (AI ĐỀ XUẤT TỰ ĐỘNG THEO STYLE):
      + Bạn hãy TỰ ĐỘNG phân tích và nhận diện chính xác phong cách thiết kế của **@ảnh phác thảo** (ví dụ: Modern Luxury, Japandi, Indochine, Scandinavian, Minimalist, Industrial, Classic...).
      + Dựa trên phong cách thiết kế và góc camera gốc từ **@ảnh phác thảo**, hãy TỰ ĐỘNG ĐỀ XUẤT kịch bản ánh sáng, bối cảnh môi trường nhã nhặn tự nhiên và hiệu ứng nhiếp ảnh/màu sắc hoàn hảo nhất.

    - PHƯƠNG ÁN 2 (THỬ NGHIỆM THEO TÙY CHỌN NGƯỜI DÙNG):
      + Bắt buộc áp dụng kịch bản ánh sáng {clean_light2}.
      + Bắt buộc đặt trong bối cảnh môi trường {clean_context2} (thoáng đãng, nhã nhặn, tôn công trình chính).
      + Bắt buộc tích hợp thông số máy ảnh '16mm wide-angle lens, f/8 aperture, shot on Sony Alpha A7R V' {film_text2}.

    BẮT BUỘC ĐỒNG BỘ VẬT LIỆU & HÌNH KHỐI (100% GIỐNG NHAU):
    - Toàn bộ nội dung mô tả {detail_str} của Phương án 1 và Phương án 2 BẮT BUỘC PHẢI GIỐNG NHAU 100% (dùng chung một mô tả trích xuất từ **@ảnh phác thảo**).
    
    Quy tắc trình bày & cấu trúc Prompt:
    1. Cả 2 câu lệnh BẮT BUỘC bắt đầu bằng cụm từ chính xác: 'Ảnh chụp thực tế'.
    2. CẤU TRÚC PHÂN THÀNH CÁC PHẦN RÕ RÀNG: Hãy chia nhỏ cấu trúc Prompt thành các thành phần chi tiết (ví dụ: Chủ thể & Góc camera, Vật liệu & Bố cục chi tiết, Kịch bản ánh sáng & Bối cảnh môi trường, Thông số nhiếp ảnh). ĐƯỢC PHÉP xuống dòng và ngắt đoạn hợp lý giữa các phần.
    3. Phân tích đầy đủ {detail_str}.
    4. BẮT BUỘC bổ sung đầy đủ thông số máy ảnh '16mm wide-angle lens, f/8 aperture, shot on Sony Alpha A7R V' vào phần nhiếp ảnh cuối mỗi phương án.
    5. KHÔNG bao giờ tự ý đưa các mã ký hiệu như 'A1', 'C1', 'I1' làm tiêu đề.
    6. Nếu có thêm ảnh tham chiếu, hãy bổ sung cú pháp sử dụng 2 thẻ **@ảnh phác thảo** (khóa khung nét) và **@ảnh tham chiếu**. {ref_instruction}

    ĐỊNH DẠNG ĐẦU RA BẮT BUỘC:
    Trả về đúng định dạng sau, được phân tách bằng dòng `===PA_SPLIT===`:
    <Prompt Phương án 1 đầy đủ các thành phần cấu trúc>
    ===PA_SPLIT===
    <Prompt Phương án 2 đầy đủ các thành phần cấu trúc>

    Không thêm lời dẫn hay giải thích thừa ngoài định dạng trên.
    """

  content_inputs = [system_instruction, sketch_img]
  if ref_img:
    content_inputs.append(ref_img)
  if extra_notes:
    content_inputs.append(f"Ghi chú bổ sung từ người dùng: {extra_notes}")

  response = model.generate_content(content_inputs)
  result_text = response.text.strip()

  if "===PA_SPLIT===" in result_text:
    parts = result_text.split("===PA_SPLIT===")
    p1 = clean_prompt_text(parts[0])
    p2 = clean_prompt_text(parts[1])
  else:
    p1 = clean_prompt_text(result_text)
    p2 = None

  return p1, p2


# ==================== KHỞI TẠO TABS ====================
tab_ext, tab_int = st.tabs(["🏛️ NGOẠI THẤT", "🛋️ NỘI THẤT"])

# Secret Key từ Server
secret_api_key = st.secrets.get("GEMINI_API_KEY", "")

# -------------------- TAB 1: NGOẠI THẤT --------------------
with tab_ext:
  col_left_e, col_main_e, col_right_e = st.columns([1.0, 1.5, 1.0], gap="medium")
  is_disabled_ext = st.session_state.get("only_light_ext", False)

  with col_left_e:
    with st.expander("⚙️ Cấu hình API & AI Model (Ngoại thất)", expanded=True):
      with st.container(border=True):
        st.markdown("**1. API & Model AI**")
        user_api_key_ext = st.text_input(
            "Gemini API Key (Tùy chọn):",
            type="password",
            placeholder=(
                "Đã dùng Key hệ thống bí mật"
                if secret_api_key
                else "Nhập API Key..."
            ),
            key="api_key_ext_input",
        )
        api_key_ext = (
            user_api_key_ext.strip()
            if user_api_key_ext.strip()
            else secret_api_key
        )
        if secret_api_key and not user_api_key_ext:
          st.caption("🟢 **Trạng thái:** Đã kết nối API Key hệ thống.")
        selected_model_ext = st.selectbox(
            "Model AI:", ["gemini-3.6-flash", "gemini-3.1-pro"], key="model_ext"
        )

      with st.container(border=True):
        st.markdown("**2. Kịch bản Ánh sáng (PA 2)**")
        st.caption(
            "🤖 **Phương án 1:** AI tự động phân tích Style & Nhận diện chuẩn"
            " Góc camera từ phác thảo."
        )
        light_ext_2 = st.selectbox(
            "Kịch bản ánh sáng (PA 2):",
            lighting_ext_options,
            index=3,
            key="light_ext2",
            disabled=is_disabled_ext,
        )

      with st.container(border=True):
        st.markdown("**3. Bối cảnh Môi trường (PA 2)**")
        context_ext_2 = st.selectbox(
            "Bối cảnh môi trường (PA 2):",
            context_ext_options,
            index=1,
            key="context_ext2",
            disabled=is_disabled_ext,
        )

      with st.container(border=True):
        st.markdown("**4. Hiệu ứng Hình ảnh & Nhiếp ảnh (PA 2)**")
        film_ext_2 = st.selectbox(
            "Hiệu ứng màu sắc (PA 2):",
            film_ext_options,
            index=1,
            key="film_ext2",
            disabled=is_disabled_ext,
        )

  with col_main_e:
    h_col_e, b_col_e, s_col_e, c_col_e = st.columns(
        [2.0, 2.0, 0.8, 0.8], vertical_alignment="center"
    )
    with h_col_e:
      st.markdown(
          '<p class="custom-header-title">Kết quả Prompt</p>',
          unsafe_allow_html=True,
      )
    with b_col_e:
      analyze_btn_ext = st.button(
          "Phân tích & Tạo Prompt",
          type="primary",
          use_container_width=True,
          key="btn_anl_ext",
      )
    with s_col_e:
      stop_btn_ext = st.button(
          "⏹️ Dừng", type="secondary", use_container_width=True, key="btn_stop_ext"
      )
    with c_col_e:
      clear_btn_ext = st.button(
          "🗑️ Xóa", use_container_width=True, key="btn_clr_ext"
      )

    if stop_btn_ext:
      st.warning("Đã hủy quá trình phân tích Ngoại thất!")
    if clear_btn_ext:
      st.session_state.p1_res_ext = None
      st.session_state.p2_res_ext = None
      st.session_state.uploader_key_ext += 1
      st.rerun()

    prompt1_text_ext = (
        st.session_state.p1_res_ext
        if st.session_state.p1_res_ext
        else "Chưa có kết quả Ngoại thất PA 1..."
    )
    render_prompt_card(
        "Phương án 1 (AI Đề xuất Style & Nhận diện Góc camera):",
        prompt1_text_ext,
        "p1_ext",
    )
    st.markdown('<div style="margin-top: 6px;"></div>', unsafe_allow_html=True)
    prompt2_text_ext = (
        st.session_state.p2_res_ext
        if st.session_state.p2_res_ext
        else "Chưa có kết quả Ngoại thất PA 2..."
    )
    render_prompt_card(
        "Phương án 2 (Thử nghiệm PA 2):", prompt2_text_ext, "p2_ext"
    )

  with col_right_e:
    with st.expander("🖼️ Tải ảnh phác thảo & Tham chiếu", expanded=True):
      with st.container(border=True):
        st.markdown("**Ảnh phác thảo / CAD:**")
        sketch_file_ext = st.file_uploader(
            "Tải ảnh phác thảo Ngoại thất",
            type=["png", "jpg", "jpeg"],
            label_visibility="collapsed",
            key=f"sketch_up_ext_{st.session_state.uploader_key_ext}",
        )
        if sketch_file_ext:
          sketch_bytes_ext = sketch_file_ext.getvalue()
          sketch_img_ext = Image.open(io.BytesIO(sketch_bytes_ext))
          render_clickable_image(
              file_bytes_to_b64(sketch_bytes_ext), "Ảnh phác thảo Ngoại thất", 0
          )
        else:
          sketch_img_ext = None

      with st.container(border=True):
        r_head1_e, r_head2_e = st.columns(
            [1.1, 1], vertical_alignment="center"
        )
        with r_head1_e:
          st.markdown("**Ảnh tham chiếu:**")
        with r_head2_e:
          only_light_mode_ext = st.checkbox(
              "Chỉ lấy sáng", value=False, key="only_light_ext"
          )
        ref_file_ext = st.file_uploader(
            "Tải ảnh tham chiếu Ngoại thất",
            type=["png", "jpg", "jpeg"],
            label_visibility="collapsed",
            key=f"ref_up_ext_{st.session_state.uploader_key_ext}",
        )
        if ref_file_ext:
          ref_bytes_ext = ref_file_ext.getvalue()
          ref_img_ext = Image.open(io.BytesIO(ref_bytes_ext))
          render_clickable_image(
              file_bytes_to_b64(ref_bytes_ext), "Ảnh tham chiếu Ngoại thất", 1
          )
        else:
          ref_img_ext = None

      extra_notes_ext = st.text_area(
          "Mô tả hoặc yêu cầu bổ sung:",
          placeholder="Ví dụ: biệt thự 3 tầng, thêm cây cảnh nhiệt đới...",
          height=75,
          key=f"notes_ext_{st.session_state.uploader_key_ext}",
      )

  if analyze_btn_ext:
    if not api_key_ext:
      st.error("Vui lòng nhập API Key!")
    elif not sketch_file_ext:
      st.warning("Vui lòng tải lên ảnh phác thảo Ngoại thất!")
    else:
      try:
        p1, p2 = process_gemini_analysis(
            api_key_ext,
            selected_model_ext,
            "",
            "",
            "",
            light_ext_2,
            context_ext_2,
            film_ext_2,
            sketch_img_ext,
            ref_img_ext,
            extra_notes_ext,
            only_light_mode_ext,
            is_interior=False,
        )
        st.session_state.p1_res_ext = p1
        st.session_state.p2_res_ext = p2
        st.session_state.show_dog_modal = True
        st.rerun()
      except Exception as e:
        st.error(f"Lỗi khi kết nối API: {str(e)}")


# -------------------- TAB 2: NỘI THẤT --------------------
with tab_int:
  col_left_i, col_main_i, col_right_i = st.columns([1.0, 1.5, 1.0], gap="medium")
  is_disabled_int = st.session_state.get("only_light_int", False)

  with col_left_i:
    with st.expander("⚙️ Cấu hình API & AI Model (Nội thất)", expanded=True):
      with st.container(border=True):
        st.markdown("**1. API & Model AI**")
        user_api_key_int = st.text_input(
            "Gemini API Key (Tùy chọn):",
            type="password",
            placeholder=(
                "Đã dùng Key hệ thống bí mật"
                if secret_api_key
                else "Nhập API Key..."
            ),
            key="api_key_int_input",
        )
        api_key_int = (
            user_api_key_int.strip()
            if user_api_key_int.strip()
            else secret_api_key
        )
        if secret_api_key and not user_api_key_int:
          st.caption("🟢 **Trạng thái:** Đã kết nối API Key hệ thống.")
        selected_model_int = st.selectbox(
            "Model AI:", ["gemini-3.6-flash", "gemini-3.1-pro"], key="model_int"
        )

      with st.container(border=True):
        st.markdown("**2. Kịch bản Ánh sáng (PA 2)**")
        st.caption(
            "🤖 **Phương án 1:** AI tự động phân tích Style & Nhận diện chuẩn"
            " Góc camera từ phác thảo."
        )
        light_int_2 = st.selectbox(
            "Kịch bản ánh sáng Nội thất (PA 2):",
            lighting_int_options,
            index=4,
            key="light_int2",
            disabled=is_disabled_int,
        )

      with st.container(border=True):
        st.markdown("**3. Bối cảnh Môi trường (PA 2)**")
        context_int_2 = st.selectbox(
            "Bối cảnh môi trường (PA 2):",
            context_int_options,
            index=0,
            key="context_int2",
            disabled=is_disabled_int,
        )

      with st.container(border=True):
        st.markdown("**4. Hiệu ứng Hình ảnh & Nhiếp ảnh (PA 2)**")
        film_int_2 = st.selectbox(
            "Hiệu ứng màu sắc (PA 2):",
            film_int_options,
            index=1,
            key="film_int2",
            disabled=is_disabled_int,
        )

  with col_main_i:
    h_col_i, b_col_i, s_col_i, c_col_i = st.columns(
        [2.0, 2.0, 0.8, 0.8], vertical_alignment="center"
    )
    with h_col_i:
      st.markdown(
          '<p class="custom-header-title">Kết quả Prompt</p>',
          unsafe_allow_html=True,
      )
    with b_col_i:
      analyze_btn_int = st.button(
          "Phân tích & Tạo Prompt",
          type="primary",
          use_container_width=True,
          key="btn_anl_int",
      )
    with s_col_i:
      stop_btn_int = st.button(
          "⏹️ Dừng", type="secondary", use_container_width=True, key="btn_stop_int"
      )
    with c_col_i:
      clear_btn_int = st.button(
          "🗑️ Xóa", use_container_width=True, key="btn_clr_int"
      )

    if stop_btn_int:
      st.warning("Đã hủy quá trình phân tích Nội thất!")
    if clear_btn_int:
      st.session_state.p1_res_int = None
      st.session_state.p2_res_int = None
      st.session_state.uploader_key_int += 1
      st.rerun()

    prompt1_text_int = (
        st.session_state.p1_res_int
        if st.session_state.p1_res_int
        else "Chưa có kết quả Nội thất PA 1..."
    )
    render_prompt_card(
        "Phương án 1 (AI Đề xuất Style & Nhận diện Góc camera):",
        prompt1_text_int,
        "p1_int",
    )
    st.markdown('<div style="margin-top: 6px;"></div>', unsafe_allow_html=True)
    prompt2_text_int = (
        st.session_state.p2_res_int
        if st.session_state.p2_res_int
        else "Chưa có kết quả Nội thất PA 2..."
    )
    render_prompt_card(
        "Phương án 2 (Thử nghiệm PA 2):", prompt2_text_int, "p2_int"
    )

  with col_right_i:
    with st.expander("🖼️ Tải ảnh phác thảo & Tham chiếu", expanded=True):
      with st.container(border=True):
        st.markdown("**Ảnh phác thảo Nội thất / CAD:**")
        sketch_file_int = st.file_uploader(
            "Tải ảnh phác thảo Nội thất",
            type=["png", "jpg", "jpeg"],
            label_visibility="collapsed",
            key=f"sketch_up_int_{st.session_state.uploader_key_int}",
        )
        if sketch_file_int:
          sketch_bytes_int = sketch_file_int.getvalue()
          sketch_img_int = Image.open(io.BytesIO(sketch_bytes_int))
          render_clickable_image(
              file_bytes_to_b64(sketch_bytes_int), "Ảnh phác thảo Nội thất", 2
          )
        else:
          sketch_img_int = None

      with st.container(border=True):
        r_head1_i, r_head2_i = st.columns(
            [1.1, 1], vertical_alignment="center"
        )
        with r_head1_i:
          st.markdown("**Ảnh tham chiếu Nội thất:**")
        with r_head2_i:
          only_light_mode_int = st.checkbox(
              "Chỉ lấy sáng", value=False, key="only_light_int"
          )
        ref_file_int = st.file_uploader(
            "Tải ảnh tham chiếu Nội thất",
            type=["png", "jpg", "jpeg"],
            label_visibility="collapsed",
            key=f"ref_up_int_{st.session_state.uploader_key_int}",
        )
        if ref_file_int:
          ref_bytes_int = ref_file_int.getvalue()
          ref_img_int = Image.open(io.BytesIO(ref_bytes_int))
          render_clickable_image(
              file_bytes_to_b64(ref_bytes_int), "Ảnh tham chiếu Nội thất", 3
          )
        else:
          ref_img_int = None

      extra_notes_int = st.text_area(
          "Mô tả hoặc yêu cầu bổ sung:",
          placeholder=(
              "Ví dụ: phòng khách hiện đại, sofa da bò, đèn chùm cao cấp..."
          ),
          height=75,
          key=f"notes_int_{st.session_state.uploader_key_int}",
      )

  if analyze_btn_int:
    if not api_key_int:
      st.error("Vui lòng nhập API Key!")
    elif not sketch_file_int:
      st.warning("Vui lòng tải lên ảnh phác thảo Nội thất!")
    else:
      try:
        p1, p2 = process_gemini_analysis(
            api_key_int,
            selected_model_int,
            "",
            "",
            "",
            light_int_2,
            context_int_2,
            film_int_2,
            sketch_img_int,
            ref_img_int,
            extra_notes_int,
            only_light_mode_int,
            is_interior=True,
        )
        st.session_state.p1_res_int = p1
        st.session_state.p2_res_int = p2
        st.session_state.show_dog_modal = True
        st.rerun()
      except Exception as e:
        st.error(f"Lỗi khi kết nối API: {str(e)}")
