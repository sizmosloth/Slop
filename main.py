from datetime import datetime

def say_hello(arg):
    if arg == "":
        print("Greetingsss Master!!!")

def tell_time(arg):
    current_time = datetime.now().strftime("%I:%M %p").lstrip("0")
    print(f"Its {current_time}")

def search(arg):
        print(f"Searching for {arg} ...")

def exit_assistant(arg):
    print("Sure Master, Byeee!")

def unknown(arg):
    print(f"Sorry, I don't understand ' {arg} '.")

def main ():

    commands = {
        "hello" : say_hello,
        "time" : tell_time,
        "search" : search,
        "exit" : exit_assistant,
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