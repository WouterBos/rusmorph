# RusMorph

Basic CLI tool that returns the morphemic breakdown of a given Russian word and explains it in English. A Morphemic breakdown explains the composition of a word which can be helpful when learning a language. After installation, the tool runs without requiring internet access.

> [!IMPORTANT]
> RusMorph works on my (Linux) computer. Unfortunately there's no guarantee it will work on yours.

## Prerequisites

- Python 3
- [Ollama](https://ollama.com) running with Qwen:
  ```bash
  ollama run qwen2.5:3b
  ```
- OS: Linux. Will probably work on MacOS and Windows WSL as well.

> [!WARNING]
> Make sure your Ollama is using the GPU, not the slower CPU. Otherwise you may have to install a different version of ollama like I had to.

### How it works

When installing RusMorph by running build_db.py, it downloads the A. N. Tikhonov's 96k-word dictionary and creates a local database.

When the user requests the morphemic breakdown of a word by running rusmorph.py, the script gets that morphemic breakdown from the database and will use AI to explain that morphemic breakdown in English. This script uses the LLM model Qwen2.5:3b as it's small enough for most modern computers to run locally. Since you run AI locally, you don't need any subscription to use these models.

## Usage

### 1. **Run once**: create the database

```bash
python3 build_db.py
```

It downloads the Tikhonov dataset and compiles the local `morphemes.db` SQLite database.

### 2. Run the Ollama server

```bash
ollama serve &
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
