# PulseVox 🗣✨

PulseVox is an intelligent, conversational assistant that turns your spoken commands into organized, actionable plans. This project, now deployed as a full web application, serves as a comprehensive proof-of-concept for advanced **Spoken Language Understanding (SLU)**, demonstrating robust semantic analysis and discourse processing.

## 🚀 Live Demo

Experience the app live (no installation required):

**[https://pulsevox.streamlit.app/](https://pulsevox.streamlit.app/)**

---

## 🚀 Core Features (MVP)
PulseVox understands human intent and context, supporting complex operations in a single conversational flow.

### 💬 Conversational & Multilingual
* **Conversational Context:** Maintains memory of the current session, allowing for follow-up commands and pronoun resolution (e.g., "Add a meeting at 4 PM." ... "Actually, move *it* to 5 PM.").
* **Hinglish Support:** Accurately transcribes spoken commands, supporting **Hinglish (Code-Mixed) input** and automatically resolving common Hindi time phrases like **'kal'** (tomorrow), **'parson'** (day after tomorrow), and **'shaam ko'** (evening).

### 🧠 Intelligent Task Management (CRUD+S)
* **Add (Create):** Identifies intent, extracts all entities (task, date, time), and saves new tasks with an **automatic category** (`Work`, `Social`, `Errand`, or `Personal`).
* **Update/Move:** Locates and modifies existing tasks based on partial details or conversational context (e.g., "change my 6pm call to 7").
* **Remove/Delete:** Finds and eliminates specific tasks using context (e.g., "remove the conference").
* **Query:** Answers questions about your schedule ("am I free at 5?") or a full day's plan.
* **Summarize:** Generates a concise, natural-language summary of a full day's events ("summarize my day for tomorrow").

### ⚙️ Web Interface Features
* **Voice-to-Text:** Uses `streamlit-mic-recorder` to capture audio directly in the browser.
* **Audio Feedback:** Provides a spoken response for every action using `gTTS` and `st.audio`.
* **Conflict Detection:** Automatically checks new event times against existing scheduled tasks to alert the user of overlaps.
* **Live NLP View:** The history panel displays the user's command, the assistant's reply, and the **raw JSON extracted by the LLM**, making the NLP process transparent.

---

## 🛠 Technology Stack

| Component | Library / API | Role |
| :--- | :--- | :--- |
| Web Framework | `Streamlit` | Hosts the interactive web application. |
| SLU / NLU Engine | `Google Gemini API` | Intent classification, entity extraction, context, summarization. |
| Audio Input | `streamlit-mic-recorder` | Captures user audio from the browser. |
| Audio Conversion | `pydub` | Converts browser audio (WebM) to WAV for transcription. |
| Speech-to-Text | `SpeechRecognition` | Transcribes audio data to text. |
| Audio Output | `gTTS` / `st.audio` | Generates and plays audio feedback in the browser. |
| Data Display | `Pandas` | Renders the task list in a clean table. |
| Core Logic | `Python` | Handles state, file I/O, and business logic. |

---

## ⚙ Setup and Installation

### 1️⃣ Clone the Repository
```bash
git clone https://github.com/your-username/pulsevox.git
cd pulsevox
```

### 2️⃣ Create a Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3️⃣ Install Dependencies
```bash
pip install -r requirements.txt
```
> You may need to install *portaudio* for PyAudio to work correctly for CLI Demo. Refer to the PyAudio documentation for platform-specific instructions.

> You may need to install *FFmpeg* system library from for audio conversion to work for local Web Demo.

### 4️⃣ Configure Your API Key
1. Get your API key from [Google AI Studio](https://aistudio.google.com/).  
2. Create a file named .env in the project root.  
3. Add your API key to the .env file 
```bash
GEMINI_API_KEY = "YOUR_API_KEY_HERE"
```

---

## ▶ How to Run
### 1. Live Web Demo (Recommended)
Access the deployed application directly in your browser:
**[https://pulsevox.streamlit.app/](https://pulsevox.streamlit.app/)**

### 2. Local Web Demo
To run the Streamlit interface on your local machine:
```bash
streamlit run app.py
```

### 3. Local Command Line Demo
To run the original, audio-feedback-in-terminal version:
```bash
python pulsevox.py
```

---

## 🔮 Future Scope

This project has a strong foundation for many advanced features. Here are some potential next steps:

* **Database Integration:** Replace `tasks.json` with a robust database. This would allow for faster queries, better data management, and scalability.
* **Scheduling Intelligence & Calendar Integration:** Connect to Google Calendar or Outlook APIs.
    * Automatically check for *real-world* calendar conflicts.
    * Suggest free time slots for new tasks ("I see you're free at 4 PM, shall I schedule it then?").
* **Proactive Scheduling Assistant:**
    * Learn user habits and make intelligent suggestions (e.g., "You have three meetings in a row. Would you like me to schedule a 15-minute break?").
    * Analyze task lists and suggest priorities based on due dates or keywords.
* **Email Task-Import Engine:** Allow users to forward an email to a special address. The app would use NLP to parse the email, find action items or deadlines, and automatically suggest them as new tasks.
* **Productivity Dashboard:** Add a new tab to the Streamlit app that analyzes and visualizes task data, showing pie charts of task categories or a heatmap of your busiest times.
* **Push Notifications:** Integrate with a service to send email or mobile push notifications 10 minutes before a task's `start_time` is due.
