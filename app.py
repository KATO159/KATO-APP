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

# ---------------- KHỞI TẠO STATE ----------------
for key in ["en_prompt_ext", "vi_prompt_ext", "en_prompt_int", "vi_prompt_int"]:
    if key not in st.session_state:
        st.session_state[key] = ""

if "uploader_key_ext" not in st.session_state:
    st.session_state.uploader_key_ext = 0
if "uploader_key_int" not in st.session_state:
    st.session_state.uploader_key_int = 0

if "api_models" not in st.session_state:
    st.session_state.api_models = ["gemini-pro-latest", "gemini-flash-latest"]
# ------------------------------------------------


# Hàm làm sạch văn bản & xóa từ khóa cấm nhiễu
def clean_prompt_text(text: str) -> str:
    if not text:
        return ""
    prohibited_patterns = [
        r"--[a-z0-9]+", r"\b8k\b", r"\b16k\b", r"\bphotorealistic\b",
        r"\bhyperrealistic\b", r"\bcorona render\b", r"\bvray\b",
        r"\boctane render\b", r"\bunreal engine\b", r"\bmasterpiece\b"
    ]
    cleaned = text
    for pattern in prohibited_patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    # Lọc bỏ khoảng trắng thừa nhưng vẫn giữ lại ngắt dòng
    lines = [line.strip() for line in cleaned.splitlines()]
    return "\n\n".join([line for line in lines if line]).strip()


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
    explicit_files = ["image_45819f.png", "image_45819f.jpg", "dog.png", "chihuahua.png"]
    for f in explicit_files:
        if os.path.exists(f):
            target_file = f
            break
    if not target_file:
        for f in os.listdir("."):
            if f.lower().endswith((".png", ".jpg", ".jpeg")):
                if "458" in f.lower() or "dog" in f.lower() or "chihuahua" in f.lower():
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

# Gọi chó chức mừng trực tiếp (không dùng Rerun)
def show_success_dog():
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
            modal.style.position = 'fixed'; modal.style.top = '0'; modal.style.left = '0'; modal.style.width = '100vw'; modal.style.height = '100vh'; modal.style.backgroundColor = 'rgba(0, 0, 0, 0.78)'; modal.style.zIndex = '9999999'; modal.style.display = 'flex'; modal.style.justifyContent = 'center'; modal.style.alignItems = 'center';

            var card = parentDoc.createElement('div');
            card.style.backgroundColor = '#262730'; card.style.border = '2px solid #28a745'; card.style.borderRadius = '16px'; card.style.padding = '25px 35px'; card.style.textAlign = 'center';

            var imgStr = '{img_src}';
            if (imgStr) {{
                var img = parentDoc.createElement('img'); img.src = imgStr; img.style.maxHeight = '200px'; img.style.margin = '0 auto 12px auto'; img.style.display = 'block'; card.appendChild(img);
            }}

            var txt = parentDoc.createElement('div'); txt.style.fontSize = '1.3rem'; txt.style.fontWeight = '800'; txt.style.color = '#28a745'; txt.innerText = 'ĐÃ TẠO XONG PROMPT TỐI ƯU!'; card.appendChild(txt);
            modal.appendChild(card); parentDoc.body.appendChild(modal);

            setTimeout(function() {{
                if (modal && modal.parentNode) modal.parentNode.removeChild(modal);
            }}, 1800);
        }})();
        </script>
        """,
        height=0,
    )


# Hiển thị ảnh xem trước
def render_clickable_image(img_b64, caption, uploader_index):
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            * {{ box-sizing: border-box; }}
            body {{ margin: 0; padding: 0; background-color: transparent; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
            .img-container {{ position: relative; width: 100%; height: 135px; cursor: pointer; border-radius: 8px; overflow: hidden; border: 1.5px dashed #484c5a; transition: all 0.25s ease; background-color: #1e1e24; display: flex; justify-content: center; align-items: center; }}
            .img-container:hover {{ border-color: #28a745; box-shadow: 0 0 12px rgba(40, 167, 69, 0.35); }}
            .img-container img {{ max-height: 125px; width: 100%; object-fit: contain; display: block; }}
            .overlay-text {{ position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); color: #ffffff; font-weight: 700; font-size: 0.82rem; background: rgba(38, 39, 48, 0.92); padding: 6px 12px; border-radius: 16px; opacity: 0; transition: opacity 0.25s ease; pointer-events: none; border: 1px solid #28a745; }}
            .img-container:hover .overlay-text {{ opacity: 1; }}
            .caption-text {{ text-align: center; color: #a0a0a0; font-size: 0.75rem; margin-top: 3px; font-weight: 500; }}
        </style>
    </head>
    <body>
        <div class="img-container" onclick="changeImage()">
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
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=160)


# Giao diện Box Copy Prompt (UI Component)
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
            .header-row {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }}
            .title-text {{ font-weight: 700; color: #38bdf8; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 0.5px; }}
            .copy-btn {{ background-color: #28a745; color: #ffffff; border: none; padding: 6px 14px; border-radius: 6px; cursor: pointer; font-size: 0.8rem; font-weight: 600; transition: all 0.2s ease; outline: none; box-shadow: 0 2px 4px rgba(0,0,0,0.2); }}
            .copy-btn:hover {{ background-color: #218838; transform: translateY(-1px); }}
            .prompt-box {{ background-color: #1e1e24; border: 1px solid #363945; border-radius: 8px; padding: 1.2rem; height: 260px; overflow-y: auto; font-family: "Courier New", Courier, monospace; font-size: 0.95rem; line-height: 1.6; color: #7dd3fc; white-space: pre-wrap; word-wrap: break-word; word-break: break-word; }}
            .prompt-box::-webkit-scrollbar {{ width: 6px; }}
            .prompt-box::-webkit-scrollbar-track {{ background: #1e1e24; border-radius: 8px; }}
            .prompt-box::-webkit-scrollbar-thumb {{ background: #484c5a; border-radius: 8px; }}
        </style>
    </head>
    <body>
        <div class="header-row">
            <span class="title-text">{title}</span>
            <button id="btn_{box_id}" class="copy-btn" onclick="copyText()">📋 COPY PROMPT</button>
        </div>
        <div id="text_{box_id}" class="prompt-box">{escaped_text}</div>
        <script>
        function copyText() {{
            var el = document.getElementById("text_{box_id}");
            if (!el) return;
            var text = el.innerText || el.textContent;
            var btn = document.getElementById("btn_{box_id}");
            function onSuccess() {{
                btn.innerHTML = "✅ ĐÃ SAO CHÉP!"; btn.style.backgroundColor = "#d97706";
                setTimeout(function() {{ btn.innerHTML = "📋 COPY PROMPT"; btn.style.backgroundColor = "#28a745"; }}, 2000);
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
    components.html(html_code, height=320)


# CSS GIAO DIỆN HỆ THỐNG
st.markdown(
    """
<style>
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
section[data-testid="stSidebar"] { display: none !important; }
.block-container {
    padding-top: 2.8rem !important;
    padding-bottom: 1.0rem !important;
    padding-left: 1.5rem !important;
    padding-right: 1.5rem !important;
    max-width: 100% !important;
}
div[data-baseweb="tab-list"] {
    z-index: 999999 !important;
    position: relative !important;
}
button[data-baseweb="tab"] {
    font-size: 1.0rem !important;
    font-weight: 700 !important;
    padding: 0.4rem 1.5rem !important;
    border-radius: 8px 8px 0 0 !important;
}
button[aria-selected="true"] {
    background-color: #262730 !important;
    color: #28a745 !important;
    border-bottom: 3px solid #28a745 !important;
}
.custom-header-title { white-space: nowrap !important; font-size: 1.2rem !important; font-weight: 700 !important; color: #ffffff !important; margin: 0 !important; line-height: 32px !important; }
button[kind="primary"] { background-color: #28a745 !important; color: #ffffff !important; border: none !important; height: 42px !important; border-radius: 6px !important; font-weight: 700 !important; font-size: 0.95rem !important; transition: all 0.2s ease !important; }
button[kind="primary"]:hover { background-color: #218838 !important; transform: translateY(-2px); box-shadow: 0 4px 8px rgba(40,167,69,0.3); }

/* Tùy chỉnh độ rộng Selectbox để hiển thị hết chữ */
div[data-testid="stSelectbox"] label { font-size: 0.85rem !important; font-weight: 600 !important; color: #a0a0a0 !important;}
</style>
""",
    unsafe_allow_html=True,
)

# ==================== DANH SÁCH TÙY CHỌN ====================

# Ngoại thất
lighting_ext_options = [
    "A1 - Nắng sáng sớm trong trẻo (Bright Early Morning Sun)",
    "A2 - Nắng trưa rực rỡ & Bóng đổ sắc nét (High Noon Direct Sun & Sharp Shadows)",
    "A3 - Ngày mây / Ánh sáng tán xạ (Overcast Diffused Light - True Material Focus)",
    "A4 - Hoàng hôn rực rỡ / Giờ vàng (Golden Hour Warm Sunset)",
    "A5 - Chạng vạng lên đèn kiến trúc (Blue Hour & Facade Lighting)",
    "A6 - Đêm huyền bí & Điểm nhấn cảnh quan (Moody Night & Landscape Spotlights)",
    "A7 - Sau mưa / Sân ướt phản chiếu (Post-Rain Wet Surface Reflections)"
]

context_ext_options = [
    "C1 - Phố thị hiện đại (Urban Street & Paved Sidewalk - Natural Layout)",
    "C2 - Biệt thự sân vườn nhiệt đới (Tropical Villa Garden & Pool - Gentle Greenery)",
    "C3 - Ngoại ô / Khu nghỉ dưỡng (Suburban Resort & Nature Greenery - Balanced Surroundings)",
    "C4 - Mặt đường sau mưa (Post-Rain Wet Asphalt Reflections - Realistic Night Reflections)",
    "C5 - Nhà phố liền kề / Đường thẳng (Mid-block townhouse on a straight continuous street, flanked by adjacent buildings, strictly not a corner lot)"
]

film_ext_options = [
    "B0 - None (Màu nguyên bản công trình)",
    "B1 - Tạp chí Kiến trúc Cao cấp (Architectural Digest - Clean & High Contrast)",
    "B2 - Nhiếp ảnh Tạp chí Hiện đại (Fujifilm Classic Chrome - Architectural Tone)",
    "B3 - Tông Ấm Cổ điển (Kodak Portra 400 - Warm Vintage Vibe)",
    "B4 - Đêm Điện ảnh Đô thị (CineStill 800T - Night Halation & Glow)",
    "B5 - Nhiếp ảnh trong trẻo (Clean & Zero Perspective Distortion)"
]

# Nội thất
lighting_int_options = [
    "I1 - Nắng sáng sớm qua rèm voan (Soft Morning Sun & Sheer Curtains)",
    "I2 - Nắng trưa tương phản cao (High Noon & Crisp Shadows)",
    "I3 - Luồng nắng xuyên khe (Volumetric God Rays)",
    "I4 - Trời u uất / Ánh sáng tán xạ đều (Overcast Ambient Light - Material Focus)",
    "I5 - Đèn ấm thư giãn (Warm Cozy Mood 2700K - 3000K)",
    "I6 - Đèn trung tính hiện đại (Neutral Daylight 4000K - 4500K)",
    "I7 - Đèn LED hắt khe & Ray âm trần (Modern Cove LED & Magnetic Track Lights)",
    "I8 - Hỗn hợp Hoàng hôn & Đèn trong nhà (Golden Hour & Indoor Warm Lights)",
    "I9 - Tối nghệ thuật & Đèn rọi điểm nhấn (Moody Dark & Accent Spotlights)",
    "I10 - Đèn dải màu / Gaming / Bar (RGB Linear Strip & Modern Accent Light)"
]

context_int_options = [
    "C1 - View sân vườn nhiệt đới qua kính (Glass Wall to Tropical Garden View - Soft Ambient Green)",
    "C2 - View thành phố trên cao (High-Rise City Skyline View - Natural High-Rise Light)",
    "C3 - Vệt nắng & Hạt bụi vờn nhẹ (Volumetric Sunlight & Floating Dust Motes - Atmospheric Depth)",
    "C4 - Dấu vết sinh hoạt tự nhiên (Lived-in Natural Details - Fresh Flora & Balanced Decor)"
]

film_int_options = [
    "F0 - None (Màu nguyên bản chất liệu)",
    "F1 - Tạp chí Sáng trong (Architectural Digest - Clean & Bright Showcase)",
    "F2 - Tông Gỗ & Đất Ấm áp (Kodak Portra 400 - Warm Wood & Earth Tones)",
    "F3 - Mộc mạc & Creamy (Fuji Pro 400H - Soft & Airy Pastel)",
    "F4 - Sang trọng Điện ảnh (Cinematic Moody - Deep Shadows & Contrast)",
    "F5 - Ấm áp Cổ điển (Kodak Gold 200 - Vintage Warm Gold Tone)",
    "F6 - Kính lọc Tán mờ Đèn (Black Pro-Mist 1/4 - Soft Glow Lights)",
    "F7 - Chi tiết Siêu nét (Clean & High Texture)"
]


# HÀM XỬ LÝ GỌI API GEMINI (TỰ ĐỘNG NHẬN DIỆN GÓC CAMERA)
def process_gemini_analysis_bilingual(
    api_key,
    selected_model_display,
    light_opt,
    context_opt,
    film_opt,
    sketch_img,
    ref_img,
    extra_notes,
    is_interior=False,
):
    genai.configure(api_key=api_key)
    model_name = f"models/{selected_model_display}"
    model = genai.GenerativeModel(model_name)

    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
    ]

    domain = "INTERIOR ARCHITECTURE" if is_interior else "EXTERIOR ARCHITECTURE"

    clean_light = light_opt.split(" - ")[1] if " - " in light_opt else light_opt
    clean_context = context_opt.split(" - ")[1] if " - " in context_opt else context_opt
    clean_film = film_opt.split(" - ")[1] if " - " in film_opt else film_opt

    if "B0" in film_opt or "F0" in film_opt:
        film_instruction = "Apply natural true-to-life colors without any film filter."
    else:
        film_instruction = f"Apply {clean_film} photography style and color grading."

    system_instruction = f"""
    You are an expert architectural prompt engineer specializing in GOOGLE LABS FLOW (ImageFX / Imagen model).
    Analyze the sketch image of {domain} and write a highly detailed, natural English description, then translate it into Vietnamese.

    CRITICAL INSTRUCTIONS FOR AI:
    1. AUTOMATIC CAMERA ANGLE: Carefully analyze the provided sketch image to determine the exact camera angle and perspective (e.g., strictly frontal flat elevation, 3/4 architectural perspective, bird's-eye view, eye-level wide angle). Incorporate this perspective into the description.
    2. OVERRIDE RULE: If the user provided extra notes, prioritize the user's note over the sketch line darkness/shadows. 
    3. FORMAT RULES: Write strictly in clear English natural sentences. DO NOT use Midjourney tags (--ar, --v), resolution buzzwords (8k, 16k, photorealistic), or render engine names.

    OUTPUT STRUCTURE REQUIREMENT:
    Return EXACTLY 2 sections separated by `===LANG_SPLIT===`:
    <English Paragraph>
    ===LANG_SPLIT===
    <Vietnamese Paragraph>
    
    The English paragraph MUST flow naturally combining:
    - Subject/Style
    - Materials/Colors
    - The AUTO-DETECTED Camera Angle
    - Lighting: "{clean_light}"
    - Environment: "{clean_context}"
    - Camera details: "Shot on Hasselblad H6D-100c, crisp surface textures. {film_instruction}"
    
    Do not include the < > brackets or any other labels. Just output the plain text paragraphs.
    """

    content_inputs = [system_instruction, sketch_img]
    if ref_img:
        content_inputs.append(ref_img)
    if extra_notes:
        content_inputs.append(f"USER MATERIAL/COLOR OVERRIDE NOTES: {extra_notes}")

    try:
        response = model.generate_content(content_inputs, safety_settings=safety_settings)
        result_text = response.text.strip()
    except Exception as e:
        return [f"Lỗi phản hồi từ AI: {str(e)}", ""]

    if not result_text:
        return ["AI trả về kết quả rỗng (Có thể do lỗi mạng hoặc ảnh không hợp lệ).", ""]

    if "===LANG_SPLIT===" in result_text:
        parts = result_text.split("===LANG_SPLIT===")
        en_prompt = clean_prompt_text(parts[0])
        vn_prompt = clean_prompt_text(parts[1]) if len(parts) > 1 else ""
        return [en_prompt, vn_prompt]
    else:
        return [clean_prompt_text(result_text), "⚠️ AI không tạo được phiên bản tiếng Việt phân tách rõ ràng."]


# KHỞI TẠO TABS VÀ SECRETS
tab_ext, tab_int = st.tabs(["🏛️ NGOẠI THẤT", "🛋️ NỘI THẤT"])
secret_api_key = st.secrets.get("GEMINI_API_KEY", "")


# ============================== TAB 1: NGOẠI THẤT ==============================
with tab_ext:
    # CÂN ĐỐI LẠI TỶ LỆ 3 CỘT CHO GỌN GÀNG VÀ CHUYÊN NGHIỆP
    col_left_e, col_main_e, col_right_e = st.columns([0.8, 1.8, 1.1], gap="large")

    with col_left_e:
        with st.expander("⚙️ Cấu hình API & Cài đặt (Ngoại thất)", expanded=True):
            api_label_ext = "Gemini API Key (✅ Đã kết nối Key hệ thống):" if secret_api_key else "Gemini API Key:"
            user_api_key_ext = st.text_input(api_label_ext, type="password", key="api_key_ext_input")
            api_key_ext = user_api_key_ext.strip() if user_api_key_ext.strip() else secret_api_key
            
            m_col1_e, m_col2_e = st.columns([0.85, 0.15])
            with m_col2_e:
                st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                fetch_btn_ext = st.button("🔄", key="fetch_models_ext", help="Tải danh sách Model tốt nhất từ Server", use_container_width=True)
                
            if fetch_btn_ext:
                if not api_key_ext:
                    st.error("Vui lòng nhập API Key trước!")
                else:
                    try:
                        genai.configure(api_key=api_key_ext)
                        fetched_models = []
                        for m in genai.list_models():
                            if 'generateContent' in m.supported_generation_methods:
                                name = m.name.replace("models/", "")
                                if ("pro" in name or "flash" in name) and not any(x in name for x in ["lite", "preview", "image", "omni", "nano"]):
                                    fetched_models.append(name)
                        if fetched_models:
                            fetched_models = sorted(list(set(fetched_models)), key=lambda x: ("pro" not in x, x))
                            st.session_state.api_models = fetched_models
                        else:
                            st.warning("API Key này không có model nào phù hợp.")
                    except Exception as e:
                        st.error(f"Lỗi: {e}")

            with m_col1_e:
                selected_model_ext = st.selectbox("Model AI:", st.session_state.api_models, key="model_ext")

            st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
            # DẸP BỎ MENU GÓC CAMERA, ĐỂ AI TỰ NHẬN DIỆN TỪ BẢN VẼ
            light_ext = st.selectbox("Kịch bản ánh sáng:", lighting_ext_options, index=3, key="light_ext")
            context_ext = st.selectbox("Bối cảnh môi trường:", context_ext_options, index=4, key="context_ext")
            film_ext = st.selectbox("Hiệu ứng màu sắc:", film_ext_options, index=1, key="film_ext")

    with col_main_e:
        st.markdown('<p class="custom-header-title">Kết quả Prompt Tối Ưu cho ImageFX</p>', unsafe_allow_html=True)
        main_placeholder_ext = st.empty()

    with col_right_e:
        with st.expander("🖼️ Tải ảnh phác thảo & Chỉ định màu", expanded=True):
            sketch_file_ext = st.file_uploader("Tải ảnh phác thảo Ngoại thất", type=["png", "jpg", "jpeg"], label_visibility="collapsed", key=f"sketch_up_ext_{st.session_state.uploader_key_ext}")
            sketch_img_ext = Image.open(io.BytesIO(sketch_file_ext.getvalue())) if sketch_file_ext else None
            if sketch_file_ext:
                render_clickable_image(file_bytes_to_b64(sketch_file_ext.getvalue()), "Ảnh phác thảo Ngoại thất", 0)

            ref_file_ext = st.file_uploader("Tải ảnh tham chiếu (Tùy chọn)", type=["png", "jpg", "jpeg"], label_visibility="collapsed", key=f"ref_up_ext_{st.session_state.uploader_key_ext}")
            ref_img_ext = Image.open(io.BytesIO(ref_file_ext.getvalue())) if ref_file_ext else None

            extra_notes_ext = st.text_area(
                "Ghi chú màu sắc / vật liệu ghi đè:",
                placeholder="Ví dụ: Tường sơn trắng, gỗ sồi sáng màu, mái bằng...",
                height=80,
                key=f"notes_ext_{st.session_state.uploader_key_ext}"
            )

            analyze_btn_ext = st.button("🚀 Phân tích & Tạo Prompt", type="primary", use_container_width=True, key="btn_anl_ext")

    # XỬ LÝ PHÂN TÍCH (KHÔNG DÙNG RERUN ĐỂ GIỮ NGUYÊN TAB)
    if analyze_btn_ext:
        if not api_key_ext:
            st.error("Vui lòng nhập API Key!")
        elif not sketch_file_ext:
            st.warning("Vui lòng tải lên ảnh phác thảo Ngoại thất!")
        else:
            with st.spinner("AI đang phân tích góc máy và vật liệu..."):
                try:
                    en_res, vi_res = process_gemini_analysis_bilingual(
                        api_key_ext, selected_model_ext, light_ext, context_ext, film_ext, sketch_img_ext, ref_img_ext, extra_notes_ext, is_interior=False
                    )
                    st.session_state.en_prompt_ext = en_res
                    st.session_state.vi_prompt_ext = vi_res
                    show_success_dog()
                except Exception as e:
                    st.error(f"Lỗi kết nối API: {str(e)}")

    with main_placeholder_ext.container():
        en_prompt_val_ext = st.session_state.en_prompt_ext if st.session_state.en_prompt_ext else "Đang chờ phân tích ảnh phác thảo..."
        render_prompt_card("🇺🇸 PHIÊN BẢN TIẾNG ANH (DÙNG ĐỂ TẠO ẢNH):", en_prompt_val_ext, "en_ext")
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        vi_prompt_val_ext = st.session_state.vi_prompt_ext if st.session_state.vi_prompt_ext else "Đang chờ bản dịch..."
        render_prompt_card("🇻🇳 PHIÊN BẢN TIẾNG VIỆT (ĐỂ THAM KHẢO):", vi_prompt_val_ext, "vi_ext")


# ============================== TAB 2: NỘI THẤT ==============================
with tab_int:
    col_left_i, col_main_i, col_right_i = st.columns([0.8, 1.8, 1.1], gap="medium")

    with col_left_i:
        with st.expander("⚙️ Cấu hình API & Cài đặt (Nội thất)", expanded=True):
            api_label_int = "Gemini API Key (✅ Đã kết nối Key hệ thống):" if secret_api_key else "Gemini API Key:"
            user_api_key_int = st.text_input(api_label_int, type="password", key="api_key_int_input")
            api_key_int = user_api_key_int.strip() if user_api_key_int.strip() else secret_api_key
            
            m_col1_i, m_col2_i = st.columns([0.85, 0.15])
            with m_col2_i:
                st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                fetch_btn_int = st.button("🔄", key="fetch_models_int", help="Tải danh sách Model tốt nhất", use_container_width=True)

            if fetch_btn_int:
                if not api_key_int:
                    st.error("Vui lòng nhập API Key trước!")
                else:
                    try:
                        genai.configure(api_key=api_key_int)
                        fetched_models = []
                        for m in genai.list_models():
                            if 'generateContent' in m.supported_generation_methods:
                                name = m.name.replace("models/", "")
                                if ("pro" in name or "flash" in name) and not any(x in name for x in ["lite", "preview", "image", "omni", "nano"]):
                                    fetched_models.append(name)
                        if fetched_models:
                            fetched_models = sorted(list(set(fetched_models)), key=lambda x: ("pro" not in x, x))
                            st.session_state.api_models = fetched_models
                        else:
                            st.warning("API Key này không có model nào phù hợp.")
                    except Exception as e:
                        st.error(f"Lỗi: {e}")

            with m_col1_i:
                selected_model_int = st.selectbox("Model AI:", st.session_state.api_models, key="model_int")

            st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
            light_int = st.selectbox("Kịch bản ánh sáng Nội thất:", lighting_int_options, index=4, key="light_int")
            context_int = st.selectbox("Bối cảnh môi trường:", context_int_options, index=0, key="context_int")
            film_int = st.selectbox("Hiệu ứng màu sắc:", film_int_options, index=1, key="film_int")

    with col_main_i:
        st.markdown('<p class="custom-header-title">Kết quả Prompt Tối Ưu cho ImageFX</p>', unsafe_allow_html=True)
        main_placeholder_int = st.empty()

    with col_right_i:
        with st.expander("🖼️ Tải ảnh phác thảo & Chỉ định màu", expanded=True):
            sketch_file_int = st.file_uploader("Tải ảnh phác thảo Nội thất", type=["png", "jpg", "jpeg"], label_visibility="collapsed", key=f"sketch_up_int_{st.session_state.uploader_key_int}")
            sketch_img_int = Image.open(io.BytesIO(sketch_file_int.getvalue())) if sketch_file_int else None
            if sketch_file_int:
                render_clickable_image(file_bytes_to_b64(sketch_file_int.getvalue()), "Ảnh phác thảo Nội thất", 2)

            ref_file_int = st.file_uploader("Tải ảnh tham chiếu Nội thất", type=["png", "jpg", "jpeg"], label_visibility="collapsed", key=f"ref_up_int_{st.session_state.uploader_key_int}")
            ref_img_int = Image.open(io.BytesIO(ref_file_int.getvalue())) if ref_file_int else None

            extra_notes_int = st.text_area(
                "Ghi chú màu sắc / vật liệu ghi đè:",
                placeholder="Ví dụ: Trần sơn trắng phẳng, sàn gỗ sồi sáng màu, sofa xám...",
                height=80,
                key=f"notes_int_{st.session_state.uploader_key_int}"
            )

            analyze_btn_int = st.button("🚀 Phân tích & Tạo Prompt", type="primary", use_container_width=True, key="btn_anl_int")

    if analyze_btn_int:
        if not api_key_int:
            st.error("Vui lòng nhập API Key!")
        elif not sketch_file_int:
            st.warning("Vui lòng tải lên ảnh phác thảo Nội thất!")
        else:
            with st.spinner("AI đang phân tích góc máy và vật liệu..."):
                try:
                    en_res, vi_res = process_gemini_analysis_bilingual(
                        api_key_int, selected_model_int, light_int, context_int, film_int, sketch_img_int, ref_img_int, extra_notes_int, is_interior=True
                    )
                    st.session_state.en_prompt_int = en_res
                    st.session_state.vi_prompt_int = vi_res
                    show_success_dog()
                except Exception as e:
                    st.error(f"Lỗi kết nối API: {str(e)}")

    with main_placeholder_int.container():
        en_prompt_val_int = st.session_state.en_prompt_int if st.session_state.en_prompt_int else "Đang chờ phân tích ảnh phác thảo..."
        render_prompt_card("🇺🇸 PHIÊN BẢN TIẾNG ANH (DÙNG ĐỂ TẠO ẢNH):", en_prompt_val_int, "en_int")
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        vi_prompt_val_int = st.session_state.vi_prompt_int if st.session_state.vi_prompt_int else "Đang chờ bản dịch..."
        render_prompt_card("🇻🇳 PHIÊN BẢN TIẾNG VIỆT (ĐỂ THAM KHẢO):", vi_prompt_val_int, "vi_int")
