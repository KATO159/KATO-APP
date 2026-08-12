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
st.set_page_config(page_title="KATO AI - Vision Prompt Generator (Google Labs Edition)", layout="wide")

# Khởi tạo session_state cho 4 ô kết quả Ngoại thất và Nội thất
for key in ["ext_box1", "ext_box2", "ext_box3", "ext_box4", "int_box1", "int_box2", "int_box3", "int_box4"]:
    if key not in st.session_state:
        st.session_state[key] = ""

if "uploader_key_ext" not in st.session_state:
    st.session_state.uploader_key_ext = 0
if "uploader_key_int" not in st.session_state:
    st.session_state.uploader_key_int = 0
if "show_dog_modal" not in st.session_state:
    st.session_state.show_dog_modal = False


# Hàm làm sạch văn bản & xóa từ khóa cấm nhiễu của Imagen
def clean_prompt_text(text: str) -> str:
    if not text:
        return ""
    prohibited_patterns = [
        r"--[a-z0-9]+",
        r"\b8k\b",
        r"\b16k\b",
        r"\bphotorealistic\b",
        r"\bhyperrealistic\b",
        r"\bcorona render\b",
        r"\bvray\b",
        r"\boctane render\b",
        r"\bunreal engine\b",
        r"\bmasterpiece\b"
    ]
    cleaned = text
    for pattern in prohibited_patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip()


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


# CSS GIAO DIỆN HỆ THỐNG
st.markdown(
    """
<style>
html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
    overflow-x: hidden !important;
    overflow-y: auto !important;
}
div[data-testid="stHeader"] { display: none !important; }
section[data-testid="stSidebar"] { display: none !important; }

.block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 1.0rem !important;
    padding-left: 0.8rem !important;
    padding-right: 0.8rem !important;
    max-width: 100% !important;
}

button[data-baseweb="tab"] {
    font-size: 1.0rem !important;
    font-weight: 700 !important;
    padding: 0.4rem 1.5rem !important;
}
button[aria-selected="true"] {
    background-color: #262730 !important;
    color: #28a745 !important;
    border-bottom: 3px solid #28a745 !important;
}

.custom-header-title { font-size: 1.2rem !important; font-weight: 700 !important; color: #ffffff !important; margin: 0 !important; }

div[data-testid="stTextArea"] textarea {
    background-color: #1e1e24 !important;
    color: #7dd3fc !important;
    font-family: monospace, Consolas, "Courier New" !important;
    font-size: 0.85rem !important;
    border: 1px solid #363945 !important;
    border-radius: 6px !important;
}

button[kind="primary"] { background-color: #28a745 !important; color: #ffffff !important; font-weight: 600 !important; }
button[kind="primary"]:hover { background-color: #218838 !important; }
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

# DANH SÁCH TÙY CHỌN ÁNH SÁNG & BỐI CẢNH
lighting_ext_options = [
    "Bright early morning sunlight with soft warm shadows",
    "High noon direct sunlight with sharp geometric shadows",
    "Overcast diffused daylight highlighting natural material textures",
    "Warm golden hour sunset with long dramatic outdoor shadows",
    "Twilight blue hour with warm facade accent lights turned on",
    "Moody night landscape with outdoor spotlights"
]

lighting_int_options = [
    "Soft morning sunlight streaming through floor-to-ceiling sheer curtains",
    "High noon bright natural daylight filling the entire room",
    "Volumetric sunlight beams filtering through window blinds",
    "Cozy evening ambient lighting with warm 3000K recessed spots",
    "Neutral 4000K daylight creating a crisp minimalist ambiance",
    "Concealed cove LED lighting combined with sleek magnetic track lights"
]


# HÀM XỬ LÝ GỌI API GEMINI (TÁCH 4 BỐC PROMPT TIẾNG ANH)
def process_gemini_analysis_split(
    api_key,
    selected_model,
    lighting_opt,
    sketch_img,
    ref_img,
    extra_notes,
    is_interior=False,
):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(selected_model)

    domain = "INTERIOR ARCHITECTURE" if is_interior else "EXTERIOR ARCHITECTURE"

    system_instruction = f"""
    You are an expert architectural prompt engineer specializing in GOOGLE LABS FLOW (ImageFX / Imagen model).
    Analyze the sketch image of {domain} and write a 4-part natural English description.

    CRITICAL OVERRIDE RULE FOR USER NOTES:
    - If the user provided extra notes (e.g. "flat white ceiling", "oak wood floor"), prioritize the user's note over the sketch line darkness/shadows. Ignore darkness in the sketch lines that could be misread as gray material.

    FORMAT RULES FOR GOOGLE LABS (IMAGEFX):
    - Write strictly in clear English natural sentences.
    - DO NOT use Midjourney tags (--ar, --v), resolution buzzwords (8k, 16k, photorealistic), or render engine names (Corona, Vray).
    - Lock camera angle and scale based on the provided sketch.

    OUTPUT STRUCTURE REQUIREMENT:
    Return EXACTLY 4 sections separated by `===SECTION_SPLIT===`:
    Section 1 (Subject & Style): A sentence starting with "A professional architectural photograph of a..." describing space type and style.
    Section 2 (Materials & Colors): A sentence starting with "The space features..." listing exact materials and colors (honoring user notes).
    Section 3 (Lighting & Environment): A sentence describing the lighting: "{lighting_opt}".
    Section 4 (Camera Specs & Depth): A sentence describing camera technique: "Shot on Hasselblad H6D-100c, wide-angle lens, straight vertical lines, eye-level view, crisp surface textures."
    """

    content_inputs = [system_instruction, sketch_img]
    if ref_img:
        content_inputs.append(ref_img)
    if extra_notes:
        content_inputs.append(f"USER MATERIAL/COLOR OVERRIDE NOTES: {extra_notes}")

    response = model.generate_content(content_inputs)
    result_text = response.text.strip()

    if "===SECTION_SPLIT===" in result_text:
        parts = result_text.split("===SECTION_SPLIT===")
        return [clean_prompt_text(p) for p in parts[:4]]
    else:
        # Fallback phân tách theo câu nếu AI thiếu cờ phân cách
        sentences = [clean_prompt_text(s) for s in result_text.split(".") if s.strip()]
        while len(sentences) < 4:
            sentences.append("")
        return sentences[:4]


# KHỞI TẠO TABS
tab_ext, tab_int = st.tabs(["🏛️ NGOẠI THẤT", "🛋️ NỘI THẤT"])
secret_api_key = st.secrets.get("GEMINI_API_KEY", "")


# -------------------- TAB 1: NGOẠI THẤT --------------------
with tab_ext:
    col_left_e, col_main_e, col_right_e = st.columns([1.0, 1.5, 1.0], gap="medium")

    with col_left_e:
        with st.expander("⚙️ Cấu hình API & Cài đặt (Ngoại thất)", expanded=True):
            user_api_key_ext = st.text_input("Gemini API Key:", type="password", key="api_key_ext_input")
            api_key_ext = user_api_key_ext.strip() if user_api_key_ext.strip() else secret_api_key
            selected_model_ext = st.selectbox("Model AI:", ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash"], key="model_ext")
            light_ext = st.selectbox("Kịch bản ánh sáng:", lighting_ext_options, index=0, key="light_ext")

    with col_main_e:
        st.markdown('<p class="custom-header-title">Kết quả Prompt Tách 4 Ô (Tối ưu cho ImageFX)</p>', unsafe_allow_html=True)
        
        # 4 ô Textarea chỉnh sửa riêng biệt
        b1_ext = st.text_area("1. Phong cách & Không gian (Box 1):", value=st.session_state.ext_box1, height=65, key="box1_ext")
        b2_ext = st.text_area("2. Chi tiết Vật liệu & Màu sắc (Box 2 - Dễ sửa nhất):", value=st.session_state.ext_box2, height=85, key="box2_ext")
        
        # Thẻ Preset chọn nhanh vật liệu bổ sung cho Box 2 Ngoại thất
        st.caption("✨ **Thẻ chọn nhanh vật liệu (Bấm để chèn vào Box 2):**")
        tag_cols_e = st.columns(4)
        if tag_cols_e[0].button("+ Gỗ ốp mặt tiền", key="tag_e1"):
            st.session_state.ext_box2 += ", slatted timber facade cladding"
            st.rerun()
        if tag_cols_e[1].button("+ Bê tông mài", key="tag_e2"):
            st.session_state.ext_box2 += ", polished concrete panels"
            st.rerun()
        if tag_cols_e[2].button("+ Cửa kính khung đen", key="tag_e3"):
            st.session_state.ext_box2 += ", black metal frame glass doors"
            st.rerun()
        if tag_cols_e[3].button("+ Đá ốp tự nhiên", key="tag_e4"):
            st.session_state.ext_box2 += ", natural stone veneer wall"
            st.rerun()

        b3_ext = st.text_area("3. Ánh sáng & Bối cảnh (Box 3):", value=st.session_state.ext_box3, height=65, key="box3_ext")
        b4_ext = st.text_area("4. Thông số Nhiếp ảnh & Chất lượng (Box 4):", value=st.session_state.ext_box4, height=65, key="box4_ext")

        # Nút Ghép chuỗi & Sao chép prompt hoàn chỉnh
        full_ext_prompt = f"{b1_ext} {b2_ext} {b3_ext} {b4_ext}".strip()
        if st.button("📋 SAO CHÉP PROMPT HOÀN CHỈNH (Nối 4 ô)", type="primary", use_container_width=True, key="copy_ext"):
            st.write("Đã sẵn sàng dán vào Google Labs Flow:")
            st.code(full_ext_prompt, language="text")

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

            analyze_btn_ext = st.button("Phân tích & Tạo 4 Ô Prompt", type="primary", use_container_width=True, key="btn_anl_ext")

    if analyze_btn_ext:
        if not api_key_ext:
            st.error("Vui lòng nhập API Key!")
        elif not sketch_file_ext:
            st.warning("Vui lòng tải lên ảnh phác thảo Ngoại thất!")
        else:
            try:
                boxes = process_gemini_analysis_split(
                    api_key_ext, selected_model_ext, light_ext, sketch_img_ext, ref_img_ext, extra_notes_ext, is_interior=False
                )
                st.session_state.ext_box1 = boxes[0]
                st.session_state.ext_box2 = boxes[1]
                st.session_state.ext_box3 = boxes[2]
                st.session_state.ext_box4 = boxes[3]
                st.session_state.show_dog_modal = True
                st.rerun()
            except Exception as e:
                st.error(f"Lỗi kết nối API: {str(e)}")


# -------------------- TAB 2: NỘI THẤT --------------------
with tab_int:
    col_left_i, col_main_i, col_right_i = st.columns([1.0, 1.5, 1.0], gap="medium")

    with col_left_i:
        with st.expander("⚙️ Cấu hình API & Cài đặt (Nội thất)", expanded=True):
            user_api_key_int = st.text_input("Gemini API Key:", type="password", key="api_key_int_input")
            api_key_int = user_api_key_int.strip() if user_api_key_int.strip() else secret_api_key
            selected_model_int = st.selectbox("Model AI:", ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash"], key="model_int")
            light_int = st.selectbox("Kịch bản ánh sáng Nội thất:", lighting_int_options, index=0, key="light_int")

    with col_main_i:
        st.markdown('<p class="custom-header-title">Kết quả Prompt Tách 4 Ô (Tối ưu cho ImageFX)</p>', unsafe_allow_html=True)
        
        b1_int = st.text_area("1. Phong cách & Không gian (Box 1):", value=st.session_state.int_box1, height=65, key="box1_int")
        b2_int = st.text_area("2. Chi tiết Vật liệu & Màu sắc (Box 2 - Dễ sửa nhất):", value=st.session_state.int_box2, height=85, key="box2_int")
        
        # Thẻ Preset chọn nhanh vật liệu bổ sung cho Box 2 Nội thất
        st.caption("✨ **Thẻ chọn nhanh vật liệu (Bấm để chèn vào Box 2):**")
        tag_cols_i = st.columns(4)
        if tag_cols_i[0].button("+ Trần sơn trắng", key="tag_i1"):
            st.session_state.int_box2 += ", flat smooth white painted ceiling"
            st.rerun()
        if tag_cols_i[1].button("+ Sàn gỗ Sồi", key="tag_i2"):
            st.session_state.int_box2 += ", light oak timber floor"
            st.rerun()
        if tag_cols_i[2].button("+ Sofa da Cognac", key="tag_i3"):
            st.session_state.int_box2 += ", plush cognac leather sofa"
            st.rerun()
        if tag_cols_i[3].button("+ Lam gỗ Óc chó", key="tag_i4"):
            st.session_state.int_box2 += ", slatted walnut wood wall panels"
            st.rerun()

        b3_int = st.text_area("3. Ánh sáng & Bối cảnh (Box 3):", value=st.session_state.int_box3, height=65, key="box3_int")
        b4_int = st.text_area("4. Thông số Nhiếp ảnh & Chất lượng (Box 4):", value=st.session_state.int_box4, height=65, key="box4_int")

        full_int_prompt = f"{b1_int} {b2_int} {b3_int} {b4_int}".strip()
        if st.button("📋 SAO CHÉP PROMPT HOÀN CHỈNH (Nối 4 ô)", type="primary", use_container_width=True, key="copy_int"):
            st.write("Đã sẵn sàng dán vào Google Labs Flow:")
            st.code(full_int_prompt, language="text")

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

            analyze_btn_int = st.button("Phân tích & Tạo 4 Ô Prompt", type="primary", use_container_width=True, key="btn_anl_int")

    if analyze_btn_int:
        if not api_key_int:
            st.error("Vui lòng nhập API Key!")
        elif not sketch_file_int:
            st.warning("Vui lòng tải lên ảnh phác thảo Nội thất!")
        else:
            try:
                boxes = process_gemini_analysis_split(
                    api_key_int, selected_model_int, light_int, sketch_img_int, ref_img_int, extra_notes_int, is_interior=True
                )
                st.session_state.int_box1 = boxes[0]
                st.session_state.int_box2 = boxes[1]
                st.session_state.int_box3 = boxes[2]
                st.session_state.int_box4 = boxes[3]
                st.session_state.show_dog_modal = True
                st.rerun()
            except Exception as e:
                st.error(f"Lỗi kết nối API: {str(e)}")
