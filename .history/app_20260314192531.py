import streamlit as st

# --- CONFIGURATION ---
st.set_page_config(page_title="Computer Architecture Quiz", layout="centered")

# --- SESSION STATE (ระบบจำค่า) ---
if 'step' not in st.session_state:
    st.session_state.step = "start"
if 'current_q_idx' not in st.session_state:
    st.session_state.current_q_idx = 0
if 'user_answers' not in st.session_state:
    st.session_state.user_answers = {}

# --- เปลี่ยน Mock Quiz เป็นเนื้อหา Computer Architecture ---
mock_quiz = [
    {
        "type": "choice",
        "q": "ในสถาปัตยกรรมแบบ RISC (Reduced Instruction Set Computer) ข้อใดกล่าวถูกต้อง?",
        "options": [
            "มีการใช้งาน Instruction ที่ซับซ้อนและมีความยาวไม่คงที่",
            "เน้นการทำ Pipelining ให้มีประสิทธิภาพสูงสุดด้วยคำสั่งขนาดคงที่",
            "เข้าถึง Memory ได้โดยตรงผ่านทุกคำสั่งประมวลผล",
            "เน้นการลดจำนวน Register เพื่อประหยัดพื้นที่ Die"
        ],
        "a": "เน้นการทำ Pipelining ให้มีประสิทธิภาพสูงสุดด้วยคำสั่งขนาดคงที่",
        "detail": "RISC ออกแบบมาให้แต่ละคำสั่งมีขนาดเท่ากัน (Fixed-length) เพื่อให้การทำ Fetch/Decode ใน Pipeline ทำได้ง่ายและเร็ว"
    },
    {
        "type": "short",
        "q": "จงระบุชื่อของ 'Hazard' ที่เกิดขึ้นเมื่อคำสั่งหนึ่งต้องรอผลลัพธ์จากคำสั่งก่อนหน้าเพื่อนำมาประมวลผลต่อ (Data Dependency)",
        "a": "Data Hazard",
        "detail": "Data Hazard เกิดขึ้นเมื่อมีพึ่งพาข้อมูลกัน เช่น คำสั่ง ADD R1, R2, R3 ตามด้วย SUB R4, R1, R5 โดยที่ R1 ยังเขียนกลับไม่เสร็จ"
    },
    {
        "type": "long",
        "q": "จงคำนวณหาค่า Average Memory Access Time (AMAT) หากกำหนดให้: \n- L1 Hit Time = 1 Cycle \n- L1 Miss Rate = 5% \n- Miss Penalty = 100 Cycles \n(แสดงสูตรและวิธีคำนวณ)",
        "a": "AMAT = Hit Time + (Miss Rate × Miss Penalty)\n= 1 + (0.05 × 100)\n= 1 + 5\n= 6 Cycles",
        "detail": "สูตร AMAT คือการคิดค่าเฉลี่ยถ่วงน้ำหนักระหว่างเวลาที่ Hit และเวลาที่ต้องเสียไปเมื่อ Miss"
    }
]

# --- FRONTEND LOGIC ---

if st.session_state.step == "start":
    st.title("🖥️ Computer Architecture Final Review")
    st.subheader("วิชาสถาปัตยกรรมคอมพิวเตอร์ (สำหรับวิศวกรรมคอมพิวเตอร์)")
    st.write("แบบทดสอบนี้จำลองโลจิกการออกข้อสอบแบบผสม: ปรนัย, ความจำ และการคำนวณทางวิศวกรรม")
    if st.button("เริ่มทำข้อสอบ 🚀"):
        st.session_state.step = "quiz"
        st.rerun()

elif st.session_state.step == "quiz":
    idx = st.session_state.current_q_idx
    q_item = mock_quiz[idx]
    
    st.progress((idx + 1) / len(mock_quiz))
    st.write(f"**Question {idx + 1} of {len(mock_quiz)}**")
    st.markdown(f"### {q_item['q']}")

    ans_key = f"q_{idx}"
    if q_item['type'] == "choice":
        st.session_state.user_answers[ans_key] = st.radio("เลือกคำตอบที่ถูกต้อง:", q_item['options'], key=ans_key)
    elif q_item['type'] == "short":
        st.session_state.user_answers[ans_key] = st.text_input("คำตอบของคุณ (Short Answer):", key=ans_key)
    else:
        st.session_state.user_answers[ans_key] = st.text_area("แสดงวิธีทำ / อธิบาย (Long Answer):", key=ans_key, height=200)

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if idx > 0:
            if st.button("⬅️ ย้อนกลับ"):
                st.session_state.current_q_idx -= 1
                st.rerun()
    with col2:
        if idx < len(mock_quiz) - 1:
            if st.button("ข้อถัดไป ➡️"):
                st.session_state.current_q_idx += 1
                st.rerun()
        else:
            if st.button("✅ ส่งข้อสอบและตรวจคำตอบ"):
                st.session_state.step = "result"
                st.rerun()

elif st.session_state.step == "result":
    st.title("📊 สรุปผลการทดสอบ")
    
    for i, q in enumerate(mock_quiz):
        with st.expander(f"ข้อที่ {i+1}: {q['q'][:60]}..."):
            u_ans = st.session_state.user_answers.get(f'q_{i}', 'ไม่ได้ตอบ')
            st.write(f"**คำตอบของคุณ:** {u_ans}")
            st.success(f"**เฉลย:** {q['a']}")
            st.info(f"**คำอธิบายเชิงลึก:** {q['detail']}")

    if st.button("🔄 ลองทำใหม่อีกครั้ง"):
        st.session_state.step = "start"
        st.session_state.current_q_idx = 0
        st.session_state.user_answers = {}
        st.rerun()