import streamlit as st
import google.generativeai as genai
import PyPDF2
from docx import Document
import json
import os
import time  # เพิ่ม time สำหรับระบบหน่วงเวลาป้องกันบอท
from dotenv import load_dotenv

# โหลดค่าจากไฟล์ .env
load_dotenv()

def get_config(key):
    try:
        # ลองหาใน st.secrets ก่อน (สำหรับ Streamlit Cloud)
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    # ถ้าไม่เจอ ให้หาจาก environment variable / .env
    return os.getenv(key)

API_KEY = get_config("GEMINI_API_KEY")
ADMIN_PW = get_config("ADMIN_PASSWORD") 

# --- 1. การตั้งค่า API ---
if not API_KEY:
    st.error("เกิดข้อผิดพลาด: ไม่พบ API KEY สำหรับ AI")
else:
    genai.configure(api_key=API_KEY)

# --- 2. ฟังก์ชันช่วยอ่านไฟล์ ---
def extract_text(uploaded_file):
    f_type = uploaded_file.name.split('.')[-1].lower()
    text = ""
    try:
        if f_type == 'pdf':
            reader = PyPDF2.PdfReader(uploaded_file)
            for page in reader.pages:
                text += page.extract_text()
        elif f_type == 'docx':
            doc = Document(uploaded_file)
            for para in doc.paragraphs:
                text += para.text + "\n"
    except Exception as e:
        st.error(f"ไม่สามารถอ่านไฟล์ได้: {e}")
    return text

# --- 3. ระบบจัดการความจำ (Session State) ---
if 'quiz_data' not in st.session_state:
    st.session_state.quiz_data = []
if 'current_idx' not in st.session_state:
    st.session_state.current_idx = 0
if 'app_mode' not in st.session_state:
    st.session_state.app_mode = "start"
if 'custom_instruction' not in st.session_state:
    st.session_state.custom_instruction = "เน้นการคิดวิเคราะห์และโจทย์ประยุกต์"
if 'num_q' not in st.session_state:
    st.session_state.num_q = 5
if 'user_answers' not in st.session_state:
    st.session_state.user_answers = {}
    
# ตัวแปรใหม่: ระบบป้องกันล็อกอิน และ ข้อความต้อนรับ
if 'login_attempts' not in st.session_state:
    st.session_state.login_attempts = 0
if 'welcome_message' not in st.session_state:
    st.session_state.welcome_message = "ยินดีต้อนรับ! ระบบนี้จะช่วยคุณเก็งข้อสอบจากเนื้อหาบทเรียนที่แอดมินเตรียมไว้ให้"

# --- 4. หน้าตาโปรแกรม (UI) ---
st.set_page_config(page_title="AI Exam Master", layout="centered")

# --- แถบควบคุมสำหรับแอดมิน (Sidebar) ---
with st.sidebar:
    st.header("🔐 Admin Control Panel")
    
    # ระบบป้องกัน Brute-force
    if st.session_state.login_attempts >= 3:
        st.error("🚨 ระบบถูกล็อกเนื่องจากใส่รหัสผิดเกิน 3 ครั้ง!")
        st.warning("กรุณารีเฟรชหน้าเว็บ (F5) เพื่อลองใหม่")
    else:
        pw = st.text_input("รหัสผ่านแอดมิน", type="password")
        
        if pw:
            if pw == ADMIN_PW:
                st.session_state.login_attempts = 0 # รีเซ็ตค่าเมื่อเข้าถูก
                st.success("เข้าสู่ระบบแอดมินสำเร็จ")
                st.divider()
                
                # --- ส่วนตั้งค่าเนื้อหาหน้าเว็บ ---
                st.subheader("📝 ปรับแต่งหน้าเว็บ")
                st.session_state.welcome_message = st.text_area(
                    "คำอธิบายใต้หัวข้อเว็บ:",
                    value=st.session_state.welcome_message,
                    height=80
                )
                
                st.divider()
                st.subheader("🛠️ ตั้งค่าข้อสอบ")
                st.session_state.num_q = st.number_input("จำนวนข้อสอบที่ต้องการ:", min_value=1, max_value=20, value=st.session_state.num_q)
                st.session_state.custom_instruction = st.text_area(
                    "คำสั่งเพิ่มเติมถึง AI (System Instruction):",
                    value=st.session_state.custom_instruction,
                    height=80
                )
                
                uploaded_file = st.file_uploader("อัปโหลดเนื้อหาบทเรียน (PDF/DOCX)", type=["pdf", "docx"])
                
                if st.button("🚀 สร้างข้อสอบใหม่ตามเงื่อนไข") and uploaded_file:
                    with st.spinner("AI กำลังวิเคราะห์เนื้อหาและเจนข้อสอบ..."):
                        content = extract_text(uploaded_file)
                        
                        final_instruction = f"""
                        คุณคืออาจารย์ผู้เชี่ยวชาญ หน้าที่คือสร้างข้อสอบจำนวน {st.session_state.num_q} ข้อ 
                        จากเนื้อหาที่กำหนด ในรูปแบบ JSON เท่านั้น
                        ข้อกำหนด: คละประเภท (choice, short, long) ตามความเหมาะสมของวิชา
                        คำสั่งพิเศษ: {st.session_state.custom_instruction}
                        
                        รูปแบบ JSON:
                        [
                          {{"type": "choice", "q": "โจทย์", "options": ["A","B","C","D"], "a": "คำตอบ", "detail": "คำอธิบาย"}},
                          {{"type": "short", "q": "โจทย์เติมคำ", "a": "คำตอบ", "detail": "คำอธิบาย"}},
                          {{"type": "long", "q": "โจทย์อัตนัย/คำนวณ", "a": "วิธีทำละเอียด", "detail": "หลักการ"}}
                        ]
                        """
                        
                        # โค้ดที่แก้ไขแล้ว
                        model = genai.GenerativeModel(model_name='gemini-1.5-pro-latest', system_instruction=final_instruction)
                        response = model.generate_content(f"เนื้อหาบทเรียน: {content[:30000]}")
                        
                        try:
                            clean_json = response.text.replace('```json', '').replace('```', '').strip()
                            st.session_state.quiz_data = json.loads(clean_json)
                            st.session_state.current_idx = 0
                            st.session_state.user_answers = {}
                            st.session_state.app_mode = "start" # กลับไปหน้าเริ่มหลังเจนเสร็จ
                            st.success("อัปเดตข้อสอบเรียบร้อย!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"เกิดข้อผิดพลาดในการเจน JSON: {e}")
            else:
                # กรณีใส่รหัสผิด
                st.session_state.login_attempts += 1
                st.error(f"รหัสผ่านไม่ถูกต้อง! (เหลือโอกาส {3 - st.session_state.login_attempts} ครั้ง)")
                time.sleep(2) # หน่วงเวลา 2 วินาที ป้องกันบอทยิงรหัส

# --- ส่วนการแสดงผลสำหรับผู้ใช้ (Main UI) ---

# แสดงหัวเว็บและคำอธิบาย (แสดงเสมอไม่ว่าจะมีข้อสอบหรือไม่)
st.title("🎓 ระบบเก็งข้อสอบอัจฉริยะ")
st.markdown(f"*{st.session_state.welcome_message}*") # แสดงข้อความที่แอดมินตั้งค่าไว้
st.divider()

if not st.session_state.quiz_data:
    st.info("🚧 ระบบยังไม่มีข้อมูลข้อสอบ กรุณารอแอดมินอัปโหลดไฟล์บทเรียนเข้าระบบ")
else:
    # หน้าที่ 1: หน้าเริ่ม
    if st.session_state.app_mode == "start":
        st.write(f"📌 วิชานี้ถูกเก็งข้อสอบไว้ทั้งหมด **{len(st.session_state.quiz_data)}** ข้อ")
        if st.button("เริ่มทำแบบทดสอบ 🚀"):
            st.session_state.app_mode = "quiz"
            st.rerun()

    # หน้าที่ 2: แสดงโจทย์ทีละข้อ
    elif st.session_state.app_mode == "quiz":
        idx = st.session_state.current_idx
        q = st.session_state.quiz_data[idx]
        
        st.progress((idx + 1) / len(st.session_state.quiz_data))
        st.write(f"**ข้อที่ {idx + 1} จาก {len(st.session_state.quiz_data)}**")
        st.markdown(f"### {q['q']}")

        ans_key = f"q_{idx}"
        if q['type'] == "choice":
            st.session_state.user_answers[ans_key] = st.radio("เลือกคำตอบ:", q['options'], key=ans_key)
        elif q['type'] == "short":
            st.session_state.user_answers[ans_key] = st.text_input("พิมพ์คำตอบของคุณ:", key=ans_key)
        else:
            st.session_state.user_answers[ans_key] = st.text_area("เขียนวิธีทำ/คำอธิบาย:", key=ans_key, height=150)

        st.write("") # เว้นบรรทัดนิดหน่อย
        col1, col2 = st.columns(2)
        with col1:
            if idx > 0:
                if st.button("⬅️ ข้อก่อนหน้า"):
                    st.session_state.current_idx -= 1
                    st.rerun()
        with col2:
            if idx < len(st.session_state.quiz_data) - 1:
                if st.button("ข้อถัดไป ➡️"):
                    st.session_state.current_idx += 1
                    st.rerun()
            else:
                if st.button("✅ ส่งข้อสอบ"):
                    st.session_state.app_mode = "result"
                    st.rerun()

    # หน้าที่ 3: สรุปผลและเฉลย
    elif st.session_state.app_mode == "result":
        st.subheader("📊 เฉลยแบบละเอียด")
        for i, q in enumerate(st.session_state.quiz_data):
            with st.expander(f"ข้อที่ {i+1}: {q['q'][:60]}..."):
                u_ans = st.session_state.user_answers.get(f"q_{i}", "ไม่ได้ตอบ")
                st.write(f"**คำตอบของคุณ:** {u_ans}")
                st.success(f"**เฉลย:** {q['a']}")
                st.info(f"**คำอธิบายเสริม:** {q['detail']}")
        
        st.write("")
        if st.button("🔄 กลับหน้าหลัก"):
            st.session_state.app_mode = "start"
            st.session_state.current_idx = 0
            st.rerun()