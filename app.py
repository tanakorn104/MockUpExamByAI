import streamlit as st
import json
import os
from google import genai
from google.genai import types
from docx import Document

# ==========================================
# 0. ตั้งค่าพื้นฐานและ API
# ==========================================
# ดึง API Key จาก Secrets ของ Streamlit
API_KEY = st.secrets["GEMINI_API_KEY"]
client = genai.Client(api_key=API_KEY)

# ==========================================
# 1. ฟังก์ชันโหลดค่า Config จากไฟล์ JSON
# ==========================================
def load_web_config():
    try:
        with open("web_config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        # ถ้าหาไฟล์ไม่เจอ ให้ใช้ค่าเริ่มต้น
        return {
            "page_title": "Mock Exam Generator",
            "welcome_message": "กดปุ่มด้านล่างเพื่อเริ่มสร้างข้อสอบ",
            "button_text": "🚀 เริ่มสร้างข้อสอบ",
            "success_message": "✅ สร้างข้อสอบสำเร็จ!"
        }

config = load_web_config()
st.set_page_config(page_title=config.get("page_title", "Mock Exam"), page_icon="🎓")

# ==========================================
# 2. ฟังก์ชันสร้างไฟล์ Word (Export)
# ==========================================
def create_export_file(quiz_data):
    doc = Document()
    doc.add_heading('เฉลยข้อสอบ Computer Architecture', 0)
    
    for i, q in enumerate(quiz_data):
        # ดักจับทุกชื่อ Key ที่ AI อาจจะเผลอใช้
        q_text = q.get('q', q.get('question', q.get('Question', 'ไม่พบโจทย์')))
        doc.add_heading(f"ข้อที่ {i+1}: {q_text}", level=1)
        
        q_type = str(q.get('type', q.get('Type', 'unknown'))).lower()
        if q_type == 'choice':
            options = q.get('options', q.get('choices', q.get('Options', [])))
            for opt in options:
                doc.add_paragraph(str(opt))
        
        a_text = q.get('a', q.get('answer', q.get('Answer', 'ไม่พบคำตอบ')))
        doc.add_paragraph(f"คำตอบ: {a_text}", style='Intense Quote')
        
        detail_text = q.get('detail', q.get('explanation', q.get('Detail', 'ไม่มีคำอธิบายเพิ่มเติม')))
        doc.add_paragraph(f"คำอธิบาย: {detail_text}")
        doc.add_paragraph("-" * 30)
        
    import io
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()

# ==========================================
# 3. ฟังก์ชันเรียก AI เจนข้อสอบ
# ==========================================
def generate_quiz():
    content_path = "pre_processed_content.txt"
    instruction_path = "instruction.txt"

    try:
        if not os.path.exists(content_path) or not os.path.exists(instruction_path):
            st.error("❌ ไม่พบไฟล์ pre_processed_content.txt หรือ instruction.txt บน GitHub")
            return False

        with open(content_path, "r", encoding="utf-8") as f:
            content = f.read()
        with open(instruction_path, "r", encoding="utf-8") as f:
            final_instruction = f.read()

        # บังคับโครงสร้าง Output Schema ให้ AI ตอบตามที่เราต้องการเป๊ะๆ
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

        # ส่งข้อมูลให้ Gemini 2.5 Flash
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"เนื้อหาหลักสำหรับออกข้อสอบ:\n{content}",
            config=types.GenerateContentConfig(
                system_instruction=final_instruction,
                temperature=0.8,
                response_mime_type="application/json",
                response_schema=response_schema # เพิ่ม Schema บังคับ
            )
        )
        
        # คลีน JSON
        clean_json = response.text.strip()
        if clean_json.startswith("```json"):
            clean_json = clean_json[7:]
        if clean_json.endswith("```"):
            clean_json = clean_json[:-3]
            
        # strict=False เพื่อกัน Error เรื่องการขึ้นบรรทัดใหม่
        parsed_data = json.loads(clean_json.strip(), strict=False)
        
        # ดักจับกรณี AI ห่อข้อสอบมาใน Object เช่น {"quiz": [...]} แทนที่จะเป็น Array ตรงๆ
        if isinstance(parsed_data, dict):
            for key, value in parsed_data.items():
                if isinstance(value, list):
                    parsed_data = value
                    break
            else:
                parsed_data = [parsed_data]
                
        st.session_state.quiz_data = parsed_data
        st.session_state.current_idx = 0
        st.session_state.app_mode = "quiz"
        return True

    except Exception as e:
        st.error(f"❌ เกิดข้อผิดพลาดในการสร้างข้อสอบ: {str(e)}")
        # ถ้ามี Error จะแสดงข้อความดิบที่ AI ตอบมา ให้เราวิเคราะห์ได้ว่าพังตรงไหน
        if 'response' in locals():
            with st.expander("🔍 ดูข้อมูลดิบที่ AI ตอบกลับมา (Debug)"):
                st.write(response.text)
        return False

# ==========================================
# 4. หน้าจอหลัก (UI)
# ==========================================
if "app_mode" not in st.session_state:
    st.session_state.app_mode = "start"

st.title(f"🎓 {config.get('page_title', 'ระบบเก็งข้อสอบ')}")

# --- โหมดเริ่มต้น (หน้าแรก) ---
if st.session_state.app_mode == "start":
    st.markdown(f"**{config.get('welcome_message', 'ยินดีต้อนรับ!')}**")
    st.info("💡 ข้อสอบจะถูกสร้างใหม่ทุกครั้งที่กดปุ่ม โดยอิงจากสไตล์ข้อสอบเก่าของอาจารย์")
    
    if st.button(config.get('button_text', '🚀 เริ่มสร้างข้อสอบ'), use_container_width=True):
        with st.spinner("🧠 AI กำลังแต่งข้อสอบระดับวิศวกรรมให้คุณ... (อาจใช้เวลา 15-30 วินาที)"):
            if generate_quiz():
                st.rerun()

# --- โหมดทำข้อสอบ ---
elif st.session_state.app_mode == "quiz":
    st.success(config.get('success_message', '✅ สร้างข้อสอบสำเร็จ! เลื่อนดูโจทย์ด้านล่างได้เลย'))
    
    if not st.session_state.quiz_data:
         st.error("ไม่พบข้อมูลข้อสอบ กรุณาลองใหม่อีกครั้ง")
         if st.button("ย้อนกลับ"):
             st.session_state.app_mode = "start"
             st.rerun()
    else:
        # วนลูปแสดงข้อสอบทั้งหมด
        for i, q in enumerate(st.session_state.quiz_data):
            # ดึงข้อมูลแบบปลอดภัย ดักจับทุกชื่อ Key
            q_type = str(q.get('type', q.get('Type', 'UNKNOWN'))).upper()
            q_text = q.get('q', q.get('question', q.get('Question', 'ไม่พบโจทย์')))
            
            st.markdown(f"### ข้อที่ {i+1} ({q_type})")
            st.write(f"**โจทย์:** {q_text}")
            
            if q_type == 'CHOICE':
                options = q.get('options', q.get('choices', q.get('Options', [])))
                for opt in options:
                    st.write(f"- {opt}")
            
            # ปุ่มกดดูเฉลยทีละข้อ
            with st.expander("👀 ดูเฉลยและคำอธิบาย"):
                a_text = q.get('a', q.get('answer', q.get('Answer', 'ไม่พบคำตอบ')))
                detail_text = q.get('detail', q.get('explanation', q.get('Detail', 'ไม่มีคำอธิบายเพิ่มเติม')))
                
                st.success(f"**คำตอบ:** {a_text}")
                st.info(f"**คำอธิบาย:** {detail_text}")
                
            st.divider()

        # ปุ่ม Export ไฟล์ Word
        try:
            word_file = create_export_file(st.session_state.quiz_data)
            st.download_button(
                label="💾 ดาวน์โหลดเฉลยทั้งหมดเป็นไฟล์ Word",
                data=word_file,
                file_name="ComArch_Final_MockExam.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True
            )
        except Exception as e:
            st.error(f"ไม่สามารถสร้างไฟล์ Word ได้: {e}")
        
        # ปุ่มสุ่มใหม่
        if st.button("🔄 สร้างข้อสอบชุดใหม่อีกครั้ง", use_container_width=True):
            st.session_state.app_mode = "start"
            st.session_state.quiz_data = None
            st.rerun()