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
import google.generativeai as genai

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    print("ERROR: GEMINI_API_KEY is not set or couldn't be found in .env file.")
    exit()

genai.configure(api_key=API_KEY)
TASK_FILE = "tasks.json" 
console = Console()

# System Prompt (The "Brain's" Rules)
# UPDATED with Hinglish, Category, and Summarize rules
system_prompt = f"""
You are an expert task parsing engine. Your job is to extract events and intents from a user's command.
The output must be a single, valid JSON object.

CONTEXT: The current date is {datetime.now().strftime('%A, %B %d, %Y')}.

CRITICAL: Use the conversation history to resolve pronouns or ambiguous commands. 
For example, if the user says "add a call at 6" and then "move it to 7", you must understand "it" refers to the "call at 6".

CRITICAL: The user may speak in Hinglish (a mix of Hindi and English). Your job is to understand the command and extract the English entities (like 'call mom' or 'tomorrow at 6').

CRITICAL (Hinglish Time): The user will use Hindi words for time. You MUST interpret these and map them to the correct date.
- 'aaj' = today.
- 'kal' = 'tomorrow' . *For scheduling, "kal" ALWAYS means tomorrow, not yesterday.*
- 'parson' = 'day after tomorrow'.
- 'shaam ko' = 'in the evening' (e.g., 19:00).
- 'subah' = 'in the morning' (e.g., 09:00).
- 'dopahar ko' = 'in the afternoon' (e.g., 14:00).
Example 1: "kal shaam ko karaoke" means "karaoke tomorrow in the evening".
Example 2: "parson subah meeting" means "meeting day after tomorrow in the morning".

First, determine the user's "intent". It must be one of: "add_task", "query_schedule", "query_specific_time", "remove_task", "update_task", or "summarize_schedule".

- If "add_task": Respond with a "tasks" list. 
  Each task MUST use keys: "task_description", "date", "start_time", "end_time", and "category".
  The "category" MUST be one of: 'Work', 'Personal', 'Errand', or 'Social'.
  Example: {{"intent": "add_task", "tasks": [{{"task_description": "Call Mom", "date": "2025-10-28", "start_time": "17:00", "end_time": "17:30", "category": "Personal"}}]}}

- If "query_schedule" (e.g., "what's on my schedule tomorrow?"): Respond with: 
  {{"intent": "query_schedule", "date_query": "YYYY-MM-DD"}}

- If "query_specific_time" (e.g., "am I free at 6pm?"): Respond with: 
  {{"intent": "query_specific_time", "date_query": "YYYY-MM-DD", "time_query": "HH:MM"}}

- If "summarize_schedule" (e.g., "summarize my day", "what's my plan?"): Respond with:
  {{"intent": "summarize_schedule", "date_query": "YYYY-MM-DD"}}

- If "remove_task" (e.g., "remove my 6pm call"): Respond with details.
  Example 1: {{"intent": "remove_task", "task_details": {{"date": "2025-10-27", "start_time": "18:00"}}}}

- If "update_task" (e.g., "move my 6pm call to 7"): 
  You MUST find the original task using context.
  You MUST extract the *new* details.
  The output MUST have two keys: "find_details" (to locate the old task) and "update_details" (the new info).
  Example 1: {{"intent": "update_task", "find_details": {{"task_description": "call", "start_time": "18:00"}}, "update_details": {{"start_time": "19:00", "end_time": "19:30"}}}}

CRITICAL RULES FOR TIME EXTRACTION:
1. Resolve all relative dates ("tomorrow", "today").
2. Handle Durations: "from 6pm to 8pm" -> start_time "18:00", end_time "20:00".
3. Default Duration: "at 6pm" -> start_time "18:00", end_time "18:30".

The user's command will follow. Respond ONLY with the valid JSON object.
"""

llm_model = genai.GenerativeModel(
    'models/gemini-2.5-flash',
    system_instruction=system_prompt
)
chat_session = llm_model.start_chat(history=[])

summarizer_system_prompt = "You are a helpful assistant. You answer user requests in natural, conversational language. You do NOT output JSON."
summarizer_model = genai.GenerativeModel(
    'models/gemini-2.5-flash',
    system_instruction=summarizer_system_prompt
)

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
        console.print("[bold cyan]Listening...[/bold cyan]")
        try:
            audio = r.listen(source, timeout=7, phrase_time_limit=30)
        except sr.WaitTimeoutError:
            return None
    try:
        console.print("[yellow]Recognizing speech...[/yellow]")
        # This "en-IN" locale is key for Hinglish support
        command = r.recognize_google(audio, language="en-IN")
        return command.lower()
    except sr.UnknownValueError:
        return None 
    except sr.RequestError as e:
        console.print(f"[bold red]Speech service error; {e}[/bold red]")
        return None

def get_llm_response(transcribed_text):
    """Sends transcribed text to the global chat session and gets structured task data."""
    console.print("[yellow]Analyzing with PulseVox Engine...[/yellow]")
    try:
        response = chat_session.send_message(transcribed_text)
        json_response_text = response.text.strip().lstrip("```json").rstrip("```").strip()
        return json_response_text
    except Exception as e:
        console.print(f"[bold red]LLM API Error: {e}[/bold red]")
        return None

def get_task_description(task_dict, fallback="an unnamed task"):
    """Gets the task description from various possible keys."""
    if not task_dict: return fallback
    return task_dict.get('task_description') or \
           task_dict.get('task') or \
           task_dict.get('title') or \
           task_dict.get('description') or \
           fallback

def load_all_tasks():
    """Loads all tasks from the JSON file."""
    if os.path.exists(TASK_FILE):
        with open(TASK_FILE, 'r') as f:
            try: 
                return json.load(f)
            except json.JSONDecodeError: 
                return []
    return []

def save_all_tasks(all_tasks):
    """Saves the entire task list back to the JSON file."""
    try:
        with open(TASK_FILE, 'w') as f:
            json.dump(all_tasks, f, indent=4)
        return True
    except Exception as e:
        console.print(f"[bold red]Error saving tasks: {e}[/bold red]")
        return False

def check_for_conflicts(new_task, all_tasks):
    """Checks if a new task conflicts with any existing tasks on the same day."""
    if not all(k in new_task for k in ["date", "start_time", "end_time"]): return None
    time_format = "%H:%M"
    try:
        new_start = datetime.strptime(new_task["start_time"], time_format).time()
        new_end = datetime.strptime(new_task["end_time"], time_format).time()
    except ValueError:
        return None 
    for existing_task in all_tasks:
        if existing_task.get("date") == new_task.get("date") and all(k in existing_task for k in ["start_time", "end_time"]):
            try:
                existing_start = datetime.strptime(existing_task["start_time"], time_format).time()
                existing_end = datetime.strptime(existing_task["end_time"], time_format).time()
                if new_start < existing_end and new_end > existing_start:
                    return existing_task
            except ValueError:
                continue
    return None

def answer_schedule_query(date_query):
    """Reads tasks.json and answers questions about the schedule in chronological order."""
    all_tasks = load_all_tasks()
    if not all_tasks: 
        speak("You don't have any tasks saved yet."); return
    
    tasks_for_date = [task for task in all_tasks if task.get('date') == date_query]
    
    if not tasks_for_date:
        response_text = f"You have nothing scheduled for {date_query}."
    else:
        tasks_for_date.sort(key=lambda x: datetime.strptime(x.get('start_time', '00:00'), "%H:%M"))
        task_descriptions = []
        for task in tasks_for_date:
            desc = get_task_description(task)
            start_time_str = task.get('start_time'); end_time_str = task.get('end_time')
            if start_time_str and end_time_str:
                try:
                    start_time_obj = datetime.strptime(start_time_str, "%H:%M"); end_time_obj = datetime.strptime(end_time_str, "%H:%M")
                    natural_start_time = start_time_obj.strftime("%I:%M %p").lstrip('0'); natural_end_time = end_time_obj.strftime("%I:%M %p").lstrip('0')
                    if (end_time_obj - start_time_obj).seconds > 60: 
                        desc += f" from {natural_start_time} to {natural_end_time}"
                    else:
                        desc += f" at {natural_start_time}"
                except ValueError:
                    desc += f" at {start_time_str}" 
            task_descriptions.append(desc)

        if len(tasks_for_date) == 1:
            response_text = f"For {date_query}, you have one task: {task_descriptions[0]}."
        else:
            joined_tasks = ", ".join(task_descriptions[:-1]) + f", and {task_descriptions[-1]}"
            response_text = f"For {date_query}, you have {len(tasks_for_date)} tasks: {joined_tasks}."
    console.print(f"[bold green]Assistant Response:[/bold green] {response_text}"); speak(response_text)

def answer_specific_time_query(date_query, time_query):
    """Checks for a task at a specific time and responds."""
    all_tasks = load_all_tasks()
    if not all_tasks: 
        speak("You don't have any tasks saved yet."); return

    try:
        time_format = "%H:%M"; query_time = datetime.strptime(time_query, time_format).time()
    except ValueError:
        speak(f"Sorry, I didn't understand the time {time_query}."); return

    found_task = None
    for task in all_tasks:
        if task.get("date") == date_query and all(k in task for k in ["start_time", "end_time"]):
            try:
                start_time = datetime.strptime(task["start_time"], time_format).time(); end_time = datetime.strptime(task["end_time"], time_format).time()
                if start_time <= query_time < end_time:
                    found_task = task; break
            except ValueError:
                continue 

    if found_task:
        task_desc = get_task_description(found_task)
        start_str = datetime.strptime(found_task['start_time'], time_format).strftime("%I:%M %p").lstrip('0')
        end_str = datetime.strptime(found_task['end_time'], time_format).strftime("%I:%M %p").lstrip('0')
        response_text = f"Yes, at that time, you have '{task_desc}' scheduled from {start_str} to {end_str}."
    else:
        natural_query_time = datetime.strptime(time_query, time_format).strftime("%I:%M %p").lstrip('0')
        response_text = f"You appear to be free at {natural_query_time} on {date_query}."
    console.print(f"[bold green]Assistant Response:[/bold green] {response_text}"); speak(response_text)

def handle_task_removal(task_details, all_tasks):
    """Finds and removes the *best matching* task from the JSON file."""
    if not task_details:
        return "Sorry, I didn't catch the details of the task you want to remove."

    desc_to_match = (task_details.get('task_description') or task_details.get('title') or task_details.get('description') or "").lower()
    time_to_match = task_details.get('start_time')
    date_to_match = task_details.get('date') 
    best_score, best_match_index = -1, -1

    for i, task in enumerate(all_tasks):
        current_score = 0
        task_desc = get_task_description(task, "").lower()
        task_start = task.get('start_time')
        task_date = task.get('date')

        if desc_to_match and desc_to_match in task_desc: current_score += 10
        if date_to_match and date_to_match == task_date: current_score += 5
        if time_to_match and task_start:
            try:
                time_format = "%H:%M"
                llm_time = datetime.strptime(time_to_match, time_format)
                task_time = datetime.strptime(task_start, time_format)
                time_diff_minutes = abs((llm_time - task_time).total_seconds() / 60)
                if time_diff_minutes == 0: current_score += 3
                elif time_diff_minutes <= 30: current_score += 2
            except ValueError: pass 

        if current_score > best_score:
            best_score = current_score
            best_match_index = i

    if best_match_index != -1 and best_score >= 10:
        removed_task = all_tasks.pop(best_match_index)
        task_desc = get_task_description(removed_task)
        if save_all_tasks(all_tasks):
            return f"Okay, I've removed '{task_desc}' from your schedule."
        else:
            return "Found task, but failed to save updated file."
    else:
        return "Sorry, I couldn't find that specific task to remove."

def handle_task_update(find_details, update_details, all_tasks):
    """Finds the best-matching task and applies updates."""
    if not find_details or not update_details:
        return "Sorry, I didn't catch what you wanted to change or what you wanted to change it to."

    # Find the task (using the same logic as remove)
    desc_to_match = (find_details.get('task_description') or "").lower()
    time_to_match = find_details.get('start_time')
    date_to_match = find_details.get('date')
    best_score, best_match_index = -1, -1

    for i, task in enumerate(all_tasks):
        current_score = 0
        task_desc = get_task_description(task, "").lower()
        task_start = task.get('start_time')
        task_date = task.get('date')

        if desc_to_match and desc_to_match in task_desc: current_score += 10
        if date_to_match and date_to_match == task_date: current_score += 5
        if time_to_match and task_start:
            try:
                time_format = "%H:%M"
                llm_time = datetime.strptime(time_to_match, time_format)
                task_time = datetime.strptime(task_start, time_format)
                time_diff_minutes = abs((llm_time - task_time).total_seconds() / 60)
                if time_diff_minutes == 0: current_score += 3
                elif time_diff_minutes <= 30: current_score += 2
            except ValueError: pass
        
        if current_score > best_score:
            best_score = current_score
            best_match_index = i

    # Update the task if found
    if best_match_index != -1 and best_score >= 10:
        task_to_update = all_tasks[best_match_index]
        original_desc = get_task_description(task_to_update)
        
        # Apply all updates from the LLM
        for key, value in update_details.items():
            task_to_update[key] = value
        
        if save_all_tasks(all_tasks):
            updated_desc = get_task_description(task_to_update)
            return f"Okay, I've updated '{original_desc}' to '{updated_desc}'."
        else:
            return "Found task, but failed to save updated file."
    else:
        return "Sorry, I couldn't find the task you wanted to update."

# NEW FUNCTION FOR SUMMARIZATION
def handle_summarization(date_query):
    """Loads tasks for a day and asks the SUMMARIZER LLM to review them."""
    all_tasks = load_all_tasks()
    if not all_tasks: 
        return "You don't have any tasks saved yet."
    
    tasks_for_date = [task for task in all_tasks if task.get('date') == date_query]
    
    if not tasks_for_date:
        return f"You have nothing scheduled for {date_query}."
    
    # Prepare a simple list of tasks for the summarizer
    tasks_for_date.sort(key=lambda x: datetime.strptime(x.get('start_time', '00:00'), "%H:%M"))
    task_descriptions = []
    for task in tasks_for_date:
        desc = get_task_description(task)
        start = task.get('start_time', 'all day')
        task_descriptions.append(f"- {desc} at {start}")
    
    tasks_str = "\n".join(task_descriptions)
    
    # Send to the separate SUMMARIZER model
    console.print("[yellow]Generating summary...[/yellow]")
    try:
        summary_prompt = (f"Here is a list of my tasks for {date_query}:\n{tasks_str}\n\n"
                          f"Please write a brief, natural language summary of my day (in one or two sentences).")
        
        # Use the new, "vanilla" model that isn't locked to JSON output
        response = summarizer_model.generate_content(summary_prompt) 
        
        return response.text.strip()
    except Exception as e:
        console.print(f"[bold red]Summarization LLM Error: {e}[/bold red]")
        return "I found your tasks but had trouble summarizing them."


if __name__ == "__main__":
    console.print(Panel.fit("[bold magenta]Welcome to PulseVox 🗣️✨[/bold magenta]\nYour Command-Line Planning Assistant"))

    while True:
        command = listen_for_command()
        if command:
            if "exit program" in command or "stop listening" in command or "goodbye" in command:
                console.print("[bold yellow]PulseVox signing off. Goodbye![/bold yellow]")
                speak("Goodbye!")
                break 
            
            console.print(f"\n> [bold]You said:[/bold] \"{command}\"\n")
            json_tasks_str = get_llm_response(command)
            
            if json_tasks_str:
                console.print(Panel.fit("[bold blue]--- RESPONSE DATA ---[/bold blue]"))
                syntax = Syntax(json_tasks_str, "json", theme="monokai", line_numbers=True); console.print(syntax)
                
                try:
                    response_data = json.loads(json_tasks_str)
                    intent = response_data.get("intent", "")
                    response_text = "" # To store the spoken response
                    all_tasks = load_all_tasks() # Load tasks once per command

                    if intent == "query_specific_time":
                        if not all(k in response_data for k in ["date_query", "time_query"]):
                            response_text = "I understood you were asking about a time, but I missed the date or time."
                        else:
                            answer_specific_time_query(response_data.get("date_query"), response_data.get("time_query"))
                    
                    elif intent == "query_schedule":
                        if not response_data.get("date_query"):
                            response_text = "I understood you were asking about your schedule, but I missed which day."
                        else:
                            answer_schedule_query(response_data.get("date_query"))
                    
                    # Handle Summarization
                    elif intent == "summarize_schedule":
                        date_query = response_data.get("date_query")
                        if not date_query:
                            response_text = "I understood you wanted a summary, but I missed which day."
                        else:
                            response_text = handle_summarization(date_query)
                    
                    elif intent == "remove_task":
                        task_details = response_data.get("task_details")
                        response_text = handle_task_removal(task_details, all_tasks)
                    
                    elif intent == "update_task":
                        find_details = response_data.get("find_details")
                        update_details = response_data.get("update_details")
                        response_text = handle_task_update(find_details, update_details, all_tasks)
                            
                    elif intent == "add_task":
                        # Category is now automatically handled by the LLM
                        new_tasks = response_data.get("tasks", [])
                        if not new_tasks:
                            response_text = "I understood you wanted to add a task, but I couldn't extract the details."
                        else:
                            conflict_found = False
                            tasks_to_add = []
                            for task in new_tasks:
                                task['timestamp'] = datetime.now().isoformat(); task['status'] = 'pending'
                                conflicting_task = check_for_conflicts(task, all_tasks + tasks_to_add) 
                                if conflicting_task:
                                    conflict_desc = get_task_description(conflicting_task)
                                    new_task_desc = get_task_description(task)
                                    response_text = (f"Hold on. You have a conflict. You want to schedule '{new_task_desc}', but you already have "
                                                    f"'{conflict_desc}'. I haven't added the new task.")
                                    conflict_found = True
                                    break 
                                else:
                                    tasks_to_add.append(task) 

                            if not conflict_found and tasks_to_add:
                                all_tasks.extend(tasks_to_add) 
                                if save_all_tasks(all_tasks): 
                                    task_descriptions = " and ".join([f"'{get_task_description(t)}'" for t in tasks_to_add])
                                    response_text = f"Okay, adding {task_descriptions} to your list."
                                else:
                                    response_text = "I extracted the tasks, but there was an error saving the file."
                    
                    else:
                        response_text = "I'm not sure what you wanted to do with that."
                    
                    # Speak and print the response if one was generated
                    if response_text:
                        console.print(f"[bold green]Assistant Response:[/bold green] {response_text}")
                        speak(response_text)
                
                except json.JSONDecodeError:
                    console.print("[bold red]Error: Could not decode the LLM response.[/bold red]"); 
                    speak("Sorry, I had a problem processing that.")
            
            else:
                console.print("[bold red]Error: The PulseVox Engine (LLM) failed to respond.[/bold red]")
                speak("I'm having trouble connecting to my brain right now. Please try again in a moment.")
        
        else:
            console.print("[dim]Didn't catch that. Listening again...[/dim]")

        console.print("\n" + "="*50 + "\n")
        