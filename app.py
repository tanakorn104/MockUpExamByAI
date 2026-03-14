import streamlit as st
import json
import os
from google import genai
from google.genai import types
from docx import Document
import io
import datetime
import time

# ==========================================
# 0. การตั้งค่าและโหลด API Key
# ==========================================
def get_api_key():
    try:
        return st.secrets["GEMINI_API_KEY"]
    except:
        return os.getenv("GEMINI_API_KEY")

API_KEY = get_api_key()

def load_web_config():
    try:
        with open("web_config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "page_title": "ระบบเก็งข้อสอบ Computer Architecture",
            "welcome_message": "ยินดีต้อนรับ! ระบบนี้จะดึงเนื้อหาจากบทที่ 7 (I/O) และบทที่ 8 (CPU) มาสร้างเป็นข้อสอบจำลองระดับความยากเทียบเท่าข้อสอบจริง",
            "button_text": "🚀 เริ่มสุ่มสร้างข้อสอบ 24 ข้อ",
            "success_message": "สร้างข้อสอบสำเร็จ! ลุยเลยขอให้โชคดี"
        }

config = load_web_config()
st.set_page_config(page_title=config.get("page_title"), page_icon="🎓")

if not API_KEY:
    st.error("❌ ไม่พบ API Key กรุณาตรวจสอบการตั้งค่า")
    st.stop()

# ใช้ API Key จากเครื่องมือที่ให้มา
client = genai.Client(api_key=API_KEY)

# ==========================================
# 1. ระบบจัดการประวัติ (History State)
# ==========================================
if "exam_history" not in st.session_state:
    st.session_state.exam_history = []

# ==========================================
# 2. ฟังก์ชันสร้างไฟล์ Word แบบหลายโหมด
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
# 3. ฟังก์ชันเรียก AI เจนข้อสอบ (Gemini 3.1 Flash Lite Preview)
# ==========================================
def generate_quiz():
    try:
        with open("pre_processed_content.txt", "r", encoding="utf-8") as f:
            content = f.read()
        with open("instruction.txt", "r", encoding="utf-8") as f:
            system_instruction_text = f.read()

        current_time_seed = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

        # บังคับการสอบแบบ Open Book ที่เน้นการคำนวณ (Calculation) และการวิเคราะห์ (Analysis)
        user_prompt = f"""
        สร้างข้อสอบชุดใหม่ (24 ข้อ) โดยอ้างอิงจากเนื้อหาบทที่ 7 และ 8 (Seed: {current_time_seed})
        
        เป้าหมายหลัก: เน้นการคำนวณ (Calculation) และการวิเคราะห์เชิงลึก (Deep Analysis)
        
        ข้อกำหนดเนื้อหาเฉพาะ:
        1. "ห้ามถามนิยาม" ที่เปิดหนังสือหาคำตอบได้โดยตรง
        2. ทุกข้อต้องมี "ข้อมูลทางเทคนิค" ประกอบ เช่น:
           - เลขฐานสอง (Binary Strings) สำหรับ Booth's Algorithm หรือ Twos Complement
           - ค่าทศนิยมที่ต้องแปลงเป็น IEEE 754 (Single Precision)
           - พารามิเตอร์ CPU (Clock Speed GHz, Bus Width, Memory Latency) สำหรับการคำนวณ I/O throughput หรือ CPU Utilization
           - จำนวน Register และ Opcode สำหรับการคำนวณบิตใน Instruction Format
        3. โครงสร้าง JSON:
           - ข้อ 1-8 (CHOICE): โจทย์สถานการณ์ที่ต้องคำนวณหรือวิเคราะห์ก่อนเลือกคำตอบ ตัวเลือกหลอกต้องมาจากการคำนวณที่ผิดขั้นตอน
           - ข้อ 9-16 (SHORT): โจทย์สั่งให้ "แสดงขั้นตอนการคำนวณ" (Step-by-step calculation) เช่น Booth's Algorithm แต่ละรอบ หรือการแปลง Floating Point
           - ข้อ 17-20 (SHORT): โจทย์วิเคราะห์เปรียบเทียบประสิทธิภาพสถาปัตยกรรม (เช่น ผลกระทบของ Cycle Stealing ต่อ CPU performance)
           - ข้อ 21-24 (SHORT Case Study): โจทย์บูรณาการขนาดใหญ่ Part A (การออกแบบ/คำนวณ) และ Part B (การวิจารณ์ผลกระทบเชิงสถาปัตยกรรม)
        4. ฟิลด์ 'detail': ต้องแสดง "วิธีทำ" (Step-by-step) อย่างละเอียดเป็นภาษาไทย

        เนื้อหาประกอบ:
        {content}
        """

        response = client.models.generate_content(
            model='gemini-3.1-flash-lite-preview',
            config={
                "system_instruction": system_instruction_text + "\nYou are an expert Computer Architecture Professor. Focus on mathematical derivations and performance analysis. Always output in Thai.",
                "temperature": 1.0,
                "response_mime_type": "application/json"
            },
            contents=user_prompt
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
        st.success(f"คุณทำไปแล้ว {len(st.session_state.exam_history)} ชุด")
        history_docx = create_docx(mode="history", history_data=st.session_state.exam_history)
        st.download_button("💾 โหลดประวัติทั้งหมด (Word)", history_docx, "History.docx", use_container_width=True)

# ==========================================
# 5. หน้าจอหลัก (UI)
# ==========================================
if "app_mode" not in st.session_state:
    st.session_state.app_mode = "start"

st.title(f"🎓 {config.get('page_title')}")

if st.session_state.app_mode == "start":
    st.markdown(f"**{config.get('welcome_message')}**")
    st.info("💡 เวอร์ชันอัปเดต: เน้นโจทย์เชิงคำนวณ Booth's, IEEE 754 และการวิเคราะห์ CPU Utilization")
    if st.button(config.get('button_text'), use_container_width=True):
        with st.spinner("Gemini 3.1 กำลังสร้างข้อสอบเชิงคำนวณระดับสูง 24 ข้อ..."):
            if generate_quiz():
                st.rerun()

elif st.session_state.app_mode == "quiz_running":
    st.success(config.get('success_message'))
    worksheet_data = create_docx(quiz_data=st.session_state.quiz_data, mode="worksheet")
    st.download_button("📥 โหลดใบงาน (โจทย์+เฉลยหน้าหลัง)", worksheet_data, "Worksheet.docx", use_container_width=True)
    st.divider()

    with st.form("exam_form"):
        temp_answers = {}
        for i, q in enumerate(st.session_state.quiz_data):
            st.markdown(f"**ข้อที่ {i+1}:** {q.get('q')}")
            if str(q.get('type')).upper() == "CHOICE":
                temp_answers[i] = st.radio(f"คำตอบข้อ {i+1}", q.get('options', []), key=f"ans_{i}", index=None, label_visibility="collapsed")
            else:
                temp_answers[i] = st.text_input(f"คำตอบข้อ {i+1}", key=f"ans_{i}", placeholder="พิมพ์การวิเคราะห์หรือแสดงขั้นตอนการคำนวณ...", label_visibility="collapsed")
            st.write("") 

        if st.form_submit_button("📤 ส่งข้อสอบและตรวจคำตอบ", use_container_width=True):
            st.session_state.user_answers = temp_answers
            score = sum(1 for idx, q in enumerate(st.session_state.quiz_data) if str(temp_answers.get(idx, "")).strip().lower() == str(q.get('a', '')).strip().lower())
            st.session_state.exam_history.append({"quiz_data": st.session_state.quiz_data, "user_answers": temp_answers, "score": score, "total": len(st.session_state.quiz_data)})
            st.session_state.app_mode = "result"
            st.rerun()

elif st.session_state.app_mode == "result":
    score = sum(1 for i, q in enumerate(st.session_state.quiz_data) if str(st.session_state.user_answers.get(i, "")).strip().lower() == str(q.get('a', '')).strip().lower())
    st.header(f"🎯 คะแนนของคุณ: {score} / {len(st.session_state.quiz_data)}")
    for i, q in enumerate(st.session_state.quiz_data):
        u_ans = st.session_state.user_answers.get(i, "")
        is_correct = str(u_ans).strip().lower() == str(q.get('a')).strip().lower()
        with st.container(border=True):
            st.write(f"**ข้อที่ {i+1}:** {q.get('q')}")
            if is_correct: st.success(f"✅ ถูกต้อง! ({u_ans})")
            else:
                st.error(f"❌ ผิด (คำตอบคุณ: {u_ans} | เฉลย: {q.get('a')})")
            st.info(f"💡 **วิธีทำอย่างละเอียด:** {q.get('detail')}")
    if st.button("🔄 สุ่มสร้างชุดใหม่", use_container_width=True):
        st.session_state.app_mode = "start"
        st.rerun()