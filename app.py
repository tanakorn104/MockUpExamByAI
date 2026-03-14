import streamlit as st
import json
import os
from google import genai
from google.genai import types
from docx import Document
import io

# ==========================================
# 0. การตั้งค่าและโหลด API Key
# ==========================================
def get_api_key():
    try:
        return st.secrets["GEMINI_API_KEY"]
    except:
        return os.getenv("GEMINI_API_KEY")

API_KEY = get_api_key()

# ==========================================
# 1. โหลดการตั้งค่าเว็บ
# ==========================================
def load_web_config():
    try:
        with open("web_config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "page_title": "ระบบเก็งข้อสอบ Computer Architecture",
            "welcome_message": "ยินดีต้อนรับสู่ระบบจำลองข้อสอบ (บทที่ 7-8)",
            "button_text": "🚀 เริ่มสุ่มสร้างข้อสอบชุดใหม่",
            "success_message": "สร้างข้อสอบสำเร็จ! ขอให้โชคดีในการทำ"
        }

config = load_web_config()
st.set_page_config(page_title=config.get("page_title"), page_icon="🎓")

if not API_KEY:
    st.error("❌ ไม่พบ API Key กรุณาตรวจสอบการตั้งค่า")
    st.stop()

client = genai.Client(api_key=API_KEY)

# ==========================================
# 2. ฟังก์ชันสร้างไฟล์ Word (Export)
# ==========================================
def create_docx(quiz_data, user_answers=None, include_answers=False):
    doc = Document()
    title = 'เฉลยและสรุปผลข้อสอบ' if include_answers else 'ใบงานข้อสอบจำลอง (Worksheet)'
    doc.add_heading(title, 0)
    
    if include_answers and user_answers:
        score = 0
        for i, q in enumerate(quiz_data):
            u_ans = str(user_answers.get(i, "")).strip().lower()
            correct_ans = str(q.get('a', '')).strip().lower()
            if u_ans == correct_ans and u_ans != "":
                score += 1
        doc.add_paragraph(f"คะแนนที่ทำได้: {score} / {len(quiz_data)} คะแนน")
        doc.add_paragraph("-" * 20)

    for i, q in enumerate(quiz_data):
        q_text = q.get('q', 'ไม่พบโจทย์')
        doc.add_heading(f"ข้อที่ {i+1}: {q_text}", level=1)
        
        q_type = str(q.get('type', 'unknown')).upper()
        if q_type == 'CHOICE':
            options = q.get('options', [])
            for opt in options:
                doc.add_paragraph(f"  [ ] {opt}")
        else:
            doc.add_paragraph("  ..................................................................")
        
        if include_answers:
            u_ans = user_answers.get(i, "ไม่ได้ตอบ") if user_answers else "N/A"
            doc.add_paragraph(f"คำตอบของคุณ: {u_ans}")
            doc.add_paragraph(f"เฉลย: {q.get('a')}", style='Intense Quote')
            doc.add_paragraph(f"คำอธิบาย: {q.get('detail')}")
        
        doc.add_paragraph("") # เว้นบรรทัด

    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()

# ==========================================
# 3. ฟังก์ชันเรียก AI เจนข้อสอบ
# ==========================================
def generate_quiz():
    try:
        with open("pre_processed_content.txt", "r", encoding="utf-8") as f:
            content = f.read()
        with open("instruction.txt", "r", encoding="utf-8") as f:
            final_instruction = f.read()

        response_schema = {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "type": {"type": "STRING"},
                    "q": {"type": "STRING"},
                    "options": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "a": {"type": "STRING"},
                    "detail": {"type": "STRING"}
                },
                "required": ["type", "q", "a", "detail"]
            }
        }

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"เนื้อหา:\n{content}",
            config=types.GenerateContentConfig(
                system_instruction=final_instruction,
                temperature=0.8,
                response_mime_type="application/json",
                response_schema=response_schema
            )
        )
        
        st.session_state.quiz_data = json.loads(response.text.strip(), strict=False)
        st.session_state.user_answers = {}
        st.session_state.app_mode = "quiz_running"
        return True
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาด: {e}")
        return False

# ==========================================
# 4. หน้าจอหลัก (UI)
# ==========================================
if "app_mode" not in st.session_state:
    st.session_state.app_mode = "start"

st.title(f"🎓 {config.get('page_title')}")

# --- หน้าแรก ---
if st.session_state.app_mode == "start":
    st.markdown(f"**{config.get('welcome_message')}**")
    if st.button(config.get('button_text'), use_container_width=True):
        with st.spinner("AI กำลังสร้างข้อสอบ..."):
            if generate_quiz():
                st.rerun()

# --- หน้าทำข้อสอบ ---
elif st.session_state.app_mode == "quiz_running":
    st.success(config.get('success_message'))
    
    # ปุ่มดาวน์โหลดใบงานก่อนทำ (วางไว้ด้านบนเพื่อให้เห็นชัดเจน)
    worksheet_data = create_docx(st.session_state.quiz_data, include_answers=False)
    st.download_button(
        label="📥 ดาวน์โหลดใบงาน (เฉพาะโจทย์) ไปฝึกทำในเครื่อง",
        data=worksheet_data,
        file_name="ComArch_Worksheet.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        use_container_width=True
    )
    st.divider()

    with st.form("exam_form"):
        temp_answers = {}
        for i, q in enumerate(st.session_state.quiz_data):
            st.markdown(f"**ข้อที่ {i+1}:** {q.get('q')}")
            q_type = str(q.get('type')).upper()
            
            if q_type == "CHOICE":
                temp_answers[i] = st.radio(f"คำตอบข้อ {i+1}", q.get('options', []), key=f"ans_{i}", index=None)
            else:
                temp_answers[i] = st.text_input(f"คำตอบข้อ {i+1}", key=f"ans_{i}", placeholder="พิมพ์คำตอบสั้นๆ...")
            st.write("") 

        if st.form_submit_button("📤 ส่งข้อสอบและตรวจคำตอบ", use_container_width=True):
            st.session_state.user_answers = temp_answers
            st.session_state.app_mode = "result"
            st.rerun()

# --- หน้าผลลัพธ์ ---
elif st.session_state.app_mode == "result":
    # คำนวณคะแนน
    score = sum(1 for i, q in enumerate(st.session_state.quiz_data) 
                if str(st.session_state.user_answers.get(i, "")).strip().lower() == str(q.get('a', '')).strip().lower())
    
    st.header(f"🎯 คะแนนของคุณ: {score} / {len(st.session_state.quiz_data)}")
    st.progress(score / len(st.session_state.quiz_data))

    for i, q in enumerate(st.session_state.quiz_data):
        u_ans = st.session_state.user_answers.get(i)
        is_correct = str(u_ans).strip().lower() == str(q.get('a')).strip().lower()
        
        with st.container(border=True):
            st.write(f"**ข้อที่ {i+1}:** {q.get('q')}")
            if is_correct:
                st.success(f"✅ ถูกต้อง! (คำตอบของคุณ: {u_ans})")
            else:
                st.error(f"❌ ผิด (คำตอบของคุณ: {u_ans})")
                st.write(f"**เฉลยที่ถูกต้อง:** {q.get('a')}")
            st.info(f"💡 **คำอธิบาย:** {q.get('detail')}")

    # ปุ่มดาวน์โหลดเฉลยและเริ่มใหม่
    col1, col2 = st.columns(2)
    with col1:
        result_data = create_docx(st.session_state.quiz_data, st.session_state.user_answers, include_answers=True)
        st.download_button("💾 ดาวน์โหลดเฉลยฉบับเต็ม", result_data, "Exam_Result.docx", use_container_width=True)
    with col2:
        if st.button("🔄 สุ่มสร้างชุดใหม่", use_container_width=True):
            st.session_state.app_mode = "start"
            st.rerun()