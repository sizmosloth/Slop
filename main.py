from datetime import datetime
from pathlib import Path
import os
import time
import requests
from tavily import TavilyClient
from rich.console import Console
from rich.panel import Panel

console = Console()

# ---- Setup ----
api_key = os.environ.get("TAVILY_API_KEY")
client = TavilyClient(api_key=api_key)
MODEL = "qwen2.5:0.5b"

# --- ALSO TRIED llama3.2:3b BUT NOT STABLE FOR MY PC SO SWITCHED TO 0.5B PARAMETER MODEL --- 

# ---- LLM helper ----
def ask_llm(prompt, system=""):
    """Send a prompt to the local Ollama model and return its text response."""
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": MODEL,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {"num_predict": 250}
        }
    )
    return response.json()["response"]


# ---- Search + RAG ----
def search_and_answer(query):
    """Search Tavily, feed results to the LLM, print a synthesized answer."""
    if query == "":
        print("Search for what?")
        return

    with console.status("Searching..."):
        t0 = time.time()
        response = client.search(query, max_results=2)
        results = response.get("results", [])
        console.print(f"[dim]Tavily: {time.time() - t0:.1f}s[/dim]")

        if not results:
            console.print("[yellow]No results found.[/yellow]")
            return

        context = ""
        for r in results:
            context += f"{r['title']}\n{r['content'][:400]}\n\n"

        prompt = (
            f"Context from web search:\n{context}\n\n"
            f"Question: {query}\n\n"
            f"Answer the question using the context above. "
            f"Match your answer length to the question — short for simple facts, "
            f"longer only if it truly needs explanation."
        )

    with console.status("Writing answer..."):
        answer = ask_llm(prompt)

    console.print(Panel(answer, title="Answer", border_style="green"))
    for r in results:
        console.print(Panel(f"[bold]{r['title']}[/bold]\n{r['url']}", border_style="cyan"))


# ---- Direct chat (no search) ----
def chat(query):
    with console.status("Thinking..."):
        answer = ask_llm(
            query,
            system=(
                "You are a helpful, concise assistant. Keep casual replies short "
                "(1-2 sentences). Give longer answers only when the question truly "
                "needs explanation."
            )
        )
    console.print(Panel(answer, border_style="magenta"))


# ---- System utility commands ----
def tell_time(arg):
    current_time = datetime.now().strftime("%I:%M %p").lstrip("0")
    print(f"Its {current_time}")


def exit_assistant(arg):
    print("Sure Master, Byeee!")


def list_files(arg):
    folder = Path(".")
    for file in folder.iterdir():
        if file.is_file():
            print(file.name)


def read_file(arg):
    path = Path(arg)
    if not path.exists():
        print("File not found.")
        return
    print(path.read_text())


# ---- Main loop ----
def main():
    commands = {
        "time": tell_time,
        "exit": exit_assistant,
        "list": list_files,
        "read": read_file,
        "search": search_and_answer,
    }

    while True:
        raw_input_text = input("\nYou : ").strip()
        part = raw_input_text.split(maxsplit=1)

        if not part:
            continue

        cmd = part[0].lower()
        arg = part[1] if len(part) > 1 else ""

        try:
            if cmd in commands:
                # known command (time, exit, list, read, search) -> run it directly
                commands[cmd](arg)
            else:
                # anything else -> straight to the LLM, no search, no routing call
                chat(raw_input_text)
        except requests.exceptions.ConnectionError:
            console.print("[red]Couldn't reach Ollama. Is it running? (ollama serve)[/red]")
        except Exception as e:
            console.print(f"[red]Something unusual happened: {e}[/red]")

        if cmd == "exit":
            break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nForce quit. Bye!")