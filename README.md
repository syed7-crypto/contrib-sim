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

The default provider is hosted Gemma through the Gemini API. Set
`GEMINI_API_KEY` in your environment; do not commit the key. Google currently
documents hosted Gemma models including `gemma-4-26b-a4b-it` and
`gemma-4-31b-it`.

PowerShell:

```powershell
$env:GEMINI_API_KEY = "your-key"
$env:CONTRIBSIM_PROVIDER = "gemini"
```

Make sure Ollama is running and the selected model is available:

```bash
ollama run gemma4:e4b
```

Run the sample:

```bash
python -m app.main
```

To switch to local Ollama later:

```powershell
$env:CONTRIBSIM_PROVIDER = "ollama"
python -m app.main --model gemma4:e4b
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

Use a public GitHub repository and issue:

```bash
python -m app.main \
  --repo-url https://github.com/owner/repository \
  --issue-url https://github.com/owner/repository/issues/123
```

The collector fetches issue metadata, the default branch, the file tree, and a
small deterministic selection of README, configuration, source, and test files.

Run tests:

```bash
python -m unittest discover -s tests
```

## End-to-end evaluation

Run the repeatable evaluation fixture against a real public repository and
issue. This workflow only reads GitHub data and does not modify the target
repository:

```powershell
python -m app.evaluate --fixture evaluations/hello-world-issue-1.json --verbose
```

The JSON output preserves the Contributor Plan, grounding result, review, and
verbose diagnostics for the retrieved issue and supplied evidence.
