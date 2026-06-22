from config import DEFAULT_MODEL
from ollama_client import OllamaClientError, chat


def main() -> None:
    print("LLM Prompt Injection Lab")
    print(f"Model: {DEFAULT_MODEL}")
    print("Type 'exit' or 'quit' to leave.\n")

    while True:
        try:
            prompt = input("prompt> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not prompt:
            continue

        if prompt.lower() in {"exit", "quit"}:
            print("Bye.")
            break

        try:
            response = chat(prompt)
        except OllamaClientError as exc:
            print(f"Error: {exc}")
            continue

        print(f"\n{response}\n")


if __name__ == "__main__":
    main()
