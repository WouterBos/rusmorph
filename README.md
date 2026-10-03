# RusMorph

Local Russian morphemic analyzer. Uses A. N. Tikhonov's 96k-word dictionary (SQLite) for exact morpheme boundaries and a local LLM (`qwen2.5:3b` via Ollama) to explain the English meanings of roots, prefixes, and suffixes.

## Prerequisites

- Python 3
- [Ollama](https://ollama.com) running with Qwen:
  ```bash
  ollama run qwen2.5:3b
  ```

## Usage

### 1. **Run once**: `build_db.py`. It downloads the Tikhonov dataset and compiles the local `morphemes.db` SQLite database.
```bash
python3 build_db.py
```

### 2. `rusmorph.py`
Analyzes a Russian word and streams the English breakdown:
```bash
# Single word
python3 rusmorph.py одуматься

# Interactive mode
python3 rusmorph.py
```

Options:
- `--model <name>`: Custom Ollama model (default: `qwen2.5:3b`)
- `--db <path>`: Custom SQLite database path (default: `morphemes.db`)

## Quick Access

Add an alias to `~/.zshrc` or `~/.bashrc`:
```bash
alias rusmorph="python3 /home/wbo/rusmorph/rusmorph.py"
```

Reload shell and use anywhere:
```bash
rusmorph переподготовка
```
