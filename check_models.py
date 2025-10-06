# A script to see which Gemini models are available to your API key.

import os
import google.generativeai as genai
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

# Setup
load_dotenv()
console = Console()

# Load API Key
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    console.print("[bold red]ERROR: GEMINI_API_KEY not found in your .env file.[/bold red]")
    exit()

genai.configure(api_key=api_key)

# Main Logic
try:
    console.print("[yellow]Fetching available models from Google AI...[/yellow]\n")

    # Create a table to display the models
    table = Table(title="Available Gemini Models (that support 'generateContent')")
    table.add_column("Model Name", style="cyan", no_wrap=True)
    table.add_column("Description", style="magenta")

    found_models = False
    for model in genai.list_models():
        if 'generateContent' in model.supported_generation_methods:
            table.add_row(model.name, model.description)
            found_models = True

    if found_models:
        console.print(table)
        console.print("\n[bold green]ACTION:[/bold green] Copy the most suitable 'Model Name' from the table above (likely '[cyan]models/gemini-pro[/cyan]') and paste it into your `pulsevox.py` file.")
    else:
        console.print("[bold red]No models supporting 'generateContent' were found for your API key.[/bold red]")

except Exception as e:
    console.print(f"[bold red]An error occurred while trying to fetch the models: {e}[/bold red]")