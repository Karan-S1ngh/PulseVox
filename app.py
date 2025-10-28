import streamlit as st
import os
import json
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
import google.generativeai as genai
import speech_recognition as sr
import io
from streamlit_mic_recorder import mic_recorder
from pydub import AudioSegment
from gtts import gTTS
# import glob # For finding FFmpeg

try:
    from pulsevox import (
        system_prompt, 
        get_task_description,
        load_all_tasks,
        save_all_tasks,
        check_for_conflicts,
        handle_task_removal,
        handle_task_update,
    )
except ImportError:
    st.error("Could not import functions from pulsevox.py. Make sure it's in the same directory.")
    st.stop()


load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
# if not API_KEY:
#     st.error("ERROR: GEMINI_API_KEY is not set or couldn't be found in .env file.")
#     # st.stop()

genai.configure(api_key=API_KEY)
TASK_FILE = "tasks.json"

# username = os.getlogin() # Get current username
# # Ensure the path uses raw string or escaped backslashes
# # Use glob to find the specific version folder as it might change
# ffmpeg_winget_path_pattern = rf"C:\Users\{username}\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_*\ffmpeg-*-full_build\bin\ffmpeg.exe"

# ffmpeg_paths = glob.glob(ffmpeg_winget_path_pattern)
# ffmpeg_path_to_set = None
# if ffmpeg_paths:
#     # Sort paths to get the latest version if multiple exist (though unlikely for same package ID)
#     ffmpeg_paths.sort(reverse=True)
#     ffmpeg_path_to_set = ffmpeg_paths[0] # Use the first (potentially latest) match
#     try:
#         AudioSegment.converter = ffmpeg_path_to_set
#         # st.sidebar.info(f"Using FFmpeg found at: {ffmpeg_path_to_set}") # Optional confirmation in sidebar
#     except Exception as e:
#         st.sidebar.error(f"Error setting FFmpeg path ({ffmpeg_path_to_set}): {e}. Make sure FFmpeg is correctly installed and accessible.")
#         ffmpeg_path_to_set = None # Indicate failure

# if not ffmpeg_path_to_set:
#     # If winget path failed or not found, try relying on PATH
#     try:
#         # pydub checks PATH by default if AudioSegment.converter is not set
#          # Attempt a dummy conversion to see if it works via PATH
#          dummy_input = io.BytesIO(b'\0'*100) # Create dummy bytes
#          # Need format, rate, channels, width for raw data
#          AudioSegment.from_file(dummy_input, format="raw", frame_rate=44100, channels=1, sample_width=1)
#          # st.sidebar.info("Using FFmpeg found in system PATH.") # Optional
#     except Exception as e:
#          st.sidebar.error(f"FFmpeg not found via winget or system PATH. Audio conversion will fail. Please install FFmpeg and add it to PATH. Details: {e}")
#          # Consider st.stop() if FFmpeg is absolutely essential

def initialize_state():
    """Initializes the models and chat history in Streamlit's session state."""
    # Initialize only if 'initialized' flag is not set
    if "initialized" not in st.session_state:
        try:
            # 1. The JSON Expert (Main Brain)
            json_model = genai.GenerativeModel(
                'models/gemini-2.5-flash',
                system_instruction=system_prompt # Use imported variable
            )
            st.session_state.chat_session = json_model.start_chat(history=[])

            # 2. The Text Summarizer (Generalist)
            summarizer_prompt = "You are a helpful assistant. You answer user requests in natural, conversational language. You do NOT output JSON."
            st.session_state.summarizer_model = genai.GenerativeModel(
                'models/gemini-2.5-flash',
                system_instruction=summarizer_prompt
            )

            # 3. The chat history for display
            st.session_state.history = []

            # 4. Speech Recognizer
            st.session_state.recognizer = sr.Recognizer()

            # 5. State flags for audio processing
            st.session_state.audio_command_ready = None # None: no audio, "": failed trans, str: ready
            st.session_state.history = []
            
            # 6. Set initialized flag
            st.session_state.message_to_speak = None
            st.session_state.initialized = True

        except Exception as e:
            st.error(f"Failed to initialize Gemini model: {e}")
            # Potentially stop the app if initialization fails critically
            st.stop()

def transcribe_audio(audio_dict):
    """Transcribes audio bytes from the web recorder's output dict."""
    if not audio_dict or 'bytes' not in audio_dict:
        return None

    # Ensure recognizer is initialized
    if "recognizer" not in st.session_state:
        st.error("Speech recognizer not initialized.")
        return None
    r = st.session_state.recognizer
    audio_bytes = audio_dict['bytes']

    try:
        # 1. Load the web-format audio bytes
        input_audio = io.BytesIO(audio_bytes)
        # Explicitly state format if known, otherwise let pydub guess
        sound = AudioSegment.from_file(input_audio) # pydub often guesses webm/ogg correctly

        # 2. Create an in-memory WAV file
        output_wav = io.BytesIO()
        sound.export(output_wav, format="wav")
        output_wav.seek(0)
    except Exception as e:
        st.error(f"Audio conversion error (check FFmpeg installation/path): {e}")
        return None

    try:
        # 3. Read the WAV file
        with sr.AudioFile(output_wav) as source:
            # Adjust for ambient noise (though less effective on file vs mic)
            # r.adjust_for_ambient_noise(source, duration=0.5) # Optional: Can sometimes help
            audio_data = r.record(source)

        # 4. Transcribe
        text = r.recognize_google(audio_data, language="en-IN")
        return text.lower()
    except sr.UnknownValueError:
        st.warning("Speech Recognition could not understand audio.")
        return None
    except sr.RequestError as e:
        st.error(f"Speech service error; {e}")
        return None
    
def speak_web(text_to_speak):
    """Generates speech audio and embeds it in Streamlit."""
    if not text_to_speak: # Don't try to speak if message is empty
        return
    try:
        tts = gTTS(text=text_to_speak, lang='en', slow=False)
        # Create an in-memory file-like object
        mp3_fp = io.BytesIO()
        tts.write_to_fp(mp3_fp)
        # Reset the stream position to the beginning
        mp3_fp.seek(0)
        # Embed the audio player
        st.audio(mp3_fp, format='audio/mp3', start_time=0)
    except Exception as e:
        st.error(f"Error generating or playing audio feedback: {e}")

def handle_web_schedule_query(date_query):
    """Web-friendly version: Returns text instead of speaking."""
    all_tasks = load_all_tasks()
    if not all_tasks: 
        return "You don't have any tasks saved yet."
    tasks_for_date = [task for task in all_tasks if task.get('date') == date_query]
    if not tasks_for_date: 
        return f"You have nothing scheduled for {date_query}."
    tasks_for_date.sort(key=lambda x: datetime.strptime(x.get('start_time', '00:00'), "%H:%M"))
    task_descriptions = []
    for task in tasks_for_date:
        desc = get_task_description(task)
        start_time_str = task.get('start_time'); end_time_str = task.get('end_time')
        if start_time_str and end_time_str:
            try:
                start_obj = datetime.strptime(start_time_str, "%H:%M")
                end_obj = datetime.strptime(end_time_str, "%H:%M")
                start_natural = start_obj.strftime("%I:%M %p").lstrip('0')
                end_natural = end_obj.strftime("%I:%M %p").lstrip('0')
                if (end_obj - start_obj).total_seconds() > 60: # Use total_seconds() for reliability
                    desc += f" from {start_natural} to {end_natural}"
                else:
                    desc += f" at {start_natural}"
            except ValueError: desc += f" at {start_time_str}"
        task_descriptions.append(desc)
    if len(tasks_for_date) == 1:
        return f"For {date_query}, you have one task: {task_descriptions[0]}."
    else:
        # Handle cases with 2 tasks correctly
        if len(task_descriptions) == 2:
             joined_tasks = f"{task_descriptions[0]} and {task_descriptions[1]}"
        elif len(task_descriptions) > 2:
             joined_tasks = ", ".join(task_descriptions[:-1]) + f", and {task_descriptions[-1]}"
        else: # Should not happen if tasks_for_date is not empty, but good fallback
             joined_tasks = task_descriptions[0] if task_descriptions else "nothing"
        return f"For {date_query}, you have {len(tasks_for_date)} tasks: {joined_tasks}."

def handle_web_specific_time_query(date_query, time_query):
    """Web-friendly version: Returns text instead of speaking."""
    all_tasks = load_all_tasks()
    if not all_tasks: 
        return "You don't have any tasks saved yet."
    try:
        time_format = "%H:%M"; query_time = datetime.strptime(time_query, time_format).time()
    except ValueError: 
        return f"Sorry, I didn't understand the time {time_query}."
    found_task = None
    for task in all_tasks:
        # Check date and ensure time keys exist before parsing
        if task.get("date") == date_query and all(k in task for k in ["start_time", "end_time"]):
            try:
                start_time = datetime.strptime(task["start_time"], time_format).time()
                end_time = datetime.strptime(task["end_time"], time_format).time()
                # Check for overlap: query time is within [start_time, end_time)
                if start_time <= query_time < end_time:
                    found_task = task; break
            except ValueError: 
                continue # Ignore tasks with invalid time format
    if found_task:
        task_desc = get_task_description(found_task)
        start_str = datetime.strptime(found_task['start_time'], time_format).strftime("%I:%M %p").lstrip('0')
        end_str = datetime.strptime(found_task['end_time'], time_format).strftime("%I:%M %p").lstrip('0')
        return f"Yes, at that time, you have '{task_desc}' scheduled from {start_str} to {end_str}."
    else:
        natural_query_time = datetime.strptime(time_query, time_format).strftime("%I:%M %p").lstrip('0')
        return f"You appear to be free at {natural_query_time} on {date_query}."

# Wrapper for summarization to pass the correct model from state
def handle_web_summarization(date_query):
    """Web-friendly version: Returns summary text."""
    if "summarizer_model" not in st.session_state:
        return "Summarizer model not initialized."

    all_tasks = load_all_tasks()
    if not all_tasks: 
        return "You don't have any tasks saved yet."
    tasks_for_date = [task for task in all_tasks if task.get('date') == date_query]
    if not tasks_for_date: 
        return f"You have nothing scheduled for {date_query}."
    tasks_for_date.sort(key=lambda x: datetime.strptime(x.get('start_time', '00:00'), "%H:%M"))
    task_descriptions = [f"- {get_task_description(task)} at {task.get('start_time', 'all day')}" for task in tasks_for_date]
    tasks_str = "\n".join(task_descriptions)
    try:
        summary_prompt = (f"Here is a list of my tasks for {date_query}:\n{tasks_str}\n\n"
                           f"Please write a brief, natural language summary of my day (in one or two sentences).")
        response = st.session_state.summarizer_model.generate_content(summary_prompt)
        return response.text.strip()
    except Exception as e:
        return f"I found your tasks but had trouble summarizing them: {e}"

# Streamlit UI
st.set_page_config(layout="wide", page_title="PulseVox Demo")
st.title("PulseVox 🗣️✨ - Prototype Demo Interface")

# Initialize the chat session and models (runs only once)
initialize_state()

# Define the two-column layout
col1, col2 = st.columns([1, 1.2]) # Adjust column width ratio if needed

# Column 1: Control Panel & History 
# Ensure this block only appears ONCE
with col1:
    st.header("Control Panel")

    st.write("Click the button to record your command:")
    audio_info = mic_recorder(
        start_prompt="Start Recording 🎤",
        stop_prompt="Stop Recording 🛑",
        key='recorder', # Unique key for the component
        format="webm" # Specify format if known, helps pydub
    )

    # Initialize state flags if they don't exist (redundant due to initialize_state, but safe)
    if "audio_command_ready" not in st.session_state:
        st.session_state.audio_command_ready = None

    #  Step 1: Handle Audio Recording Output 
    if audio_info:
        # Check if this audio has already been processed in this run
        # Use audio_info['id'] if available and unique, otherwise rely on audio_command_ready state
        audio_id = audio_info.get('id', None) # Get unique ID if provided by component
        if "last_processed_audio_id" not in st.session_state:
            st.session_state.last_processed_audio_id = None

        # Process only if it's new audio or state allows
        if st.session_state.audio_command_ready is None and \
           (audio_id is None or audio_id != st.session_state.last_processed_audio_id):

            with st.spinner("Transcribing audio..."):
                transcribed_text = transcribe_audio(audio_info)
                if transcribed_text:
                    st.info(f"You said: \"{transcribed_text}\"")
                    # Store the command to be processed on the *next* rerun
                    st.session_state.audio_command_ready = transcribed_text
                    if audio_id: st.session_state.last_processed_audio_id = audio_id
                else:
                    # Warning shown by transcribe_audio
                    st.session_state.audio_command_ready = "" # Use empty string to indicate handled failure

            # Rerun *once* after transcription to trigger processing below
            st.rerun()

    #  Step 2: Check if Audio Command Needs Processing 
    command_to_process = ""
    process_now = False

    if st.session_state.audio_command_ready: # Check if not None and not empty string
        command_to_process = st.session_state.audio_command_ready
        process_now = True
        st.session_state.audio_command_ready = None # Reset state *before* processing

    #  Step 3: Text Input & Manual Process Button 
    user_command_text = st.text_input(
        "Enter command (or edit transcription):",
        # Show transcribed text only if it's ready for processing
        value=command_to_process if process_now else "",
        placeholder="e.g., 'Add meeting kal shaam ko' or 'move it to 7'",
        key="user_input_text_area" # Use a distinct key
    )

    # Allow processing via button ONLY if audio wasn't just processed
    if not process_now and st.button("Process Command 🚀", type="primary"):
        if user_command_text:
            command_to_process = user_command_text
            process_now = True
            # Clear any leftover audio state if text is used
            st.session_state.audio_command_ready = None

        else:
            st.warning("Please enter or record a command.")

    #  Step 4: Processing Logic 
    if process_now and command_to_process:
        with st.spinner("Analyzing with PulseVox Engine..."):
            assistant_message = ""
            try:
                # 1. Get JSON response
                if "chat_session" not in st.session_state:
                     st.error("Chat session not initialized.")
                     st.stop() # Stop execution if chat session isn't ready
                chat_session = st.session_state.chat_session
                response = chat_session.send_message(command_to_process)
                json_response_text = response.text.strip().lstrip("```json").rstrip("```").strip()
                # Attempt to load JSON immediately to catch errors early
                response_data = json.loads(json_response_text)

                # 2. Add to history
                if "history" not in st.session_state: st.session_state.history = []
                st.session_state.history.append({
                    "user": command_to_process,
                    "json": json_response_text # Store the raw JSON string
                })

                # 3. Handle the intent
                intent = response_data.get("intent", "")
                assistant_message = ""
                all_tasks = load_all_tasks() # Load fresh task list

                #  Intent Handling Logic 
                if intent == "add_task":
                    new_tasks = response_data.get("tasks", [])
                    if not new_tasks:
                        assistant_message = "I understood you wanted to add a task, but couldn't extract details."
                    else:
                        conflict_found = False; tasks_to_add = []
                        for task in new_tasks:
                            # Add metadata before checking conflicts
                            task['timestamp'] = datetime.now().isoformat(); task['status'] = 'pending'
                            conflicting_task = check_for_conflicts(task, all_tasks + tasks_to_add)
                            if conflicting_task:
                                conflict_desc = get_task_description(conflicting_task)
                                new_task_desc = get_task_description(task)
                                assistant_message = f"❌ **CONFLICT:** Can't add '{new_task_desc}', it conflicts with '{conflict_desc}'."
                                conflict_found = True; break
                            else:
                                tasks_to_add.append(task)
                        if not conflict_found and tasks_to_add:
                            all_tasks.extend(tasks_to_add)
                            if save_all_tasks(all_tasks):
                                task_descs = " and ".join([f"'{get_task_description(t)}'" for t in tasks_to_add])
                                assistant_message = f"✅ **Success:** Okay, adding {task_descs} to your list."
                            else:
                                assistant_message = "❌ **Error:** Failed to save updated task list."

                elif intent == "remove_task":
                    task_details = response_data.get("task_details")
                    result_message = handle_task_removal(task_details, all_tasks) # Saves internally
                    if "Okay, I've removed" in result_message:
                         assistant_message = f"✅ **Success:** {result_message}"
                    else:
                         assistant_message = f"⚠️ {result_message}" # Use warning for failure

                elif intent == "update_task":
                    find_details = response_data.get("find_details")
                    update_details = response_data.get("update_details")
                    result_message = handle_task_update(find_details, update_details, all_tasks) # Saves internally
                    if "Okay, I've updated" in result_message:
                         assistant_message = f"✅ **Success:** {result_message}"
                    else:
                         assistant_message = f"⚠️ {result_message}" # Use warning for failure

                elif intent == "summarize_schedule":
                    date_query = response_data.get("date_query")
                    if not date_query:
                        assistant_message = "⚠️ I understood you wanted a summary, but I missed which day."
                    else:
                        summary = handle_web_summarization(date_query)
                        assistant_message = f"🗓️ **Summary:** {summary}"

                elif intent == "query_schedule":
                    date_query = response_data.get("date_query")
                    if not date_query:
                        assistant_message = "⚠️ I understood you were asking about your schedule, but I missed which day."
                    else:
                        assistant_message = f"🗓️ **Schedule:** {handle_web_schedule_query(date_query)}"

                elif intent == "query_specific_time":
                    date_query = response_data.get("date_query")
                    time_query = response_data.get("time_query")
                    if not (date_query and time_query):
                         assistant_message = "⚠️ I understood you were asking about a time, but I missed the date or time."
                    else:
                        assistant_message = f"🗓️ **Availability:** {handle_web_specific_time_query(date_query, time_query)}"

                else:
                    # Handle cases where LLM gives JSON but no known intent
                    assistant_message = f"❓ I received data but couldn't understand the intent: '{intent}'."
                st.session_state.message_to_speak = assistant_message
                    
                # 4. Save assistant's reply and show message
                if "history" in st.session_state and st.session_state.history:
                    if assistant_message:
                        st.session_state.history[-1]["assistant"] = assistant_message # Add assistant msg to last history entry

                # Display message based on prefix or default to info
                if assistant_message:
                    if assistant_message.startswith("✅"): st.success(assistant_message)
                    elif assistant_message.startswith("🗓️"): st.info(assistant_message)
                    elif assistant_message.startswith("⚠️") or assistant_message.startswith("❓"): st.warning(assistant_message)
                    else: st.error(assistant_message) # Default to error if prefix missing or unknown
                    speak_web(assistant_message)
                    
            except json.JSONDecodeError:
                st.error("**Error:** The LLM returned invalid JSON. Could not process.")
                if "history" in st.session_state:
                    st.session_state.history.append({"user": command_to_process, "json": json_response_text, "assistant": "Error: Invalid JSON."})
                    speak_web("I encountered an error processing your command.")

            except Exception as e:
                st.error(f"**An unexpected error occurred:** {e}")
                 # Optionally log the full traceback for debugging
                 # import traceback
                 # st.error(traceback.format_exc())
                if "history" in st.session_state:
                    st.session_state.history.append({"user": command_to_process, "json": "N/A", "assistant": f"Error: {e}"})
                    speak_web("I encountered an error processing your command.")

            #  Rerun AFTER processing 
            st.rerun() # Refresh UI
    if "message_to_speak" in st.session_state and st.session_state.message_to_speak:
        speak_web(st.session_state.message_to_speak)
        st.session_state.message_to_speak = None # Clear the message after speaking
    
    st.divider()

    #  History Display 
    st.subheader("Conversation & NLP Output")

    if "history" in st.session_state and st.session_state.history:
        for i, entry in enumerate(reversed(st.session_state.history)):
            user_text = entry.get('user', 'Unknown Command')
            with st.expander(f"**You:** {user_text}", expanded=(i==0)):
                st.markdown("**Assistant's Reply:**")
                st.markdown(entry.get('assistant', '...')) # Use markdown for assistant reply
                json_output = entry.get('json', '{}')
                try:
                    st.markdown("**NLP JSON Output:**")
                    st.json(json.loads(json_output))
                except json.JSONDecodeError:
                     st.markdown("**NLP Raw Output:**")
                     st.text(json_output)

# Column 2: Live Task List 
# Ensure this block only appears ONCE
with col2:
    st.header("Current Schedule (tasks.json)")

    if st.button("Refresh List"):
        st.rerun()

    all_tasks = load_all_tasks()
    if all_tasks:
        try:
            df = pd.DataFrame(all_tasks)

            # Ensure apply uses a dict representation of the row
            df['task_description'] = df.apply(lambda row: get_task_description(row.to_dict()), axis=1)

            cols_to_show = ['task_description', 'category', 'date', 'start_time', 'end_time', 'status']
            # Filter based on actual columns present in the DataFrame
            display_cols = [col for col in cols_to_show if col in df.columns]

            # Ensure 'task_description' is included if available
            if 'task_description' in df.columns and 'task_description' not in display_cols:
                display_cols.insert(0, 'task_description') # Add to beginning if missing

            st.dataframe(df[display_cols], width='stretch', hide_index=True) # FIX: Use width='stretch'

        except Exception as e:
            st.error(f"Error displaying tasks: {e}")
            st.write("Raw task data:")
            st.json(all_tasks) # Display raw JSON if DataFrame fails
    else:
        st.write("No tasks in your schedule yet.")
        