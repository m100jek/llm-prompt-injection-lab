# LLM Prompt Injection Lab

Research project focused on:

- Direct Prompt Injection
- Indirect Prompt Injection
- Prompt Leakage
- Tool Abuse
- Defensive Techniques

Goal:
Measure effectiveness of prompt injection attacks against LLM-powered applications.

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com)

## Setup

```bash
ollama pull llama3.2
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
python main.py
```

On Linux/macOS, activate the virtual environment with `source .venv/bin/activate`.

## Usage

```text
LLM Prompt Injection Lab
Model: llama3.2
Type 'exit' or 'quit' to leave.

prompt> Hello, who are you?

<model response>

prompt> exit
Bye.
```

Each prompt is sent as an independent request (no conversation history), which makes it easier to test single injection payloads in later lab stages.

## Roadmap

| Stage | Focus |
| ----- | ----- |
| 1 (current) | Minimal REPL + Ollama (`llama3.2`) |
| 2 | System prompt + simulated guarded application |
| 3 | Attack scenario catalog (`scenarios/direct/`, `scenarios/indirect/`) |
| 4 | Document context (indirect injection) |
| 5 | Attack success metrics and defensive techniques |
| 6 | Optional FastAPI + simple UI |
