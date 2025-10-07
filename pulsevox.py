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

import google.generativeai as genai

API_KEY = os.getenv("GEMINI_API_KEY")
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
        return None # Don't print an error, just loop silently
    except sr.RequestError as e:
        console.print(f"[bold red]Speech service error; {e}[/bold red]")
        return None

def get_llm_response(transcribed_text):
    """Sends transcribed text to the LLM and gets structured task data."""
    console.print("[yellow]Analyzing with PulseVox Engine...[/yellow]")
    current_date_str = datetime.now().strftime('%A, %B %d, %Y')
    prompt = f"""
    You are an expert task parsing engine. Your job is to extract events and intents from a user's command.
    The output must be a single, valid JSON object.

    CONTEXT: The current date is {current_date_str}.

    First, determine the user's "intent". It must be one of: "add_task", "query_schedule" (for a whole day), or "query_specific_time".

    - If the intent is "add_task", respond with: {{"intent": "add_task", "tasks": [{{...task_details...}}]}}
    - If the user asks about their schedule for a whole day (e.g., "what's on my schedule tomorrow?"), respond with: {{"intent": "query_schedule", "date_query": "YYYY-MM-DD"}}
    - If the user asks about a specific time (e.g., "am I free at 6pm?"), respond with: {{"intent": "query_specific_time", "date_query": "YYYY-MM-DD", "time_query": "HH:MM"}}

    CRITICAL RULES FOR TIME EXTRACTION:
    1. Resolve all relative dates ("tomorrow", "parson").
    2. Handle Durations: A range like "from 6pm to 8pm" has start_time "18:00" and end_time "20:00".
    3. Default Duration: If only a start time is given (e.g., "call at 6pm"), assume a 30-minute event. (start_time: "18:00", end_time: "18:30").

    User Command: "{transcribed_text}"
    JSON Output:
    """
    try:
        response = llm_model.generate_content(prompt)
        json_response_text = response.text.strip().replace("```json", "").replace("```", "")
        return json_response_text
    except Exception as e:
        console.print(f"[bold red]LLM API Error: {e}[/bold red]")
        return None

def save_tasks(tasks_to_save):
    """Saves new tasks to the JSON file."""
    filename = "tasks.json"; existing_tasks = []
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            try: existing_tasks = json.load(f)
            except json.JSONDecodeError: pass
    for task in tasks_to_save:
        task['timestamp'] = datetime.now().isoformat(); task['status'] = 'pending'
    all_tasks = existing_tasks + tasks_to_save
    with open(filename, 'w') as f:
        json.dump(all_tasks, f, indent=4)
    console.print(f"[bold green]Successfully saved {len(tasks_to_save)} new task(s) to {filename}[/bold green]")

def check_for_conflicts(new_task, all_tasks):
    """Checks if a new task conflicts with any existing tasks on the same day."""
    if not all(k in new_task for k in ["date", "start_time", "end_time"]): return None
    time_format = "%H:%M"
    new_start = datetime.strptime(new_task["start_time"], time_format).time()
    new_end = datetime.strptime(new_task["end_time"], time_format).time()
    for existing_task in all_tasks:
        if existing_task.get("date") == new_task.get("date") and all(k in existing_task for k in ["start_time", "end_time"]):
            existing_start = datetime.strptime(existing_task["start_time"], time_format).time()
            existing_end = datetime.strptime(existing_task["end_time"], time_format).time()
            if new_start < existing_end and new_end > existing_start:
                return existing_task
    return None

def answer_schedule_query(date_query):
    """Reads tasks.json and answers questions about the schedule in chronological order."""
    filename = "tasks.json"
    if not os.path.exists(filename): speak("You don't have any tasks saved yet."); return
    try:
        with open(filename, 'r') as f: all_tasks = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError): speak("I had a problem reading your schedule file."); return
    tasks_for_date = [task for task in all_tasks if task.get('date') == date_query]
    if not tasks_for_date:
        response_text = f"You have nothing scheduled for {date_query}."
    else:
        tasks_for_date.sort(key=lambda x: datetime.strptime(x.get('start_time', '00:00'), "%H:%M"))
        task_descriptions = []
        for task in tasks_for_date:
            desc = task.get('task', 'an unnamed task'); start_time_str = task.get('start_time'); end_time_str = task.get('end_time')
            if start_time_str and end_time_str:
                try:
                    start_time_obj = datetime.strptime(start_time_str, "%H:%M"); end_time_obj = datetime.strptime(end_time_str, "%H:%M")
                    natural_start_time = start_time_obj.strftime("%I:%M %p").lstrip('0'); natural_end_time = end_time_obj.strftime("%I:%M %p").lstrip('0')
                    if (end_time_obj - start_time_obj).seconds > 60: desc += f" from {natural_start_time} to {natural_end_time}"
                    else: desc += f" at {natural_start_time}"
                except ValueError: desc += f" at {start_time_str}"
            task_descriptions.append(desc)
        if len(tasks_for_date) == 1: response_text = f"For {date_query}, you have one task: {task_descriptions[0]}."
        else: response_text = f"For {date_query}, you have {len(tasks_for_date)} tasks: {', and '.join(task_descriptions)}."
    console.print(f"[bold green]Assistant Response:[/bold green] {response_text}"); speak(response_text)

def answer_specific_time_query(date_query, time_query):
    """Checks for a task at a specific time and responds."""
    filename = "tasks.json";
    if not os.path.exists(filename): speak("You don't have any tasks saved yet."); return
    try:
        with open(filename, 'r') as f: all_tasks = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError): speak("I had a problem reading your schedule file."); return
    time_format = "%H:%M"; query_time = datetime.strptime(time_query, time_format).time()
    found_task = None
    for task in all_tasks:
        if task.get("date") == date_query and all(k in task for k in ["start_time", "end_time"]):
            start_time = datetime.strptime(task["start_time"], time_format).time(); end_time = datetime.strptime(task["end_time"], time_format).time()
            if start_time <= query_time < end_time: found_task = task; break
    if found_task:
        task_desc = found_task.get('task'); start_str = datetime.strptime(found_task['start_time'], time_format).strftime("%I:%M %p").lstrip('0'); end_str = datetime.strptime(found_task['end_time'], time_format).strftime("%I:%M %p").lstrip('0')
        response_text = f"Yes, at that time, you have '{task_desc}' scheduled from {start_str} to {end_str}."
    else:
        response_text = f"You appear to be free at {time_query} on {date_query}."
    console.print(f"[bold green]Assistant Response:[/bold green] {response_text}"); speak(response_text)



console.print(Panel.fit("[bold magenta]Welcome to PulseVox 🗣️✨[/bold magenta]\nYour Command-Line Planning Assistant"))

while True:
    command = listen_for_command()
    if command:
        # Check for the exit command *first*, before any other processing.
        if "exit program" in command or "stop listening" in command:
            console.print("[bold yellow]PulseVox signing off. Goodbye![/bold yellow]")
            speak("Goodbye!")
            break # Immediately break the loop and exit.
        
        console.print(f"\n> [bold]You said:[/bold] \"{command}\"\n")
        json_tasks_str = get_llm_response(command)
        
        if json_tasks_str:
            console.print(Panel.fit("[bold blue]--- RESPONSE DATA ---[/bold blue]"))
            syntax = Syntax(json_tasks_str, "json", theme="default", line_numbers=True); console.print(syntax)
            
            try:
                response_data = json.loads(json_tasks_str)
                # Sanitize the intent string to remove any invisible characters.
                raw_intent = response_data.get("intent", "")
                intent = ''.join(char for char in raw_intent if char.isalnum() or char == '_')

                if intent == "query_specific_time":
                    answer_specific_time_query(response_data.get("date_query"), response_data.get("time_query"))
                elif intent == "query_schedule":
                    answer_schedule_query(response_data.get("date_query"))
                elif intent == "add_task":
                    new_tasks = response_data.get("tasks", [])
                    if not new_tasks:
                        speak("I understood you wanted to add a task, but I couldn't extract the details.")
                        continue
                    filename = "tasks.json"; existing_tasks = []
                    if os.path.exists(filename):
                        with open(filename, 'r') as f:
                            try: existing_tasks = json.load(f)
                            except json.JSONDecodeError: pass
                    conflict_found = False
                    for task in new_tasks:
                        conflicting_task = check_for_conflicts(task, existing_tasks)
                        if conflicting_task:
                            conflict_desc = conflicting_task.get('task'); conflict_time = conflicting_task.get('start_time')
                            new_task_desc = task.get('task')
                            suggestion = (f"Hold on. You have a conflict. You want to schedule '{new_task_desc}', but you already have "
                                          f"'{conflict_desc}' at {conflict_time}. I haven't added the new task.")
                            console.print(f"[bold yellow]CONFLICT DETECTED:[/bold yellow] {suggestion}"); speak(suggestion)
                            conflict_found = True
                            break
                    if not conflict_found:
                        save_tasks(new_tasks)
                        task_descriptions = " and ".join([f"'{t.get('task', 'task')}'" for t in new_tasks])
                        confirmation = f"Okay, adding {task_descriptions} to your list."; speak(confirmation)
                else:
                    speak("I'm not sure what you wanted to do with that.")
            except json.JSONDecodeError:
                console.print("[bold red]Error: Could not decode the LLM response.[/bold red]"); speak("Sorry, I had a problem processing that.")
    console.print("\n" + "="*50 + "\n")