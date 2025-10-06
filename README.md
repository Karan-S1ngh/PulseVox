# PulseVox 🗣✨

PulseVox is a smart, command-line voice assistant designed to turn your spoken words into organized, actionable plans.  
This project serves as a powerful proof-of-concept for a frictionless personal planning tool.  
By leveraging modern Speech-to-Text and Large Language Model (LLM) APIs, PulseVox can understand complex, multi-part commands and intelligently extract tasks, appointments, and reminders, saving them directly to a local file.

---

## 🚀 Core Features (MVP)
- **Voice-to-Text Transcription:** Listens to your voice commands and accurately converts them into text.  
- **Intelligent Task Parsing:** Uses a state-of-the-art LLM (like Google's Gemini or OpenAI's GPT) to understand natural language and extract key details from complex sentences.  
- **Multi-Task Recognition:** Say multiple tasks in one go (e.g., “Remind me to call Mom at 5 PM and also buy groceries tomorrow”). PulseVox will identify and separate them.  
- **Entity Extraction:** Automatically identifies categories (To-do, Call, Appointment), dates, and times from your commands.  
- **Audio Feedback:** Provides verbal confirmation once tasks have been successfully processed and saved.  
- **Persistent Storage:** Saves all extracted tasks in a clean, human-readable `tasks.json` file.

---

## 🛠 Technology Stack
- Python 3.8+  
- **Speech-to-Text:** `SpeechRecognition` (Google Web Speech API)  
- **Natural Language Understanding (NLU):** Google Gemini API / OpenAI GPT API  
- **Text-to-Speech:** `gTTS` (Google Text-to-Speech)  
- **Audio Playback:** `playsound`  
- **Terminal Styling:** `rich`

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
> You may need to install *portaudio* for PyAudio to work correctly. Refer to the PyAudio documentation for platform-specific instructions.

### 4️⃣ Configure Your API Key
1. Get your API key from [Google AI Studio](https://aistudio.google.com/) or [OpenAI Platform](https://platform.openai.com/).  
2. Open `pulsevox.py`.  
3. Replace `API_KEY = "YOUR_API_KEY_HERE"` with your actual key.

---

## ▶ How to Run
With your environment activated and API key configured, simply run:
```bash
python pulsevox.py
```
The script will prompt you to speak, transcribe your command, and show the structured tasks it extracted.

---

## 🔮 Future Scope 
- **Custom Wake Word** using Picovoice Porcupine  
- **Conversational Context** memory system  
- **Scheduling Intelligence** with calendar conflict detection  
- **Database Integration** 
- **Web UI** using Streamlit or Gradio  

---