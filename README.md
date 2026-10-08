# contrib-sim

## Structure

```
contrib-sim/
├── app/
│   ├── main.py        # Entry point
│   ├── github.py      # GitHub interaction layer
│   ├── analyzer.py    # Analysis logic
│   ├── gemma.py       # Gemma model integration
│   └── prompts.py     # Prompt templates
├── tests/
├── requirements.txt
└── README.md
```

## Setup

```bash
pip install -r requirements.txt
```

## Phase 1

Phase 1 takes a small repository context and issue, then asks a local Ollama
model for a structured contribution plan. It does not clone repositories,
modify code, or create pull requests.

Make sure Ollama is running and the selected model is available:

```bash
ollama run gemma4:e4b
```

Run the sample:

```bash
python -m app.main
```

Run the pipeline without Ollama while the model is downloading:

```bash
python -m app.main --offline
```

Offline mode validates the CLI and response schema with a deterministic sample;
it does not evaluate Gemma's reasoning quality.

Use custom input:

```bash
python -m app.main --context path/to/context.txt --issue "Add validation for empty input before parsing."
```

Run tests:

```bash
python -m unittest discover -s tests
```
