import streamlit as st
import streamlit.components.v1 as components
import google.generativeai as genai
from PIL import Image
import re, os, io, base64, html

# Cấu hình trang Streamlit
st.set_page_config(page_title="KATO AI - Vision Prompt Generator", layout="wide")

# Khởi tạo session_state
if "p1_res" not in st.session_state:
    st.session_state.p1_res = None
if "p2_res" not in st.session_state:
    st.session_state.p2_res = None
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0
if "show_dog_modal" not in st.session_state:
    st.session_state.show_dog_modal = False

# Hàm chuẩn hóa văn bản về 1 đoạn liền mạch
def clean_to_single_paragraph(text: str) -> str:
    if not text:
        return ""
    lines = [re.sub(r'^\s*[\-\*\•\d\.]+\s*', '', line).strip() for line in text.splitlines() if line.strip()]
    single_line = " ".join(lines)
    return re.sub(r'\s+', ' ', single_line).strip()

# Hàm chuyển đổi PIL Image sang Base64
def image_to_b64(img):
    buffered = io.BytesIO()
    if img.mode in ("RGBA", "P"):
        img_conv = img.convert("RGBA")
        img_conv.save(buffered, format="PNG")
    else:
        img_conv = img.convert("RGB")
        img_conv.save(buffered, format="JPEG", quality=90)
    return base64.b64encode(buffered.getvalue()).decode()

# Hàm lọc bỏ nền xanh lá của ảnh chú chó
def get_transparent_dog_b64():
    target_file = None
    explicit_files = [
        "image_45819f.png", "image_45819f.jpg", "image_45819f.jpeg",
        "dog.png", "dog.jpg", "dog.jpeg", "chihuahua.png", "chihuahua.jpg"
    ]
    for f in explicit_files:
        if os.path.exists(f):
            target_file = f
            break
            
    if not target_file:
        for f in os.listdir("."):
            if f.lower().endswith((".png", ".jpg", ".jpeg")):
                if "458" in f.lower() or "dog" in f.lower() or "chihuahua" in f.lower() or f.startswith("image_"):
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

# Hiển thị khung Prompt
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
            .header-row {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }}
            .title-text {{ font-weight: 600; color: #ffffff; font-size: 0.95rem; }}
            .copy-btn {{ background-color: #363945; color: #e0e0e0; border: 1px solid #484c5a; padding: 4px 12px; border-radius: 6px; cursor: pointer; font-size: 0.82rem; font-weight: 600; transition: all 0.2s ease; outline: none; }}
            .copy-btn:hover {{ background-color: #484c5a; color: #ffffff; }}
            .prompt-box {{ background-color: #1e1e24; border: 1px solid #363945; border-radius: 8px; padding: 0.85rem; height: 350px; overflow-y: auto; font-family: monospace, Consolas, "Courier New"; font-size: 0.92rem; line-height: 1.55; color: #e0e0e0; white-space: pre-wrap; word-wrap: break-word; word-break: break-word; }}
            .prompt-box::-webkit-scrollbar {{ width: 6px; }}
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
    components.html(html_code, height=390)

# Hiển thị ảnh xem trước bấm đè hoặc xóa X
def render_clickable_image(img_b64, caption, uploader_index):
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            * {{ box-sizing: border-box; }}
            body {{ margin: 0; padding: 0; background-color: transparent; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
            .img-container {{ position: relative; width: 100%; height: 200px; cursor: pointer; border-radius: 8px; overflow: hidden; border: 1.5px dashed #484c5a; transition: all 0.25s ease; background-color: #1e1e24; display: flex; justify-content: center; align-items: center; }}
            .img-container:hover {{ border-color: #28a745; box-shadow: 0 0 12px rgba(40, 167, 69, 0.35); }}
            .img-container img {{ max-height: 190px; width: 100%; object-fit: contain; display: block; transition: filter 0.25s ease, transform 0.25s ease; }}
            .img-container:hover img {{ filter: brightness(0.45); transform: scale(1.01); }}
            .overlay-text {{ position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); color: #ffffff; font-weight: 700; font-size: 0.88rem; background: rgba(38, 39, 48, 0.92); padding: 8px 16px; border-radius: 20px; opacity: 0; transition: opacity 0.25s ease; pointer-events: none; white-space: nowrap; border: 1px solid #28a745; box-shadow: 0 4px 12px rgba(0,0,0,0.5); }}
            .img-container:hover .overlay-text {{ opacity: 1; }}
            .delete-x-btn {{ position: absolute; top: 8px; right: 8px; width: 28px; height: 28px; background-color: #dc3545; color: #ffffff; border: 1px solid #ff6b6b; border-radius: 50%; font-size: 14px; font-weight: bold; display: flex; align-items: center; justify-content: center; cursor: pointer; z-index: 99; box-shadow: 0 2px 8px rgba(0,0,0,0.6); transition: all 0.2s ease; outline: none; }}
            .delete-x-btn:hover {{ background-color: #bd2130; transform: scale(1.15); }}
            .caption-text {{ text-align: center; color: #a0a0a0; font-size: 0.8rem; margin-top: 4px; font-weight: 500; }}
        </style>
    </head>
    <body>
        <div class="img-container" title="Nhấp vào ảnh để chọn ảnh khác" onclick="changeImage()">
            <button class="delete-x-btn" title="Xóa ảnh này" onclick="deleteImage(event)">✖</button>
            <img src="data:image/png;base64,{img_b64}" />
            <div class="overlay-text">📷 Nhấp vào ảnh để thay đổi</div>
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
    components.html(html_code, height=230)

# CSS GIAO DIỆN HỆ THỐNG
st.markdown("""
<style>
section[data-testid="stSidebar"] { display: none !important; }
div[data-testid="stHeader"], header[data-testid="stHeader"] { display: flex !important; background: transparent !important; z-index: 99 !important; pointer-events: none !important; }
div[data-testid="stHeader"] *, header[data-testid="stHeader"] * { pointer-events: auto !important; }

.block-container { padding-top: 2.6rem !important; padding-bottom: 0.2rem !important; padding-left: 1.2rem !important; padding-right: 1.2rem !important; max-width: 100% !important; margin-top: 0rem !important; }

div[data-testid="stExpander"] { background-color: #1e1e24 !important; border: 1px solid #363945 !important; border-radius: 10px !important; box-shadow: 0 4px 12px rgba(0,0,0,0.15) !important; }
div[data-testid="stExpander"]:has(details[open]) { height: calc(100vh - 3.8rem) !important; min-height: calc(100vh - 3.8rem) !important; max-height: calc(100vh - 3.8rem) !important; display: flex !important; flex-direction: column !important; }
div[data-testid="stExpander"]:has(details:not([open])) { height: auto !important; min-height: auto !important; max-height: auto !important; }
div[data-testid="stExpander"] details { display: flex !important; flex-direction: column !important; height: 100% !important; overflow: hidden !important; }
div[data-testid="stExpander"] details summary { font-weight: 600 !important; font-size: 0.95rem !important; color: #e0e0e0 !important; padding: 0.5rem 0.8rem !important; flex-shrink: 0 !important; }
div[data-testid="stExpander"] details > div[role="region"] { overflow: auto !important; padding-right: 0.3rem !important; padding-left: 0.2rem !important; padding-bottom: 0.2rem !important; flex: 1 !important; }

div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 8px !important; background-color: #262730 !important; border: 1px solid #363945 !important; margin-bottom: 0.4rem !important; padding: 0.5rem !important; }

.custom-header-title { white-space: nowrap !important; font-size: 1.35rem !important; font-weight: 700 !important; color: #ffffff !important; margin: 0 !important; line-height: 36px !important; }
.dashed-divider { border: none !important; border-top: 1.5px dashed #484c5a !important; margin: 0.1rem 0 0.1rem 0 !important; width: 100% !important; }

div[data-testid="stFileUploader"]:has(div[data-testid="stFileUploaderFileData"]),
div[data-testid="stFileUploader"]:has(span[data-testid="stFileUploaderFileName"]),
div[data-testid="stFileUploader"]:has(button[title="Remove file"]),
div[data-testid="stFileUploader"]:has(button[aria-label*="Remove"]),
div[data-testid="stFileUploader"]:has(ul) { position: absolute !important; opacity: 0 !important; height: 0 !important; width: 0 !important; max-height: 0 !important; margin: 0 !important; padding: 0 !important; overflow: hidden !important; pointer-events: none !important; }

div[data-testid="stTextArea"] textarea { height: 115px !important; max-height: 115px !important; }

button[kind="primary"] { background-color: #28a745 !important; color: #ffffff !important; border: none !important; height: 40px !important; border-radius: 8px !important; font-weight: 600 !important; font-size: 0.95rem !important; }
button[kind="primary"]:hover { background-color: #218838 !important; }
button[kind="secondary"] { background-color: #dc3545 !important; color: #ffffff !important; border: none !important; height: 40px !important; border-radius: 8px !important; font-weight: 600 !important; font-size: 0.95rem !important; }
button[kind="secondary"]:hover { background-color: #c82333 !important; }

div[data-testid="stColumn"] div[data-testid="stColumn"]:nth-child(4) button { background-color: #495057 !important; color: #ffffff !important; border: none !important; height: 40px !important; border-radius: 8px !important; font-weight: 600 !important; font-size: 0.95rem !important; }
div[data-testid="stColumn"] div[data-testid="stColumn"]:nth-child(4) button:hover { background-color: #343a40 !important; }
</style>
""", unsafe_allow_html=True)

# THÔNG BÁO CHÚ CHÓ
if st.session_state.get("show_dog_modal", False):
    st.session_state.show_dog_modal = False
    dog_b64 = get_transparent_dog_b64()
    img_src = f"data:image/png;base64,{dog_b64}" if dog_b64 else ""

    components.html(f"""
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
    """, height=0)

film_options = [
    "B0 - None (Không sử dụng hiệu ứng màu)",
    "B1 - Fujifilm Classic Chrome",
    "B2 - Fujifilm Classic Negative",
    "B3 - Kodak Portra 400",
    "B4 - CineStill 800T",
    "B5 - Hasselblad + Tilt-Shift",
    "B6 - Black Pro-Mist 1/4"
]

col_left, col_main, col_right = st.columns([1.0, 1.5, 1.0], gap="medium")

# CỘT TRÁI
with col_left:
    with st.expander("⚙️ Cấu hình API & AI Model", expanded=True):
        with st.container(border=True):
            st.markdown("**1. API & Model AI**")
            
            # Lấy Key bí mật từ Server Secrets
            secret_api_key = st.secrets.get("GEMINI_API_KEY", "")
            
            # Ô nhập để trống, dùng Key bí mật ngầm định ở backend
            user_api_key = st.text_input(
                "Gemini API Key (Tùy chọn):", 
                type="password", 
                placeholder="Đã dùng Key hệ thống bí mật" if secret_api_key else "Nhập API Key của bạn...",
                help="Để trống để sử dụng API Key mặc định của công ty."
            )
            
            api_key = user_api_key.strip() if user_api_key.strip() else secret_api_key
            
            if secret_api_key and not user_api_key:
                st.caption("🟢 **Trạng thái:** Đã kết nối API Key hệ thống (Bảo mật).")
                
            selected_model = st.selectbox("Model AI:", ["gemini-3.6-flash", "gemini-3.1-pro"])
        
        with st.container(border=True):
            st.markdown("**2. Phương án 1 (Mặc định)**")
            lighting_opt1 = st.selectbox("Kịch bản ánh sáng (PA 1):", ["A1 - Ban ngày trong trẻo (Pure Daylight)", "A2 - Hoàng hôn ấm áp (Golden Hour)", "A3 - Chạng vạng lên đèn (Twilight 3000K)", "A4 - Hỗn hợp Nội thất (Hybrid Lighting)"], key="light1")
            film_opt1 = st.selectbox("Hiệu ứng màu sắc (PA 1):", film_options, index=1, key="film1")

        with st.container(border=True):
            st.markdown("**3. Phương án 2 (Bổ sung)**")
            lighting_opt2 = st.selectbox("Kịch bản ánh sáng (PA 2):", ["A1 - Ban ngày trong trẻo (Pure Daylight)", "A2 - Hoàng hôn ấm áp (Golden Hour)", "A3 - Chạng vạng lên đèn (Twilight 3000K)", "A4 - Hỗn hợp Nội thất (Hybrid Lighting)"], index=1, key="light2")
            film_opt2 = st.selectbox("Hiệu ứng màu sắc (PA 2):", film_options, index=3, key="film2")

# CỘT GIỮA
with col_main:
    header_col, btn_col, stop_col, clear_col = st.columns([2.0, 2.0, 0.8, 0.8], vertical_alignment="center")
    with header_col: st.markdown('<p class="custom-header-title">Kết quả Prompt</p>', unsafe_allow_html=True)
    with btn_col: analyze_btn = st.button("Phân tích ảnh & Tạo Prompt", type="primary", use_container_width=True)
    with stop_col: stop_btn = st.button("⏹️ Dừng", type="secondary", use_container_width=True)
    with clear_col: clear_btn = st.button("🗑️ Xóa", use_container_width=True)

    if stop_btn: st.warning("Đã hủy quá trình phân tích!")
    if clear_btn:
        st.session_state.p1_res = None
        st.session_state.p2_res = None
        st.session_state.uploader_key += 1
        st.rerun()

    prompt1_text = st.session_state.p1_res if st.session_state.p1_res else "Chưa có kết quả. Vui lòng tải ảnh và bấm 'Phân tích ảnh & Tạo Prompt'..."
    render_prompt_card("Phương án 1:", prompt1_text, "p1")
    st.markdown('<hr class="dashed-divider" />', unsafe_allow_html=True)
    prompt2_text = st.session_state.p2_res if st.session_state.p2_res else "Chưa có kết quả Phương án 2..."
    render_prompt_card("Phương án 2:", prompt2_text, "p2")

# CỘT PHẢI
with col_right:
    with st.expander("🖼️ Tải ảnh phác thảo & Tham chiếu", expanded=True):
        with st.container(border=True):
            st.markdown("**Ảnh phác thảo / CAD:**")
            sketch_file = st.file_uploader("Tải ảnh phác thảo", type=["png", "jpg", "jpeg"], label_visibility="collapsed", key=f"sketch_up_{st.session_state.uploader_key}")
            if sketch_file:
                sketch_img = Image.open(sketch_file)
                b64_str = image_to_b64(sketch_img)
                render_clickable_image(b64_str, "Ảnh phác thảo đầu vào", 0)
            else: sketch_img = None

        with st.container(border=True):
            r_head1, r_head2 = st.columns([1.1, 1], vertical_alignment="center")
            with r_head1: st.markdown("**Ảnh tham chiếu:**")
            with r_head2: only_light_mode = st.checkbox("Chỉ lấy sáng", value=False)
            ref_file = st.file_uploader("Tải ảnh tham chiếu", type=["png", "jpg", "jpeg"], label_visibility="collapsed", key=f"ref_up_{st.session_state.uploader_key}")
            if ref_file:
                ref_img = Image.open(ref_file)
                b64_str_ref = image_to_b64(ref_img)
                render_clickable_image(b64_str_ref, "Ảnh tham chiếu phong cách", 1)
            else: ref_img = None

        extra_notes = st.text_area("Mô tả hoặc yêu cầu bổ sung (nếu có):", placeholder="Ví dụ: biệt thự 3 tầng, bổ sung cây xanh nhiệt đới...", height=115, key=f"extra_notes_{st.session_state.uploader_key}")

# XỬ LÝ API
if analyze_btn:
    if not api_key: st.error("Vui lòng mở Panel Cấu hình API bên trái và nhập API Key!")
    elif not sketch_file: st.warning("Vui lòng mở Panel Tải ảnh bên phải và tải lên ít nhất 1 ảnh phác thảo!")
    else:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(selected_model)

            ref_instruction = ""
            if ref_file:
                if only_light_mode:
                    ref_instruction = "LƯU Ý ĐẶC BIỆT CHO @ảnh tham chiếu: CHỈ TRÍCH XUẤT duy nhất kịch bản ánh sáng, góc nắng đổ bóng, nhiệt độ màu và không khí ánh sáng từ **@ảnh tham chiếu**. BẢO TỒN HOÀN TOÀN toàn bộ vật liệu, màu sắc bề mặt và bối cảnh từ **@ảnh phác thảo**."
                else:
                    ref_instruction = "Đối với **@ảnh tham chiếu**, trích xuất toàn bộ bối cảnh môi trường xung quanh, kịch bản ánh sáng và các bề mặt vật liệu/bảng màu chính để áp lên khung nét của **@ảnh phác thảo**."

            clean_light1 = lighting_opt1.split(" - ")[1] if " - " in lighting_opt1 else lighting_opt1
            clean_film1 = film_opt1.split(" - ")[1] if " - " in film_opt1 else film_opt1
            film_text1 = f"kết hợp hiệu ứng {clean_film1}" if "B0 - None" not in film_opt1 else "giữ màu sắc tự nhiên chân thực, không áp hiệu ứng màu phim"
            
            clean_light2 = lighting_opt2.split(" - ")[1] if " - " in lighting_opt2 else lighting_opt2
            clean_film2 = film_opt2.split(" - ")[1] if " - " in film_opt2 else film_opt2
            film_text2 = f"kết hợp hiệu ứng {clean_film2}" if "B0 - None" not in film_opt2 else "giữ màu sắc tự nhiên chân thực, không áp hiệu ứng màu phim"
            
            system_instruction = f"""
            Bạn là một chuyên gia phân tích kiến trúc và diễn họa 3D. 
            Hãy nhìn vào hình ảnh phác thảo được cung cấp và tạo ra CÁC CÂU LỆNH (prompt) mô tả chi tiết bằng TIẾNG VIỆT để đưa vào phần mềm sinh ảnh Flow.

            Nhiệm vụ của bạn là tạo ra 2 PHƯƠNG ÁN PROMPT (Phương án 1 và Phương án 2) để so sánh kịch bản ánh sáng và hiệu ứng màu sắc.

            BẮT BUỘC ĐỒNG BỘ VẬT LIỆU & HÌNH KHỐI (100% GIỐNG NHAU):
            - Toàn bộ nội dung mô tả hình khối kiến trúc, góc chụp, bố cục ô cửa, từng chất liệu bề mặt (gạch, đá, gỗ, sơn, kính...) và bối cảnh cây xanh đô thị của Phương án 1 và Phương án 2 BẮT BUỘC PHẢI GIỐNG NHAU 100% (dùng chung một mô tả vật liệu được trích xuất từ **@ảnh phác thảo**).
            - Sự khác biệt DUY NHẤT giữa 2 phương án là đoạn miêu tả kịch bản ánh sáng và thông số nhiếp ảnh ở cuối câu lệnh:
              + Phương án 1: Không khí ánh sáng theo phong cách {clean_light1}, shot on Sony Alpha A7R V {film_text1}.
              + Phương án 2: Không khí ánh sáng theo phong cách {clean_light2}, shot on Sony Alpha A7R V {film_text2}.

            Quy tắc bắt buộc chung:
            1. Cả 2 câu lệnh BẮT BUỘC bắt đầu bằng cụm từ chính xác: 'Ảnh chụp thực tế'.
            2. QUY TẮC TRÌNH BÀY BẮT BUỘC: Mỗi phương án CHỈ ĐƯỢC VIẾT THÀNH 01 ĐOẠN VĂN LIỀN MẠCH DUY NHẤT. Tuyệt đối KHÔNG xuống dòng, KHÔNG tạo đoạn mới, KHÔNG dùng gạch đầu dòng, KHÔNG tạo danh sách dạng số.
            3. Phân tích đầy đủ hình khối, số tầng, góc quay (mặt tiền, góc chéo 3/4, toàn cảnh nội thất...), từng chất liệu bề mặt các tầng và bối cảnh Việt Nam.
            4. KHÔNG bao giờ tự ý đưa các mã ký hiệu như 'A1', 'A2', 'Kịch bản ánh sáng A1' vào văn bản prompt.
            5. Nếu có thêm ảnh tham chiếu, hãy bổ sung cú pháp sử dụng 2 thẻ **@ảnh phác thảo** (khóa khung nét) và **@ảnh tham chiếu**. {ref_instruction}
            
            ĐỊNH DẠNG ĐẦU RA BẮT BUỘC:
            Trả về đúng định dạng sau, được phân tách bằng dòng `===PA_SPLIT===`:
            <01 đoạn văn liền mạch duy nhất của Phương án 1>
            ===PA_SPLIT===
            <01 đoạn văn liền mạch duy nhất của Phương án 2>

            Không thêm lời dẫn hay giải thích thừa ngoài định dạng trên.
            """

            content_inputs = [system_instruction, sketch_img]
            if ref_img: content_inputs.append(ref_img)
            if extra_notes: content_inputs.append(f"Ghi chú bổ sung từ người dùng: {extra_notes}")

            response = model.generate_content(content_inputs)
            result_text = response.text.strip()
            
            if "===PA_SPLIT===" in result_text:
                parts = result_text.split("===PA_SPLIT===")
                st.session_state.p1_res = clean_to_single_paragraph(parts[0])
                st.session_state.p2_res = clean_to_single_paragraph(parts[1])
            else:
                st.session_state.p1_res = clean_to_single_paragraph(result_text)
                st.session_state.p2_res = None
            
            st.session_state.show_dog_modal = True
            st.rerun()
            
        except Exception as e:
            st.error(f"Lỗi khi kết nối API: {str(e)}")
