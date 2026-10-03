# RusMorph

Basic CLI tool that returns the morphemic breakdown of a given Russian word and explains it in English. A Morphemic breakdown explains the composition of a word which can be helpful when learning a language. After installation, the tool runs without requiring internet access.

> [!IMPORTANT]
> RusMorph is only tested on my laptop (Linux). Unfortunately there's no guarantee it will work on yours.

## Prerequisites

- Python 3
- [Ollama](https://ollama.com) running with Qwen:
  ```bash
  ollama run qwen2.5:3b
  ```
- OS: Linux. Will probably work on MacOS and Windows WSL as well.

### How it works

It downloads the A. N. Tikhonov's 96k-word dictionary and creates a local database. When the user requests the morphemic breakdown of a word, the script gets that morphemic breakdown from the database and will then pass it on to AI get additional explanation and translation. This script uses the LLM model Qwen2.5:3b as it's small enough for most modern computers to run locally.

## Usage

### 1. **Run once**: create the database

```bash
python3 build_db.py
```

It downloads the Tikhonov dataset and compiles the local `morphemes.db` SQLite database.

### 2. Run the Ollama server

```bash
ollama serve &
ollama run qwen2.5:3b
```

### 3. **Run once**: Install the default LLM model

```bash
ollama run qwen2.5:3b
```

### 4. Analyze a Russian word and stream the English breakdown:

```bash
# Single word
python3 rusmorph.py одуматься

# Interactive mode
python3 rusmorph.py
```

Options:
- `--model <name>`: Custom Ollama model (default: `qwen2.5:3b`)
- `--db <path>`: Custom SQLite database path (default: `morphemes.db`)

## Quick Access (optional)

Add an alias to `~/.zshrc` (zshell) or `~/.bashrc` (bash):

```bash
alias rusmorph="python3 /home/wbo/rusmorph/rusmorph.py"
```

Save the rc-file and reload the shell. Now you can run anywhere:

```bash
rusmorph переподготовка
```
