import streamlit as st
import json
import os
import base64
import hashlib
import io
import datetime
from docx import Document
from google import genai
from google.genai import types
from streamlit_javascript import st_javascript

# ==========================================
# 0. การตั้งค่าและโหลด API Key
# ==========================================
def get_api_key():
    try:
        return st.secrets["GEMINI_API_KEY"]
    except:
        return os.getenv("GEMINI_API_KEY", "")

API_KEY = get_api_key()

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
# 1. ระบบจัดการ Session & Local Storage Sync
# ==========================================
if "exam_history" not in st.session_state:
    st.session_state.exam_history = []
if "app_mode" not in st.session_state:
    st.session_state.app_mode = "start"
if "quiz_data" not in st.session_state:
    st.session_state.quiz_data = None
if "user_answers" not in st.session_state:
    st.session_state.user_answers = {}
if "ls_synced" not in st.session_state:
    st.session_state.ls_synced = False

# โหลดข้อมูลจาก Local Storage ตอนเริ่มแอป
if not st.session_state.ls_synced:
    ls_data = st_javascript("localStorage.getItem('comarch_v5');", key="load_ls")
    if ls_data and ls_data != 0 and ls_data != "null":
        try:
            stored = json.loads(ls_data)
            st.session_state.app_mode = stored.get("app_mode", "start")
            st.session_state.quiz_data = stored.get("quiz_data")
            raw_ans = stored.get("user_answers", {})
            st.session_state.user_answers = {int(k) if k.isdigit() else k: v for k, v in raw_ans.items()}
            st.session_state.exam_history = stored.get("exam_history", [])
            st.session_state.ls_synced = True
            st.rerun()
        except:
            st.session_state.ls_synced = True
    elif ls_data == "null" or (ls_data is not None and ls_data != 0):
        st.session_state.ls_synced = True

# ==========================================
# 2. ฟังก์ชันจัดการไฟล์ Word
# ==========================================
def create_docx(quiz_data=None, user_answers=None, mode="worksheet", history_data=None):
    doc = Document()
    
    if mode == "worksheet":
        doc.add_heading('ใบงานข้อสอบจำลอง (Worksheet)', 0)
        for i, q in enumerate(quiz_data):
            doc.add_heading(f"ข้อที่ {i+1}: {q.get('q', 'ไม่พบโจทย์')}", level=1)
            if str(q.get('type')).upper() == 'CHOICE':
                for opt in q.get('options', []):
                    doc.add_paragraph(f"  [ ] {opt}")
            else:
                doc.add_paragraph("  ..................................................................")
            doc.add_paragraph("")
        doc.add_page_break()
        doc.add_heading('เฉลยข้อสอบ (Answer Key)', 0)
        for i, q in enumerate(quiz_data):
            doc.add_heading(f"ข้อที่ {i+1}: {q.get('q', '')}", level=2)
            doc.add_paragraph(f"เฉลย: {q.get('a', '')}", style='Intense Quote')
            doc.add_paragraph(f"คำอธิบาย: {q.get('detail', '')}")
            doc.add_paragraph("-" * 20)

    elif mode == "result":
        doc.add_heading('สรุปผลข้อสอบ', 0)
        score = sum(1 for i, q in enumerate(quiz_data) if str(user_answers.get(i, "")).strip().lower() == str(q.get('a', '')).strip().lower() and str(user_answers.get(i, "")).strip() != "")
        doc.add_paragraph(f"คะแนนที่ทำได้: {score} / {len(quiz_data)} คะแนน")
        for i, q in enumerate(quiz_data):
            doc.add_heading(f"ข้อที่ {i+1}: {q.get('q', '')}", level=1)
            doc.add_paragraph(f"คำตอบของคุณ: {user_answers.get(i, 'ไม่ได้ตอบ')}")
            doc.add_paragraph(f"เฉลย: {q.get('a', '')}", style='Intense Quote')
            doc.add_paragraph(f"คำอธิบาย: {q.get('detail', '')}")
            doc.add_paragraph("-" * 20)

    elif mode == "history":
        doc.add_heading('ประวัติการทำข้อสอบทั้งหมด (Exam History)', 0)
        doc.add_paragraph(f"วันที่พิมพ์เอกสาร: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        for idx, record in enumerate(history_data):
            doc.add_heading(f"ชุดข้อสอบที่ {idx+1} | คะแนน: {record['score']} / {record['total']}", level=1)
            for i, q in enumerate(record['quiz_data']):
                u_ans = record['user_answers'].get(str(i), record['user_answers'].get(i, 'ไม่ได้ตอบ'))
                doc.add_paragraph(f"ข้อ {i+1}: {q.get('q', '')} | ตอบ: {u_ans} | เฉลย: {q.get('a', '')}")
            doc.add_page_break()

    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()

# ==========================================
# 3. ฟังก์ชันเรียก AI เจนข้อสอบ (ใช้ Gemma 3 12B)
# ==========================================
def generate_quiz():
    try:
        with open("pre_processed_content.txt", "r", encoding="utf-8") as f:
            content = f.read()
        with open("instruction.txt", "r", encoding="utf-8") as f:
            final_instruction = f.read()

        # Gemma 3 ไม่รองรับ system_instruction พารามิเตอร์ 
        # จึงต้องนำ instruction ไปรวมไว้ใน contents แทน
        full_prompt = f"{final_instruction}\n\nเนื้อหาสำหรับออกข้อสอบ:\n{content}"

        response = client.models.generate_content(
            model='gemma-3-12b-it',
            contents=full_prompt,
            config=types.GenerateContentConfig(
                temperature=0.8,
                response_mime_type="application/json",
                response_schema={
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
# 4. แถบเมนูด้านข้าง (Sidebar)
# ==========================================
with st.sidebar:
    st.header("📂 เก็บประวัติลงเครื่อง")
    if len(st.session_state.exam_history) > 0:
        st.success(f"ทำไปแล้ว {len(st.session_state.exam_history)} ชุด")
        h_docx = create_docx(mode="history", history_data=st.session_state.exam_history)
        st.download_button("💾 โหลดประวัติทั้งหมด (Word)", h_docx, "History.docx", use_container_width=True)
        if st.button("🗑️ ล้างข้อมูลเบราว์เซอร์", use_container_width=True):
            st_javascript("localStorage.removeItem('comarch_v5');")
            st.session_state.exam_history = []
            st.session_state.app_mode = "start"
            st.rerun()

# ==========================================
# 5. หน้าจอหลัก (UI)
# ==========================================
st.title(f"🎓 {config.get('page_title')}")

if st.session_state.app_mode == "start":
    st.markdown(f"**{config.get('welcome_message')}**")
    if st.button(config.get('button_text'), use_container_width=True):
        with st.spinner("🧠 Gemma 3 12B กำลังสร้างข้อสอบ..."):
            if generate_quiz(): st.rerun()

elif st.session_state.app_mode == "quiz_running":
    st.success(config.get('success_message'))
    ws_data = create_docx(quiz_data=st.session_state.quiz_data, mode="worksheet")
    st.download_button("📥 โหลดใบงาน (โจทย์+เฉลยหน้าหลัง)", ws_data, "Worksheet.docx", use_container_width=True)
    st.divider()

    with st.form("exam_form"):
        temp_answers = {}
        for i, q in enumerate(st.session_state.quiz_data):
            st.markdown(f"**ข้อที่ {i+1}:** {q.get('q')}")
            saved = st.session_state.user_answers.get(i)
            if str(q.get('type', '')).upper() == "CHOICE":
                opts = q.get('options', [])
                idx = opts.index(saved) if saved in opts else None
                temp_answers[i] = st.radio(f"คำตอบข้อ {i+1}", opts, key=f"ans_{i}", index=idx, label_visibility="collapsed")
            else:
                temp_answers[i] = st.text_input(f"คำตอบข้อ {i+1}", value=saved if saved else "", key=f"ans_{i}", label_visibility="collapsed")
            st.write("") 

        if st.form_submit_button("📤 ส่งข้อสอบและตรวจคำตอบ", use_container_width=True):
            st.session_state.user_answers = temp_answers
            score = sum(1 for idx, q in enumerate(st.session_state.quiz_data) if str(temp_answers.get(idx, "")).strip().lower() == str(q.get('a', '')).strip().lower() and str(temp_answers.get(idx, "")).strip() != "")
            st.session_state.exam_history.append({"quiz_data": st.session_state.quiz_data, "user_answers": temp_answers, "score": score, "total": len(st.session_state.quiz_data)})
            st.session_state.app_mode = "result"
            st.rerun()

elif st.session_state.app_mode == "result":
    score = sum(1 for i, q in enumerate(st.session_state.quiz_data) if str(st.session_state.user_answers.get(i, "")).strip().lower() == str(q.get('a', '')).strip().lower() and str(st.session_state.user_answers.get(i, "")).strip() != "")
    st.header(f"🎯 คะแนนของคุณ: {score} / {len(st.session_state.quiz_data)}")
    st.progress(score / len(st.session_state.quiz_data))
    for i, q in enumerate(st.session_state.quiz_data):
        u_ans = st.session_state.user_answers.get(i, "")
        correct = str(u_ans).strip().lower() == str(q.get('a', '')).strip().lower() and str(u_ans).strip() != ""
        with st.container(border=True):
            st.write(f"**ข้อที่ {i+1}:** {q.get('q')}")
            if correct: st.success(f"✅ ถูกต้อง! ({u_ans})")
            else:
                st.error(f"❌ ผิด (คำตอบคุณ: {u_ans} | เฉลย: {q.get('a')})")
            st.info(f"💡 {q.get('detail')}")
    if st.button("🔄 สุ่มสร้างชุดใหม่", use_container_width=True):
        st.session_state.app_mode = "start"
        st.rerun()

# บันทึกข้อมูลลง Local Storage (Background Sync)
if st.session_state.ls_synced:
    try:
        state = {"app_mode": st.session_state.app_mode, "quiz_data": st.session_state.quiz_data, "user_answers": st.session_state.user_answers, "exam_history": st.session_state.exam_history}
        b64 = base64.b64encode(json.dumps(state, ensure_ascii=False).encode('utf-8')).decode('utf-8')
        st_javascript(f"localStorage.setItem('comarch_v5', decodeURIComponent(escape(window.atob('{b64}'))));", key=f"save_{hashlib.md5(b64.encode()).hexdigest()}")
    except: pass