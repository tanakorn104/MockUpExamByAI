import google.generativeai as genai
import os
from dotenv import load_dotenv

# โหลด API Key จากไฟล์ .env ของคุณ
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

print("=== กำลังดึงข้อมูลจาก Google... ===")
print("รายชื่อโมเดลที่ API Key นี้สามารถใช้เจนเนื้อหาได้:")

try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print("-", m.name)
except Exception as e:
    print("เกิดข้อผิดพลาดในการดึงข้อมูล:", e)