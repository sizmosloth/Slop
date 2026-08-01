from datetime import datetime
from pathlib import Path
from ddgs import DDGS
import os
from tavily import TavilyClient
from rich.console import Console
from rich.panel import Panel
console = Console()

# Get the API key from environment variable of TAVILY for search response
api_key = os.environ.get("TAVILY_API_KEY")

# Initialize the Tavily client
client = TavilyClient(api_key=api_key)

def say_hello(arg):
    if arg == "":
        print("Greetingsss Master!!!")

def tell_time(arg):
    current_time = datetime.now().strftime("%I:%M %p").lstrip("0")
    print(f"Its {current_time}")

def search(arg):
        if (arg == ""):
            print("Please provide a search query.")
            return
        response = client.search(arg,max_results=3)
        results = response["results"]
        print(f"Search results for '{arg}':")
        for r in results:
            console.print(Panel(
                f"[bold]{r['title']}[/bold]\n{r['url']}\n\n{r['content']}",
                border_style="cyan",
            ))
            
def exit_assistant(arg):
    print("Sure Master, Byeee!")

def unknown(arg):
    print(f"Sorry, I don't understand ' {arg} '.")

def list_files(arg):
    folder = Path(".")  
    for file in folder.iterdir():
        print(file.name)

def read_file(arg):
    path = Path(arg)
    if not path.exists():
        print("File not found.")
        return
    print(path.read_text())

def main ():

    commands = {
        "hello" : say_hello,
        "time" : tell_time,
        "search" : search,
        "exit" : exit_assistant,
        "list" : list_files,
        "read" : read_file
    }

    while True:
        user_input = input("\nYou : ").strip().lower()    
        part = user_input.split(maxsplit=1)
        cmd = part[0]
        arg = part[1] if len(part) > 1 else ""

        if cmd in commands:
            try:
                commands[cmd](arg)
            except Exception as e:
                print(f"Something unsusal happened {e}")

        else:
            unknown(user_input)
        if cmd == "exit":
            break

main ()