from datetime import datetime

def say_hello():
    print("Greetingsss Master!!!")

def tell_time():
    current_time = datetime.now().strftime("%I:%M %p").lstrip("0")
    print(f"Its {current_time}")

def exit_assistant():
    print("Sure Master, Byeee!")

def unknown():
    print("Sorry, I don't understand that command yet.")

def main ():

    commands = {
        "hello" : say_hello,
        "time" : tell_time,
        "exit" : exit_assistant,
    }

    while True:
        user_input = input("\nYou : ").strip().lower()    

        if user_input in commands:
            commands[user_input]()

            if user_input == "exit":
                break

        else:
            unknown()

main ()