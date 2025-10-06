import os
import json
from datetime import datetime
import speech_recognition as sr
from gtts import gTTS
from playsound import playsound
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- LLM Integration ---
import google.generativeai as genai

# --- Configuration ---
API_KEY = os.getenv("GEMINI_API_KEY") # Note: Changed to GEMINI_API_KEY to match .env standard
LLM_PROVIDER = "google"

# Configure the LLM provider
if LLM_PROVIDER == "google":
    if not API_KEY:
        print("ERROR: GEMINI_API_KEY is not set or couldn't be found in .env file.")
        exit()
    genai.configure(api_key=API_KEY)
    llm_model = genai.GenerativeModel('models/gemini-2.5-flash-preview-05-20')

# Initialize Rich Console for beautiful terminal output
console = Console()

# --- Function Definitions ---

def speak(text, lang='en'):
    """Converts text to speech and plays it."""
    try:
        tts = gTTS(text=text, lang=lang, slow=False)
        filename = "response.mp3"
        tts.save(filename)
        playsound(filename)
        os.remove(filename)
    except Exception as e:
        console.print(f"[bold red]Error in text-to-speech: {e}[/bold red]")

def listen_for_command():
    """Listens for a command from the user and returns the transcribed text."""
    r = sr.Recognizer()
    with sr.Microphone() as source:
        r.adjust_for_ambient_noise(source, duration=1)
        console.print("[bold cyan]Listening... Please speak your command.[/bold cyan]")
        try:
            audio = r.listen(source, timeout=5, phrase_time_limit=15)
        except sr.WaitTimeoutError:
            return None

    try:
        console.print("[yellow]Recognizing speech...[/yellow]")
        command = r.recognize_google(audio, language="en-IN")
        return command.lower()
    except sr.UnknownValueError:
        console.print("[bold red]Sorry, I could not understand the audio.[/bold red]")
        return None
    except sr.RequestError as e:
        console.print(f"[bold red]Speech service error; {e}[/bold red]")
        return None

def get_llm_response(transcribed_text):
    """Sends transcribed text to the LLM and gets structured task data."""
    console.print("[yellow]Analyzing with PulseVox Engine...[/yellow]")
    
    prompt = f"""
    You are an expert task parsing engine for a voice assistant named PulseVox.
    The user might speak in English, Hindi, or Hinglish. Your job is to extract tasks from the user's spoken command.
    The output must be a valid JSON list of objects. Do not output anything other than the JSON list.

    **CRITICAL RULE**: You must translate common Hindi/Hinglish time and date words into their English equivalents.
    For example:
    - "kal" should be interpreted as "tomorrow" for future tasks.
    - "parson" means "the day after tomorrow".
    - "shaam ko" means "in the evening".
    - "subah" means "in the morning".
    - "kal shaam ko" would mean "tomorrow evening".

    For each task, extract:
    - "task": A concise description of the task in English.
    - "category": Classify the task into one of: 'To-do', 'Appointment', 'Call', 'Reminder', 'Shopping'.
    - "details": Any specific names, topics, or locations.
    - "time": The specific time or date mentioned, translated into English.

    User Command: "{transcribed_text}"

    JSON Output:
    """

    try:
        if LLM_PROVIDER == "google":
            response = llm_model.generate_content(prompt)
            json_response_text = response.text.strip().replace("```json", "").replace("```", "")
            return json_response_text
    except Exception as e:
        console.print(f"[bold red]LLM API Error: {e}[/bold red]")
        return None

def save_tasks(tasks):
    """Saves the extracted tasks to a JSON file."""
    filename = "tasks.json"
    existing_tasks = []
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            try:
                existing_tasks = json.load(f)
            except json.JSONDecodeError:
                pass
    
    for task in tasks:
        task['timestamp'] = datetime.now().isoformat()
        task['status'] = 'pending'
    
    all_tasks = existing_tasks + tasks

    with open(filename, 'w') as f:
        json.dump(all_tasks, f, indent=4)
    
    console.print(f"[bold green]Successfully saved {len(tasks)} new task(s) to {filename}[/bold green]")


# --- Main Application Logic (Runs directly at the script level) ---

console.print(Panel.fit("[bold magenta]Welcome to PulseVox 🗣️✨[/bold magenta]\nYour Command-Line Planning Assistant"))

# This loop will run forever until you stop it
while True:
    command = listen_for_command()

    if command:
        # Add a check to exit the loop
        if "exit program" in command or "stop listening" in command:
            console.print("[bold yellow]PulseVox signing off. Goodbye![/bold yellow]")
            speak("Goodbye!")
            break # This breaks out of the while loop

        console.print(f"\n> [bold]You said:[/bold] \"{command}\"\n")
        json_tasks_str = get_llm_response(command)
        
        if json_tasks_str:
            console.print(Panel.fit("[bold blue]--- TASKS EXTRACTED ---[/bold blue]"))
            syntax = Syntax(json_tasks_str, "json", theme="default", line_numbers=True)
            console.print(syntax)
            
            try:
                tasks = json.loads(json_tasks_str)
                if isinstance(tasks, list) and tasks:
                    save_tasks(tasks)
                    task_descriptions = " and ".join([f"'{t.get('task', 'task')}'" for t in tasks])
                    confirmation_message = f"Okay, adding {task_descriptions} to your list."
                    speak(confirmation_message)
                else:
                    speak("I didn't find any specific tasks to add.")
            except json.JSONDecodeError:
                console.print("[bold red]Error: Could not decode the LLM response.[/bold red]")
                speak("Sorry, I had a problem processing that.")
    else:
        # Don't print "No command received" every time, just loop silently
        pass 

    # Add a small separator for the next command
    console.print("\n" + "="*50 + "\n")