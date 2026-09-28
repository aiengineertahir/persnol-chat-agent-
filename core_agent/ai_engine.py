import os
from dotenv import load_dotenv
import groq
import google.generativeai as genai
from PIL import Image
from system_prompt import SYSTEM_PROMPT

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# API Clients Initialize
groq_client = groq.Groq(api_key=os.getenv("GROQ_API_KEY"))
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# 1. Text Messages processing via Groq
def get_text_reply(user_text: str) -> str:
    models_to_try = ["openai/gpt-oss-20b", "qwen/qwen3.6-27b", "allam-2-7b"]
    for model_name in models_to_try:
        try:
            response = groq_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_text}
                ],
                temperature=0.7,
                max_tokens=1024
            )
            content = response.choices[0].message.content
            # Strip reasoning tags if model includes them
            if "<think>" in content and "</think>" in content:
                content = content.split("</think>")[-1].strip()
            return content
        except Exception as err:
            continue
            
    # Fallback to Gemini if Groq fails
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        chat = model.start_chat(history=[])
        response = chat.send_message(f"{SYSTEM_PROMPT}\nUser: {user_text}")
        return response.text
    except Exception as e:
        return f"Walaikum Assalam! Main theek hoon bhai, aap sunao? (AI Engine: {str(e)})"

# 2. Voice Notes transcription via Groq Whisper API
def transcribe_audio(audio_path: str) -> str:
    with open(audio_path, "rb") as file:
        transcription = groq_client.audio.transcriptions.create(
            file=(audio_path, file.read()),
            model="whisper-large-v3-turbo",
            response_format="json"
        )
    return transcription.text

# 3. Image Recognition via Gemini 1.5 Flash Vision
def get_image_reply(image_path: str, caption: str = "") -> str:
    img = Image.open(image_path)
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    prompt = f"{SYSTEM_PROMPT}\nUser shared an image. User Caption: {caption or 'Analyze this image and comment naturally.'}"
    response = model.generate_content([prompt, img])
    return response.text