import base64
import html
import io
import os
import re
from PIL import Image
import google.generativeai as genai
import streamlit as st
import streamlit.components.v1 as components

# ================= CẤU HÌNH TRANG VÀ HIỆU NĂNG =================
st.set_page_config(page_title="KATO AI - Vision Prompt Generator", layout="wide")

PROHIBITED_PATTERNS = re.compile(
    r"--[a-z0-9]+|\b8k\b|\b16k\b|\bphotorealistic\b|\bhyperrealistic\b|\bcorona render\b|\bvray\b|\boctane render\b|\bunreal engine\b|\bmasterpiece\b",
    re.IGNORECASE
)

def clean_prompt_text(text: str) -> str:
    if not text: return ""
    cleaned = PROHIBITED_PATTERNS.sub("", text)
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    return "\n\n".join(lines).strip()

# ---------------- KHỞI TẠO STATE ----------------
if "prompts" not in st.session_state:
    st.session_state.prompts = {"ext": {"en": "", "vi": ""}, "int": {"en": "", "vi": ""}}

if "api_models" not in st.session_state:
    st.session_state.api_models = ["gemini-pro-latest", "gemini-flash-latest"]

# ---------------- TỐI ƯU HÌNH ẢNH ----------------
@st.cache_data(show_spinner=False, max_entries=10)
def optimize_image_for_api(file_bytes: bytes) -> Image.Image:
    try:
        img = Image.open(io.BytesIO(file_bytes))
        if img.mode != "RGB": img = img.convert("RGB")
        img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
        return img
    except Exception: return None

@st.cache_data(show_spinner=False, max_entries=20)
def optimize_image_for_ui_b64(file_bytes: bytes) -> str:
    try:
        img = Image.open(io.BytesIO(file_bytes))
        img.thumbnail((400, 400), Image.Resampling.LANCZOS)
        buffered = io.BytesIO()
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGBA")
            img.save(buffered, format="PNG", optimize=True)
        else:
            img = img.convert("RGB")
            img.save(buffered, format="JPEG", quality=75, optimize=True)
        return base64.b64encode(buffered.getvalue()).decode()
    except: return ""

@st.cache_resource(show_spinner=False)
def load_cached_dog_image():
    explicit_files = ["image_45819f.png", "image_45819f.jpg", "dog.png", "chihuahua.png"]
    target_file = next((f for f in explicit_files if os.path.exists(f)), None)
    if not target_file:
        for f in os.listdir("."):
            lower_f = f.lower()
            if lower_f.endswith((".png", ".jpg", ".jpeg")) and any(k in lower_f for k in ["458", "dog", "chihuahua"]):
                target_file = f
                break
    if not target_file: return ""
    try:
        img = Image.open(target_file).convert("RGBA")
        datas = img.getdata()
        new_data = [(0,0,0,0) if g > 100 and g > r*1.1 and g > b*1.1 else item for r,g,b,a in datas for item in [(r,g,b,a)]]
        img.putdata(new_data)
        buffered = io.BytesIO()
        img.thumbnail((300, 300))
        img.save(buffered, format="PNG", optimize=True)
        return base64.b64encode(buffered.getvalue()).decode()
    except: return ""

CACHED_DOG_B64 = load_cached_dog_image()

def show_success_dog():
    if not CACHED_DOG_B64: return
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

            var img = parentDoc.createElement('img'); img.src = "data:image/png;base64,{CACHED_DOG_B64}"; img.style.maxHeight = '200px'; img.style.margin = '0 auto 12px auto'; img.style.display = 'block'; card.appendChild(img);
            var txt = parentDoc.createElement('div'); txt.style.fontSize = '1.3rem'; txt.style.fontWeight = '800'; txt.style.color = '#28a745'; txt.innerText = 'ĐÃ TẠO XONG PROMPT TỐI ƯU!'; card.appendChild(txt);
            
            modal.appendChild(card); parentDoc.body.appendChild(modal);
            setTimeout(function() {{ if (modal && modal.parentNode) modal.parentNode.removeChild(modal); }}, 1800);
        }})();
        </script>
        """, height=0
    )

def render_clickable_image(img_b64, caption, uploader_index):
    dz_id = f"custom_dz_{uploader_index}"
    components.html(f"""
    <!DOCTYPE html>
    <html><head><style>
        body {{ margin: 0; background-color: transparent; font-family: sans-serif; }}
        .img-container {{ position: relative; width: 100%; height: 140px; cursor: pointer; border-radius: 12px; overflow: hidden; border: 1.5px solid #363945; transition: 0.25s; background-color: #1e1e24; display: flex; justify-content: center; align-items: center; box-sizing: border-box; }}
        .img-container:hover, .img-container.dragover {{ border-color: #28a745; box-shadow: 0 0 15px rgba(40,167,69,0.4); }}
        .img-container img {{ max-height: 130px; width: 100%; object-fit: contain; display: block; transition: opacity 0.2s; }}
        .img-container:hover img, .img-container.dragover img {{ opacity: 0.3; }}
        .overlay-text {{ position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); color: #fff; font-weight: 700; font-size: 0.85rem; background: rgba(38,39,48,0.95); padding: 8px 16px; border-radius: 20px; opacity: 0; transition: 0.25s; pointer-events: none; border: 1.5px solid #28a745; text-align: center; white-space: nowrap; }}
        .img-container:hover .overlay-text, .img-container.dragover .overlay-text {{ opacity: 1; }}
        .caption-text {{ text-align: center; color: #a0a0a0; font-size: 0.75rem; margin-top: 6px; font-weight: 600; text-transform: uppercase; }}
        .delete-btn {{
            position: absolute; top: 6px; right: 6px; background: rgba(0,0,0,0.7); color: #fff;
            border-radius: 50%; width: 28px; height: 28px; display: flex; justify-content: center; align-items: center;
            font-size: 14px; font-weight: bold; z-index: 10; transition: 0.2s; border: 1.5px solid rgba(255,255,255,0.3);
        }}
        .delete-btn:hover {{ background: #ff4b4b; border-color: #fff; transform: scale(1.1); color: white; }}
    </style></head>
    <body>
        <div class="img-container" id="{dz_id}">
            <div class="delete-btn" onclick="deleteImage(event)" title="Xóa ảnh này">✕</div>
            <img src="data:image/jpeg;base64,{img_b64}" />
            <div class="overlay-text">📷 Đổi ảnh (Nhấp / Kéo Thả)</div>
        </div>
        <div class="caption-text">{caption}</div>
        <script>
        const dz = document.getElementById('{dz_id}');
        function deleteImage(e) {{
            e.stopPropagation();
            try {{
                const targetUploader = window.parent.document.querySelectorAll('[data-testid="stFileUploader"]')[{uploader_index}];
                if(targetUploader) {{
                    const delBtn = targetUploader.querySelector('button[aria-label="Remove file"], [data-testid="stUploadedFile"] button');
                    if(delBtn) delBtn.click();
                }}
            }} catch(err) {{}}
        }}
        dz.addEventListener('click', () => {{
            try {{ window.parent.document.querySelectorAll('input[type=file]')[{uploader_index}].click(); }} catch(e) {{}}
        }});
        dz.addEventListener('dragover', (e) => {{ e.preventDefault(); dz.classList.add('dragover'); }});
        dz.addEventListener('dragleave', (e) => {{ e.preventDefault(); dz.classList.remove('dragover'); }});
        dz.addEventListener('drop', (e) => {{
            e.preventDefault(); dz.classList.remove('dragover');
            if(e.dataTransfer.files && e.dataTransfer.files.length > 0) {{
                try {{
                    const input = window.parent.document.querySelectorAll('input[type=file]')[{uploader_index}];
                    const dt = new DataTransfer(); dt.items.add(e.dataTransfer.files[0]);
                    input.files = dt.files;
                    input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                }} catch(err) {{}}
            }}
        }});
        </script>
    </body></html>
    """, height=180)

def render_prompt_card(title: str, text: str, box_id: str):
    escaped_text = html.escape(text) if text else ""
    components.html(f"""
    <!DOCTYPE html>
    <html><head><style>
        body {{ margin: 0; background-color: transparent; font-family: sans-serif; color: #e0e0e0; overflow: hidden; }}
        .header-row {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }}
        .title-text {{ font-weight: 700; color: #38bdf8; font-size: 0.9rem; letter-spacing: 0.5px; text-transform: uppercase; }}
        .copy-btn {{ background-color: #28a745; color: #fff; border: none; padding: 6px 14px; border-radius: 6px; cursor: pointer; font-size: 0.8rem; font-weight: 600; transition: 0.2s; outline: none; box-shadow: 0 2px 4px rgba(0,0,0,0.2); }}
        .copy-btn:hover {{ background-color: #218838; transform: translateY(-1px); }}
        .prompt-box {{ background-color: #1e1e24; border: 1px solid #363945; border-radius: 12px; padding: 1.2rem; height: 260px; overflow-y: auto; font-family: "Courier New", Courier, monospace; font-size: 0.95rem; line-height: 1.6; color: #7dd3fc; white-space: pre-wrap; word-break: break-word; box-shadow: inset 0 2px 5px rgba(0,0,0,0.2); }}
        .prompt-box::-webkit-scrollbar {{ width: 6px; }}
        .prompt-box::-webkit-scrollbar-track {{ background: #1e1e24; border-radius: 8px; }}
        .prompt-box::-webkit-scrollbar-thumb {{ background: #484c5a; border-radius: 8px; }}
    </style></head>
    <body>
        <div class="header-row">
            <span class="title-text">{title}</span>
            <button id="btn_{box_id}" class="copy-btn" onclick="copyText()">📋 COPY PROMPT</button>
        </div>
        <div id="text_{box_id}" class="prompt-box">{escaped_text}</div>
        <script>
        function copyText() {{
            var el = document.getElementById("text_{box_id}");
            var btn = document.getElementById("btn_{box_id}");
            if (!el) return;
            var text = el.innerText || el.textContent;
            var ok = () => {{ btn.innerHTML="✅ ĐÃ CHÉP!"; btn.style.backgroundColor="#d97706"; setTimeout(()=>{{btn.innerHTML="📋 COPY PROMPT"; btn.style.backgroundColor="#28a745";}},2000); }};
            navigator.clipboard.writeText(text).then(ok).catch(() => {{
                var ta = document.createElement("textarea"); ta.value = text; document.body.appendChild(ta); ta.select(); document.execCommand('copy'); document.body.removeChild(ta); ok();
            }});
        }}
        </script>
    </body></html>
    """, height=320)

# ================= CSS TỐI ƯU HÓA HOÀN TOÀN GIAO DIỆN UPLOAD =================
st.markdown("""
<style>
html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] { overflow-x: hidden !important; overflow-y: auto !important; }
div[data-testid="stHeader"] { display: none !important; }
section[data-testid="stSidebar"] { display: none !important; }
.block-container { padding: 2.5rem 1.5rem 1.0rem 1.5rem !important; max-width: 100% !important; }
div[data-baseweb="tab-list"] { z-index: 999999 !important; position: relative !important; }
button[data-baseweb="tab"] { font-size: 1.0rem !important; font-weight: 700 !important; padding: 0.4rem 1.5rem !important; border-radius: 8px 8px 0 0 !important; }
button[aria-selected="true"] { background-color: #262730 !important; color: #28a745 !important; border-bottom: 3px solid #28a745 !important; }
.custom-header-title { font-size: 1.2rem !important; font-weight: 700 !important; color: #ffffff !important; margin: 0 !important; line-height: 32px !important; }
button[kind="primary"] { background-color: #28a745 !important; color: #ffffff !important; border: none !important; height: 44px !important; border-radius: 8px !important; font-weight: 700 !important; font-size: 0.95rem !important; transition: 0.2s !important; }
button[kind="primary"]:hover { background-color: #218838 !important; transform: translateY(-2px); box-shadow: 0 4px 8px rgba(40,167,69,0.3); }
div[data-testid="stSelectbox"] label { font-size: 0.85rem !important; font-weight: 600 !important; color: #a0a0a0 !important;}

/* ---------------- TÙY CHỈNH KHUNG UPLOAD TRỐNG (GIỐNG ẢNH YÊU CẦU) ---------------- */
[data-testid="stFileUploadDropzone"] {
    background-color: transparent !important;
    border: 1.5px dashed #484c5a !important;
    border-radius: 12px !important;
    min-height: 130px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    transition: all 0.25s ease !important;
    padding: 0 !important;
}
[data-testid="stFileUploadDropzone"]:hover {
    border-color: #28a745 !important;
    background-color: rgba(40,167,69,0.05) !important;
    box-shadow: 0 0 15px rgba(40,167,69,0.2) !important;
}

/* Ẩn cục rườm rà mặc định (Đám mây, Chữ tiếng Anh, Limit 200MB...) */
[data-testid="stFileUploadDropzone"] > div > div {
    display: none !important;
}

/* Ghi đè chữ và icon mới chuyên nghiệp hơn */
[data-testid="stFileUploadDropzone"]::before {
    content: "🖼️\\000A Tải lên thiết kế";
    white-space: pre-wrap;
    text-align: center;
    color: #a0a0a0;
    font-size: 0.9rem;
    font-weight: 500;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    line-height: 2.2;
    pointer-events: none; /* Không chặn click chuột */
}

/* ---------------- ẨN THÔNG MINH KHUNG TẢI ẢNH KHI ĐÃ CÓ ẢNH ---------------- */
[data-testid="stFileUploader"]:has([data-testid="stUploadedFile"]) [data-testid="stFileUploadDropzone"] {
    display: none !important;
}
[data-testid="stUploadedFile"] {
    position: absolute !important;
    opacity: 0 !important;
    width: 1px !important;
    height: 1px !important;
    overflow: hidden !important;
    pointer-events: auto !important; 
    z-index: -100 !important;
    margin: 0 !important;
    padding: 0 !important;
}
</style>
""", unsafe_allow_html=True)


# ==================== DANH SÁCH TÙY CHỌN ====================
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


@st.cache_resource(show_spinner=False)
def get_cached_model(api_key: str, model_name: str):
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(f"models/{model_name}")

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_models(api_key):
    if not api_key: return []
    try:
        genai.configure(api_key=api_key)
        models = [m.name.replace("models/", "") for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        filtered = sorted(list(set([m for m in models if ("pro" in m or "flash" in m) and not any(x in m for x in ["lite", "preview", "image", "omni", "nano"])])), key=lambda x: ("pro" not in x, x))
        return filtered
    except:
        return []

def process_gemini_analysis_bilingual(
    api_key, model_display, light_opt, context_opt, film_opt, 
    sketch_img, ref_img, extra_notes, only_light_ref=False, is_interior=False
):
    model = get_cached_model(api_key, model_display)
    safety_settings = [{"category": c, "threshold": "BLOCK_NONE"} for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]

    domain = "INTERIOR ARCHITECTURE" if is_interior else "EXTERIOR ARCHITECTURE"
    clean_light = light_opt.split(" - ")[1] if " - " in light_opt else light_opt
    clean_context = context_opt.split(" - ")[1] if " - " in context_opt else context_opt
    clean_film = film_opt.split(" - ")[1] if " - " in film_opt else film_opt

    film_instruction = "Apply natural true-to-life colors without any film filter." if ("B0" in film_opt or "F0" in film_opt) else f"Apply {clean_film} photography style and color grading."

    ref_instruction = ""
    tag_requirement = "CRITICAL: You MUST explicitly include the exact text tag '@ảnh phác thảo' naturally within BOTH the English and Vietnamese paragraphs. Example: 'A modern architecture based on @ảnh phác thảo...'. DO NOT translate this tag."

    if ref_img:
        tag_requirement = "CRITICAL: You MUST explicitly include the exact text tags '@ảnh phác thảo' (for the first input image) and '@ảnh tham chiếu' (for the second input image) naturally within BOTH the English and Vietnamese paragraphs. DO NOT translate these tags."
        if only_light_ref:
            ref_instruction = """
            REFERENCE IMAGE INSTRUCTION (LIGHTING ONLY):
            Analyze the second provided image (Reference Image). Extract ONLY its lighting scenario, mood, and atmosphere.
            STRICTLY PRESERVE the geometric structure, material textures, and colors from the first image (Sketch Image).
            - English requirement: Explicitly use the tags "@ảnh phác thảo" for geometry/materials and "@ảnh tham chiếu" for lighting. Example: "The structure exactly matches @ảnh phác thảo, while the lighting mood follows @ảnh tham chiếu."
            """
        else:
            ref_instruction = """
            REFERENCE IMAGE INSTRUCTION (FULL BLEND):
            Analyze the second provided image. Extract its environmental context, lighting, and material/color palette. Apply these styles seamlessly onto the structural geometry of the first image.
            - English requirement: Explicitly use BOTH tags "@ảnh phác thảo" and "@ảnh tham chiếu" naturally. Example: "The geometric structure follows @ảnh phác thảo, inspired by the style and lighting of @ảnh tham chiếu."
            """

    system_instruction = f"""
    You are an expert architectural prompt engineer for GOOGLE LABS FLOW (Imagen model).
    Analyze the {domain} images and write a highly detailed, natural English description, then translate it into Vietnamese.

    CRITICAL INSTRUCTIONS:
    1. AUTOMATIC CAMERA ANGLE: Carefully analyze the first image (Sketch) to determine the exact camera angle (frontal flat elevation, 3/4 perspective, eye-level wide angle). Incorporate this perspective into the description.
    2. OVERRIDE RULE: If user provided extra notes, prioritize the user's note over the image details.
    {ref_instruction}
    3. FORMAT RULES: Write strictly in clear natural sentences. DO NOT use Midjourney tags or render engine names. DO NOT bold the @ tags.

    OUTPUT STRUCTURE REQUIREMENT:
    Return EXACTLY 2 sections separated by `===LANG_SPLIT===`:
    <English Paragraph>
    ===LANG_SPLIT===
    <Vietnamese Paragraph>
    
    The English paragraph MUST flow naturally combining: Subject/Style, Materials/Colors, The AUTO-DETECTED Camera Angle, Lighting: "{clean_light}", Environment: "{clean_context}", and Camera details: "Shot on Hasselblad H6D-100c. {film_instruction}"
    
    {tag_requirement}
    Make sure the Vietnamese paragraph is a precise translation and explicitly keeps the required tags ("@ảnh phác thảo", "@ảnh tham chiếu") un-translated.
    Do not include the < > brackets. Just output the plain text paragraphs.
    """

    content_inputs = [system_instruction, sketch_img]
    if ref_img: content_inputs.append(ref_img)
    if extra_notes: content_inputs.append(f"USER OVERRIDE NOTES: {extra_notes}")

    try:
        response = model.generate_content(content_inputs, safety_settings=safety_settings)
        res = response.text.strip()
        if "===LANG_SPLIT===" in res:
            parts = res.split("===LANG_SPLIT===")
            return clean_prompt_text(parts[0]), clean_prompt_text(parts[1]) if len(parts)>1 else ""
        return clean_prompt_text(res), "⚠️ AI không phân tách được tiếng Việt."
    except Exception as e: return f"Lỗi gọi API: {str(e)}", ""


# ==================== GIAO DIỆN CHÍNH ====================
tab_ext, tab_int = st.tabs(["🏛️ NGOẠI THẤT", "🛋️ NỘI THẤT"])
secret_api_key = st.secrets.get("GEMINI_API_KEY", "")


# -------------------- TAB 1: NGOẠI THẤT --------------------
with tab_ext:
    col_left_e, col_main_e, col_right_e = st.columns([0.8, 1.8, 1.1], gap="large")

    with col_left_e:
        with st.expander("⚙️ Cấu hình API & Cài đặt (Ngoại thất)", expanded=True):
            api_label_ext = "Gemini API Key (✅ Đã kết nối Key hệ thống):" if secret_api_key else "Gemini API Key:"
            user_api_key_ext = st.text_input(api_label_ext, type="password", key="api_key_ext_input")
            api_key_ext = user_api_key_ext.strip() if user_api_key_ext.strip() else secret_api_key
            
            m_col1_e, m_col2_e = st.columns([0.85, 0.15])
            with m_col2_e:
                st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                if st.button("🔄", key="fetch_models_ext", help="Tải danh sách Model tốt nhất từ Server", use_container_width=True):
                    fetched = fetch_models(api_key_ext)
                    if fetched: st.session_state.api_models = fetched
                    else: st.warning("Không tải được Model.")
            with m_col1_e:
                selected_model_ext = st.selectbox("Model AI:", st.session_state.api_models, key="model_ext")

            st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
            light_ext = st.selectbox("Kịch bản ánh sáng:", lighting_ext_options, index=3, key="light_ext")
            context_ext = st.selectbox("Bối cảnh môi trường:", context_ext_options, index=4, key="context_ext")
            film_ext = st.selectbox("Hiệu ứng màu sắc:", film_ext_options, index=1, key="film_ext")

    with col_main_e:
        st.markdown('<p class="custom-header-title">Kết quả Prompt Tối Ưu cho ImageFX</p>', unsafe_allow_html=True)
        main_placeholder_ext = st.empty() 

    with col_right_e:
        with st.expander("🖼️ Tải ảnh phác thảo & Tham chiếu", expanded=True):
            st.markdown("<p style='font-size: 0.85rem; font-weight: 600; color: #a0a0a0; margin-bottom: 5px;'>Ảnh phác thảo (Bắt buộc):</p>", unsafe_allow_html=True)

            sketch_preview_ext_ph = st.empty()
            sketch_file_ext = st.file_uploader("Tải ảnh phác thảo Ngoại thất", type=["png", "jpg", "jpeg", "webp"], label_visibility="collapsed", key="s_up_ext")
            sketch_img_ext = None
            if sketch_file_ext:
                sketch_img_ext = optimize_image_for_api(sketch_file_ext.getvalue())
                with sketch_preview_ext_ph.container():
                    render_clickable_image(optimize_image_for_ui_b64(sketch_file_ext.getvalue()), "Ảnh phác thảo Ngoại thất", 0)

            st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
            
            r_col1_e, r_col2_e = st.columns([0.65, 0.35], vertical_alignment="bottom")
            with r_col1_e:
                st.markdown("<p style='font-size: 0.85rem; font-weight: 600; color: #a0a0a0; margin-bottom: 5px;'>Ảnh tham chiếu (Tùy chọn):</p>", unsafe_allow_html=True)
            with r_col2_e:
                only_light_ref_ext = st.checkbox("Chỉ lấy sáng", value=False, key="light_ref_ext", help="Chỉ mượn ánh sáng và nhiệt độ màu của ảnh này")
                
            ref_preview_ext_ph = st.empty()
            ref_file_ext = st.file_uploader("Tải ảnh tham chiếu Ngoại thất", type=["png", "jpg", "jpeg", "webp"], label_visibility="collapsed", key="r_up_ext")
            ref_img_ext = optimize_image_for_api(ref_file_ext.getvalue()) if ref_file_ext else None
            if ref_file_ext:
                with ref_preview_ext_ph.container():
                    render_clickable_image(optimize_image_for_ui_b64(ref_file_ext.getvalue()), "Ảnh tham chiếu Ngoại thất", 1)

            st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
            extra_notes_ext = st.text_area("Ghi chú màu sắc / vật liệu ghi đè:", placeholder="Ví dụ: Tường sơn trắng, gỗ sồi sáng màu, mái bằng...", height=80, key="n_ext")

            analyze_btn_ext = st.button("🚀 Phân tích & Tạo Prompt", type="primary", use_container_width=True, key="btn_anl_ext")

    if analyze_btn_ext:
        if not api_key_ext: st.error("Vui lòng nhập API Key!")
        elif not sketch_img_ext: st.warning("Vui lòng tải lên ảnh phác thảo Ngoại thất!")
        else:
            with st.spinner("AI đang phân tích góc máy và vật liệu..."):
                en_res, vi_res = process_gemini_analysis_bilingual(
                    api_key_ext, selected_model_ext, light_ext, context_ext, film_ext, 
                    sketch_img_ext, ref_img_ext, extra_notes_ext, 
                    only_light_ref_ext, is_interior=False
                )
                st.session_state.prompts["ext"]["en"] = en_res
                st.session_state.prompts["ext"]["vi"] = vi_res
                show_success_dog()

    with main_placeholder_ext.container():
        render_prompt_card("🇺🇸 BẢN TIẾNG ANH (DÙNG ĐỂ TẠO ẢNH):", st.session_state.prompts["ext"]["en"] or "Đang chờ phân tích...", "en_ext")
        st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)
        render_prompt_card("🇻🇳 BẢN TIẾNG VIỆT (ĐỂ THAM KHẢO):", st.session_state.prompts["ext"]["vi"] or "Đang chờ bản dịch...", "vi_ext")


# -------------------- TAB 2: NỘI THẤT --------------------
with tab_int:
    col_left_i, col_main_i, col_right_i = st.columns([0.8, 1.8, 1.1], gap="large")

    with col_left_i:
        with st.expander("⚙️ Cấu hình API & Cài đặt (Nội thất)", expanded=True):
            api_label_int = "Gemini API Key (✅ Đã kết nối Key hệ thống):" if secret_api_key else "Gemini API Key:"
            user_api_key_int = st.text_input(api_label_int, type="password", key="api_key_int_input")
            api_key_int = user_api_key_int.strip() if user_api_key_int.strip() else secret_api_key
            
            m_col1_i, m_col2_i = st.columns([0.85, 0.15])
            with m_col2_i:
                st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                if st.button("🔄", key="fetch_models_int", help="Tải danh sách Model tốt nhất", use_container_width=True):
                    fetched = fetch_models(api_key_int)
                    if fetched: st.session_state.api_models = fetched
                    else: st.warning("Không tải được Model.")
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
        with st.expander("🖼️ Tải ảnh phác thảo & Tham chiếu", expanded=True):
            st.markdown("<p style='font-size: 0.85rem; font-weight: 600; color: #a0a0a0; margin-bottom: 5px;'>Ảnh phác thảo (Bắt buộc):</p>", unsafe_allow_html=True)

            sketch_preview_int_ph = st.empty()
            sketch_file_int = st.file_uploader("Tải ảnh phác thảo Nội thất", type=["png", "jpg", "jpeg", "webp"], label_visibility="collapsed", key="s_up_int")
            sketch_img_int = None
            if sketch_file_int:
                sketch_img_int = optimize_image_for_api(sketch_file_int.getvalue())
                with sketch_preview_int_ph.container():
                    render_clickable_image(optimize_image_for_ui_b64(sketch_file_int.getvalue()), "Ảnh phác thảo Nội thất", 2)

            st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
            
            r_col1_i, r_col2_i = st.columns([0.65, 0.35], vertical_alignment="bottom")
            with r_col1_i:
                st.markdown("<p style='font-size: 0.85rem; font-weight: 600; color: #a0a0a0; margin-bottom: 5px;'>Ảnh tham chiếu (Tùy chọn):</p>", unsafe_allow_html=True)
            with r_col2_i:
                only_light_ref_int = st.checkbox("Chỉ lấy sáng", value=False, key="light_ref_int", help="Chỉ mượn ánh sáng và nhiệt độ màu của ảnh này")

            ref_preview_int_ph = st.empty()
            ref_file_int = st.file_uploader("Tải ảnh tham chiếu Nội thất", type=["png", "jpg", "jpeg", "webp"], label_visibility="collapsed", key="r_up_int")
            ref_img_int = optimize_image_for_api(ref_file_int.getvalue()) if ref_file_int else None
            if ref_file_int:
                with ref_preview_int_ph.container():
                    render_clickable_image(optimize_image_for_ui_b64(ref_file_int.getvalue()), "Ảnh tham chiếu Nội thất", 3)

            st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
            extra_notes_int = st.text_area("Ghi chú màu sắc / vật liệu ghi đè:", placeholder="Ví dụ: Trần sơn trắng phẳng, sàn gỗ sồi...", height=80, key="n_int")

            analyze_btn_int = st.button("🚀 Phân tích & Tạo Prompt", type="primary", use_container_width=True, key="btn_anl_int")

    if analyze_btn_int:
        if not api_key_int: st.error("Vui lòng nhập API Key!")
        elif not sketch_img_int: st.warning("Vui lòng tải lên ảnh phác thảo Nội thất!")
        else:
            with st.spinner("AI đang phân tích góc máy, vật liệu và ánh sáng (Vui lòng chờ)..."):
                try:
                    en_res, vi_res = process_gemini_analysis_bilingual(
                        api_key_int, selected_model_int, light_int, context_int, film_int, 
                        sketch_img_int, ref_img_int, extra_notes_int, 
                        only_light_ref_int, is_interior=True
                    )
                    st.session_state.prompts["int"]["en"] = en_res
                    st.session_state.prompts["int"]["vi"] = vi_res
                    show_success_dog()
                except Exception as e:
                    st.error(f"Lỗi kết nối API: {str(e)}")

    with main_placeholder_int.container():
        render_prompt_card("🇺🇸 BẢN TIẾNG ANH (DÙNG ĐỂ TẠO ẢNH):", st.session_state.prompts["int"]["en"] or "Đang chờ phân tích...", "en_int")
        st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)
        render_prompt_card("🇻🇳 BẢN TIẾNG VIỆT (ĐỂ THAM KHẢO):", st.session_state.prompts["int"]["vi"] or "Đang chờ bản dịch...", "vi_int")
