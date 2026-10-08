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

## Run

```bash
python -m app.main
```
