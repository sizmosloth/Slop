from datetime import datetime
from pathlib import Path
import os
import re
import time
import json
import requests
from tavily import TavilyClient

# ---- Setup ----
api_key = os.environ.get("TAVILY_API_KEY")
client = TavilyClient(api_key=api_key)
MODEL = "qwen2.5:1.5b"

MEMORY_FILE = Path("memory.json")
FACTS_FILE = Path("facts.json")
MAX_HISTORY_MESSAGES = 12   # only the last N messages get sent to the model each time

SYSTEM_PROMPT = (
    "You are Slop, a helpful personal assistant running locally on the user's computer. "
    "You are created by sizmosloth"
    "You have memory of this conversation across sessions. Use earlier messages to answer "
    "questions about things the user already told you. Keep casual replies short "
    "(1-2 sentences). Give longer, complete answers only when the question truly needs "
    "explanation or code. If you don't know something, say so honestly instead of guessing. "
    "When answering from search results, only state facts that are explicitly present in "
    "the provided context — never invent names, dates, or numbers that aren't there. "
    "Do not attempt to draw diagrams, flowcharts, or tables using text characters — "
    "describe things in plain sentences or numbered steps instead."
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


# ---- Facts: deterministic memory that doesn't rely on the model "remembering" ----
def load_facts():
    """Load known facts about the user from disk."""
    if FACTS_FILE.exists():
        try:
            return json.loads(FACTS_FILE.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save_facts(facts):
    FACTS_FILE.write_text(json.dumps(facts, indent=2))


known_facts = load_facts()


# ---- Notes: explicit, free-form memory ("remember X") ----
NOTES_FILE = Path("notes.json")


def load_notes():
    """Load saved notes from disk."""
    if NOTES_FILE.exists():
        try:
            return json.loads(NOTES_FILE.read_text())
        except json.JSONDecodeError:
            return []
    return []


def save_notes(notes):
    NOTES_FILE.write_text(json.dumps(notes, indent=2))


saved_notes = load_notes()


def notes_as_text():
    """Turn saved notes into plain text to inject into the system prompt."""
    if not saved_notes:
        return ""
    bullet_list = "\n".join(f"- {n}" for n in saved_notes)
    return "Things the user asked to be remembered:\n" + bullet_list


def extract_facts(query):
    """
    Look for simple, explicit patterns in what the user says and save them
    as facts. This is plain pattern matching, not the LLM guessing — so it's
    100% reliable regardless of how small the model is.
    """
    match = re.search(r"my name is (\w+)", query, re.IGNORECASE)
    if match:
        known_facts["name"] = match.group(1).capitalize()
        save_facts(known_facts)

    match = re.search(r"i live in ([\w\s]+?)(?:\.|$)", query, re.IGNORECASE)
    if match:
        known_facts["location"] = match.group(1).strip().title()
        save_facts(known_facts)

    match = re.search(r"my favou?rite (\w+) is ([\w\s]+?)(?:\.|$)", query, re.IGNORECASE)
    if match:
        key = f"favorite_{match.group(1).lower()}"
        known_facts[key] = match.group(2).strip().title()
        save_facts(known_facts)


def facts_as_text():
    """Turn known facts into a plain sentence to inject into the system prompt."""
    if not known_facts:
        return ""
    parts = [f"{k.replace('_', ' ')} is {v}" for k, v in known_facts.items()]
    return "Known facts about the user: " + "; ".join(parts) + "."


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
        timeout=120   # first message after a cold start can take a while to load the model
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


def build_system_prompt():
    """Combine the base system prompt with known facts and saved notes."""
    system = SYSTEM_PROMPT
    facts_text = facts_as_text()
    if facts_text:
        system += "\n" + facts_text
    notes_text = notes_as_text()
    if notes_text:
        system += "\n" + notes_text
    return system


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
        f"Answer the question fully and accurately using ONLY the context above. "
        f"If the context doesn't contain the answer, say so instead of guessing. "
        f"Match your answer length to the question — short for simple facts, "
        f"longer and complete for anything needing explanation or code."
    )

    messages = [
        {"role": "system", "content": build_system_prompt()},
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


# ---- Direct chat (remembers past messages + known facts) ----
def chat(query):
    extract_facts(query)

    recent = conversation_history[-MAX_HISTORY_MESSAGES:]
    messages = [{"role": "system", "content": build_system_prompt()}] + recent + [
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


def show_facts(arg):
    """Show known facts about the user."""
    if not known_facts:
        print("No facts known yet.")
        return
    for k, v in known_facts.items():
        print(f"{k}: {v}")


def remember(arg):
    """Save any free-form text as a permanent note."""
    if arg == "":
        print("Remember what? e.g. 'remember I'm building a Python assistant called Slop'")
        return
    text = arg
    if text.lower().startswith("that "):
        text = text[5:]   # strip a leading "that " for cleaner storage
    saved_notes.append(text)
    save_notes(saved_notes)
    print(f"Got it, I'll remember: {text}")


def show_notes(arg):
    """List everything saved via 'remember'."""
    if not saved_notes:
        print("No notes saved yet. Try: remember <something>")
        return
    for i, n in enumerate(saved_notes, start=1):
        print(f"{i}. {n}")


def clear_notes(arg):
    """Wipe all saved notes."""
    global saved_notes
    saved_notes = []
    save_notes(saved_notes)
    print("Notes cleared.")


def show_help(arg):
    print("Commands: time, list, read <file>, search <query>, remember <text>, notes,")
    print("          clearnotes, forget, memory, facts, help, exit")
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
        "facts": show_facts,
        "remember": remember,
        "notes": show_notes,
        "clearnotes": clear_notes,
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