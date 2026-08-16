from datetime import datetime
from pathlib import Path
import os
import time
import json
import requests
from tavily import TavilyClient

# ---- Setup ----
api_key = os.environ.get("TAVILY_API_KEY")
client = TavilyClient(api_key=api_key)
MODEL = "qwen2.5:1.5b"

MEMORY_FILE = Path("memory.json")
MAX_HISTORY_MESSAGES = 12   # only the last N messages get sent to the model each time

SYSTEM_PROMPT = (
    "You are Slop, a helpful personal assistant running locally on the user's computer. "
    "You have memory of this conversation across sessions. Use earlier messages to answer "
    "questions about things the user already told you. Keep casual replies short "
    "(1-2 sentences). Give longer, complete answers only when the question truly needs "
    "explanation or code. If you don't know something, say so honestly instead of guessing."
)


# ---- Memory: load/save conversation history ----
def load_memory():
    """Load past conversation history from disk, if it exists."""
    if MEMORY_FILE.exists():
        try:
            return json.loads(MEMORY_FILE.read_text())
        except json.JSONDecodeError:
            print("(memory file was corrupted, starting fresh)")
            return []
    return []


def save_memory(history):
    """Save the full conversation history to disk."""
    MEMORY_FILE.write_text(json.dumps(history, indent=2))


conversation_history = load_memory()


# ---- LLM helper (streaming, using /api/chat) ----
def ask_llm(messages, num_predict=400):
    """
    Send a list of {"role", "content"} messages to Ollama's chat endpoint,
    stream the reply, print it live, and return the full text.
    """
    print("Slop: ", end="", flush=True)

    response = requests.post(
        "http://localhost:11434/api/chat",
        json={
            "model": MODEL,
            "messages": messages,
            "stream": True,
            "options": {"num_predict": num_predict}
        },
        stream=True,
        timeout=60
    )

    full_text = ""
    for line in response.iter_lines():
        if not line:
            continue
        try:
            chunk = json.loads(line)
        except json.JSONDecodeError:
            continue

        piece = chunk.get("message", {}).get("content", "")
        print(piece, end="", flush=True)
        full_text += piece

        if chunk.get("done"):
            break

    print()
    return full_text


# ---- Search + RAG ----
def search_and_answer(query):
    """Search Tavily, feed results to the LLM, stream a synthesized answer."""
    if query == "":
        print("Search for what?")
        return

    print("Searching...")
    t0 = time.time()
    response = client.search(query, max_results=3, search_depth="advanced")
    results = response.get("results", [])
    print(f"(Tavily: {time.time() - t0:.1f}s)")

    if not results:
        print("No results found.")
        return

    context = ""
    for r in results:
        context += f"{r['title']}\n{r['content'][:600]}\n\n"

    user_prompt = (
        f"Context from web search:\n{context}\n\n"
        f"Question: {query}\n\n"
        f"Answer the question fully and accurately using the context above. "
        f"Match your answer length to the question — short for simple facts, "
        f"longer and complete for anything needing explanation or code."
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    print("--- Answer ---")
    answer = ask_llm(messages, num_predict=800)

    print("\n--- Sources ---")
    for r in results:
        print(f"- {r['title']}\n  {r['url']}")

    conversation_history.append({"role": "user", "content": f"search {query}"})
    conversation_history.append({"role": "assistant", "content": answer})
    save_memory(conversation_history)


# ---- Direct chat (remembers past messages) ----
def chat(query):
    recent = conversation_history[-MAX_HISTORY_MESSAGES:]
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + recent + [
        {"role": "user", "content": query}
    ]

    answer = ask_llm(messages, num_predict=500)

    conversation_history.append({"role": "user", "content": query})
    conversation_history.append({"role": "assistant", "content": answer})
    save_memory(conversation_history)


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


def forget(arg):
    """Wipe conversation memory."""
    global conversation_history
    conversation_history = []
    save_memory(conversation_history)
    print("Memory cleared.")


def show_memory(arg):
    """Show what's currently remembered."""
    if not conversation_history:
        print("No memory saved yet.")
        return
    for msg in conversation_history[-MAX_HISTORY_MESSAGES:]:
        print(f"[{msg['role']}] {msg['content'][:100]}")


def show_help(arg):
    print("Commands: time, list, read <file>, search <query>, forget, memory, help, exit")
    print("Anything else is sent straight to Slop as a normal message.")


# ---- Main loop ----
def main():
    commands = {
        "time": tell_time,
        "exit": exit_assistant,
        "list": list_files,
        "read": read_file,
        "search": search_and_answer,
        "forget": forget,
        "memory": show_memory,
        "help": show_help,
    }

    print(f"(loaded {len(conversation_history)} past messages from memory)")
    print("Type 'help' to see available commands.")

    while True:
        raw_input_text = input("\nYou : ").strip()
        part = raw_input_text.split(maxsplit=1)

        if not part:
            continue

        cmd = part[0].lower()
        arg = part[1] if len(part) > 1 else ""

        try:
            if cmd in commands:
                commands[cmd](arg)
            else:
                chat(raw_input_text)
        except requests.exceptions.ConnectionError:
            print("Couldn't reach Ollama. Is it running? (ollama serve)")
        except requests.exceptions.Timeout:
            print("Ollama took too long to respond. Try again.")
        except Exception as e:
            print(f"Something unusual happened: {e}")

        if cmd == "exit":
            break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nForce quit. Bye!")