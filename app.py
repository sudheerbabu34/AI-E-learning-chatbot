from flask import Flask, render_template, request, jsonify
import base64
import requests
import speech_recognition as sr
import json
import tempfile
import os
import re
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

app = Flask(__name__)

# ------------------------------
# Gemini API Setup
# ------------------------------
API_KEY = "AIzaSyD6aZDnKzgrXKZkr3klZEhuUOl4H3cBBrA"
# Using the model specified in the original request URL
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={API_KEY}"

# Shared HTTP session with connection pooling and retries
session = requests.Session()
adapter = HTTPAdapter(
    pool_connections=10,
    pool_maxsize=20,
    max_retries=Retry(total=3, backoff_factor=0.2, status_forcelist=[429, 500, 502, 503, 504])
)
session.mount('http://', adapter)
session.mount('https://', adapter)

# ------------------------------
# Helper Functions
# ------------------------------
def build_text_part(text):
    return {"text": text}

def build_image_part_from_bytes(img_bytes):
    b64_data = base64.b64encode(img_bytes).decode("utf-8")
    return {"inlineData": {"mimeType": "image/jpeg", "data": b64_data}}

def get_gemini_response(parts, timeout=(5, 20)):
    """Send request to Gemini API and ensure only one clean answer is returned."""
    body = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "candidateCount": 1,
            "maxOutputTokens": 512,
            "temperature": 0.4,
            "stopSequences": ["\n\n\n"]
        }
    }
    headers = {"Content-Type": "application/json"}
    resp = session.post(GEMINI_URL, headers=headers, json=body, timeout=timeout)

    if not resp.ok:
        return f"❌ Error {resp.status_code}: {resp.text}"

    try:
        data = resp.json()
        # Initial extraction and strip
        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()

        # ========== SIMPLIFIED DEDUPLICATION to target immediate LLM repetition ==========
        
        # 1. Remove repeated consecutive paragraphs
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        cleaned_paragraphs = []
        for p in paragraphs:
            # Normalize paragraph by collapsing internal whitespace for comparison
            normalized_p = re.sub(r'\s+', ' ', p)
            if normalized_p:
                if not cleaned_paragraphs:
                    cleaned_paragraphs.append(normalized_p)
                else:
                    # Compare against the last cleaned paragraph
                    last_normalized = cleaned_paragraphs[-1]
                    if normalized_p != last_normalized:
                        cleaned_paragraphs.append(normalized_p)
        text = "\n\n".join(cleaned_paragraphs)
        
        # 2. Remove repeated consecutive sentences
        sentences = re.split(r'(?<=[.!?])\s+', text)
        cleaned_sentences = []
        for s in sentences:
            s = s.strip()
            # Normalize internal whitespace for comparison
            normalized_s = re.sub(r'\s+', ' ', s) 
            if normalized_s:
                if not cleaned_sentences:
                    cleaned_sentences.append(s)
                else:
                    # Compare against the last cleaned sentence
                    last_normalized_s = re.sub(r'\s+', ' ', cleaned_sentences[-1])
                    if normalized_s != last_normalized_s:
                        cleaned_sentences.append(s)

        text = " ".join(cleaned_sentences)
        
        # 3. Remove unwanted labels/headers (e.g., "Generated Content:", "Answer:", etc.)
        # Common patterns the AI might add despite instructions
        label_patterns = [
            r'^Generated Content:\s*',
            r'^Answer:\s*',
            r'^Response:\s*',
            r'^Here is the answer:\s*',
            r'^Here\'s the answer:\s*',
            r'^The answer is:\s*',
        ]
        for pattern in label_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        # 4. Final whitespace cleanup
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)
        text = text.strip()

        return text
        
    except Exception as e:
        return f"🤖 Gemini: Couldn't parse the response ({e})."

def extract_json_block(text: str):
    """Extract a JSON object from a free-form model response."""
    if not text:
        return None
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n|\n```$", "", t, flags=re.MULTILINE)
        t = t.strip()
    start = t.find('{')
    end = t.rfind('}')
    if start != -1 and end != -1 and end > start:
        candidate = t[start:end+1]
        try:
            return json.loads(candidate)
        except Exception:
            pass
    return None

# ------------------------------
# Speech Recognizer
# ------------------------------
recognizer = sr.Recognizer()

# ------------------------------
# Routes
# ------------------------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def ask_text():
    question = request.form.get('question', '')
    if not question.strip():
        return jsonify({"answer": "Please enter a valid question."})

    enhanced_prompt = f"""You are an expert educational AI tutor. Provide a comprehensive, detailed, and well-structured study guide in response to the following question. Your response should be suitable for academic study and self-learning.

Guidelines:
1. Start with a clear introduction that defines key terms and concepts
2. Break down complex topics into logical sections with descriptive headers
3. Include 3-5 main points with detailed explanations
4. Provide relevant examples, analogies, or case studies for each main point
5. Use bullet points or numbered lists to organize information clearly
6. Include key terms in bold for emphasis
7. Add a summary or conclusion that ties everything together
8. Suggest related topics or questions for further study
9. Use clear, academic language appropriate for university-level study
10. Ensure the content is detailed enough for thorough understanding but remains focused

Structure your response as follows:
# [Main Topic]
[Brief introduction and context]

## Key Concepts
- Concept 1: [Definition and explanation]
- Concept 2: [Definition and explanation]
  * Example/Application

## Detailed Explanation
[2-3 paragraphs expanding on the topic]

## Practical Applications
- Real-world example 1
- Real-world example 2

## Study Tips
- How to remember key points
- Common misconceptions
- Related topics to explore

Question: {question}"""

    # Update generation config for more detailed responses
    parts = [build_text_part(enhanced_prompt)]
    body = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "candidateCount": 1,
            "maxOutputTokens": 2048,  # Increased for more detailed responses
            "temperature": 0.7,      # Slightly higher for more creative responses
            "topP": 0.9,
            "topK": 40,
            "stopSequences": ["\n\n\n"]
        }
    }
    
    # Make the API call with the updated configuration
    headers = {"Content-Type": "application/json"}
    resp = session.post(GEMINI_URL, headers=headers, json=body, timeout=(10, 30))
    
    if not resp.ok:
        return jsonify({"answer": f"❌ Error {resp.status_code}: {resp.text}"})
        
    try:
        data = resp.json()
        answer = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        # Clean up any remaining artifacts
        answer = re.sub(r'^[\s\n]*(Generated Content|Answer|Response):?[\s\n]*', '', answer, flags=re.IGNORECASE)
        return jsonify({"answer": answer})
    except Exception as e:
        return jsonify({"answer": f"❌ Error processing the response: {str(e)}"})

@app.route('/generate_quiz', methods=['POST'])
def generate_quiz():
    content = request.form.get('content', '')
    if not content.strip():
        return jsonify({"error": "No content provided for quiz generation."})

    quiz_prompt = (
        "You are a quiz generator. Respond with ONLY valid JSON, no prose, no markdown, no code fences.\n"
        "Generate 5 multiple-choice questions from the content below. Each has exactly 4 options A, B, C, D and a 'correct' key with the correct option letter.\n"
        "Schema: {\"questions\":[{\"question\":string, \"options\":{\"A\":string,\"B\":string,\"C\":string,\"D\":string}, \"correct\":\"A|B|C|D\"}]}\n"
        f"Content: {content}"
    )

    parts = [build_text_part(quiz_prompt)]
    quiz_response = get_gemini_response(parts)

    try:
        quiz_data = json.loads(quiz_response)
    except Exception:
        quiz_data = extract_json_block(quiz_response)

    if not isinstance(quiz_data, dict) or 'questions' not in quiz_data:
        return jsonify({
            "questions": [],
            "error": "Could not parse quiz.",
            "raw": quiz_response
        })

    cleaned = []
    for q in quiz_data['questions']:
        try:
            question = str(q.get('question', '')).strip()
            options = q.get('options', {})
            correct = str(q.get('correct', '')).strip().upper()
            if not question or not isinstance(options, dict):
                continue
            opts = {k: str(options.get(k, '')).strip() for k in ['A','B','C','D']}
            if not all(opts.values()):
                continue
            if correct not in ['A','B','C','D']:
                continue
            cleaned.append({"question": question, "options": opts, "correct": correct})
        except Exception:
            continue

    if not cleaned:
        return jsonify({
            "questions": [],
            "error": "Parsed quiz was empty.",
            "raw": quiz_response
        })

    return jsonify({"questions": cleaned})

@app.route('/ask_voice', methods=['POST'])
def ask_voice():
    # Note: This route is redundant because the index.html uses /ask route 
    # after transcription, but we'll keep it for completeness if the frontend changes.
    audio_file = request.files.get('audio')
    if not audio_file:
        return jsonify({"error": "No audio file uploaded."})

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_wav:
            audio_file.save(temp_wav.name)

        with sr.AudioFile(temp_wav.name) as source:
            audio = recognizer.record(source)
            # Use Google Speech Recognition for transcription (client-side uses browser API, so this is for backend fallback)
            text = recognizer.recognize_google(audio) 

        # Now send the transcribed text to the model using the standard prompt
        parts = [build_text_part(text)]
        answer = get_gemini_response(parts)

        return jsonify({"transcription": text, "answer": answer})

    except Exception as e:
        return jsonify({"error": str(e)})

    finally:
        # Cleanup temporary file if it exists
        if 'temp_wav' in locals() and os.path.exists(temp_wav.name):
            os.remove(temp_wav.name)


@app.route('/ask_image', methods=['POST'])
def ask_image():
    prompt = request.form.get('prompt', '')
    image_file = request.files.get('image')
    if not prompt.strip() or image_file is None:
        return jsonify({"answer": "Please upload an image and enter a prompt."})

    img_bytes = image_file.read()
    if not img_bytes:
        return jsonify({"answer": "Uploaded image is empty. Please try again."})

    enhanced_prompt = f"""You are an educational AI assistant analyzing images. Provide a clear, concise, and study-friendly response.

Guidelines:
- Keep responses focused and well-structured (2-4 paragraphs)
- Use bullet points when listing multiple items
- Include key concepts and explanations
- Provide educational insights about what's shown
- Avoid unnecessary verbosity while ensuring clarity
- Start DIRECTLY with your answer content. Do NOT use any labels, headers, or meta-text like "Generated Content:", "Answer:", "Response:", "The image shows:", etc.
- Do NOT repeat or restate your answer

User's question: {prompt}"""

    image_part = build_image_part_from_bytes(img_bytes)
    parts = [build_text_part(enhanced_prompt), image_part]
    answer = get_gemini_response(parts)
    return jsonify({"answer": answer})

if __name__ == "__main__":
    app.run(debug=False, threaded=True)