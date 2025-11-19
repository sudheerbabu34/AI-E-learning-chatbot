# AI-E-learning-chatbot

## Overview

This project is a web‑based **AI Learning Assistant** built with Flask. It allows a learner to:

- **Ask text questions** and receive detailed, structured study notes.
- **Use voice input** (browser speech recognition) to ask questions and get text answers.
- **Ask questions about images** (Visual Q&A) using multimodal AI.
- **Generate quizzes** (MCQs) from the AI’s explanation to self‑test understanding.

The backend uses Google’s **Gemini 2.0 Flash** generative model via HTTP API calls, while the frontend is a single‑page HTML + JavaScript interface.
---

## Tech Stack

### Languages
- **Python 3**
- **HTML5 / CSS3 / JavaScript**

### Backend
- **Flask** – routes (`/`, `/ask`, `/generate_quiz`, `/ask_voice`, `/ask_image`) and template/file handling.
- **requests** – HTTP client to Gemini with a shared `Session` and retry strategy.
- **SpeechRecognition** – optional server‑side speech‑to‑text support for `/ask_voice`.
- **Standard library** – `base64`, `json`, `tempfile`, `os`, `re` for encoding, JSON, temp files, and output cleanup.

### Frontend
- **HTML + CSS** – single `index.html`, responsive layout and basic theming.
---

## Core Features & Techniques

### 1. Text Question → Study Guide (`POST /ask`)

- Receives a text `question` and builds a structured study‑guide prompt.
- Configures Gemini (tokens, temperature, sampling) for detailed but focused answers.
- Cleans the response by removing labels (such as "Generated Content:", "Answer:") and duplicate text.
- Stores the answer in `lastContent` so a quiz can be generated from it.

### 2. Quiz Generation (`POST /generate_quiz`)

- Uses the AI explanation (`content`) to create 5 MCQ questions.
- Prompt forces **JSON‑only** output with a fixed schema (options `A`–`D` and a `correct` letter).
- Parses JSON (or extracts a JSON block if needed) and validates questions/options.
- Frontend renders questions, tracks selections, highlights correct/incorrect answers, and computes the final `score`.

### 3. Voice Questions

- **Client‑side:** browser **SpeechRecognition** API for live transcription, then sends the text to `/ask`.
- **Server‑side fallback (`/ask_voice`):** accepts audio, saves a temporary `.wav`, uses `SpeechRecognition` with Google STT, then calls Gemini.
- Both flows return text answers and save them in `lastContent` for quiz generation.

### 4. Visual Q&A (`POST /ask_image`)

- Accepts an uploaded image and a text prompt.
- Encodes image bytes to Base64 and sends them as `inlineData` to Gemini.
- Uses an educational multimodal prompt to produce a concise, structured answer that can also be used for quiz generation.
---

## Gemini API Integration Details

- Endpoint: `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent`.
- Auth via API key in the query string (`?key=API_KEY`).
- Shared `requests.Session` with connection pooling and retries on common transient errors.
- `get_gemini_response` builds the request body, sends the request, extracts the first candidate’s text, and then:
  - Deduplicates paragraphs/sentences.
  - Strips labels like "Generated Content:" or "Answer:".
  - Normalizes whitespace so the user sees a single clean answer.
---

## Project Structure (Simplified)

- `app.py` – Flask application and all routes.
- `templates/index.html` – Single‑page UI for text, voice, image, and quiz.
- `requirements.txt` – Python dependencies (`Flask`, `gunicorn`, `requests`, `SpeechRecognition`, etc.).
---

## How to Run (Basic)
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Set the Gemini API key (for example, by replacing `API_KEY` in `app.py` or loading it from the environment).
3. Start the Flask app:
   ```bash
   python app.py
   ```
4. Open the app in a browser at:
   - `http://127.0.0.1:5000/`.
---

## Notes & Possible Improvements
- Move `API_KEY` to environment variables and avoid committing secrets.
- Add authentication / rate limiting for production deployments.
- Add more robust error handling and UI messages for network/API failures.
- Extend quiz generation to support different difficulty levels or question types.
- Persist user sessions or quiz history in a database if needed.
