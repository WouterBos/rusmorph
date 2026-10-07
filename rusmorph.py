#!/usr/bin/env python3
"""
rusmorph.py
Russian Morphemic Analyzer with English Semantics.
Combines Russian Dictionary (SQLite) with AI (via Ollama)
for contextual English explanations of roots, affixes, and nuances.
"""

import argparse
import json
import os
import readline  # enables arrow keys and history in interactive input
import re
import socket
import sqlite3
import sys
import threading
import urllib.request
import urllib.error
import unicodedata

DEFAULT_MODEL = os.environ.get("RUSMORPH_MODEL", "qwen2.5:3b")
DEFAULT_OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(SCRIPT_DIR, "morphemes.db")
DEFAULT_TIMEOUT = int(os.environ.get("RUSMORPH_TIMEOUT", "60"))
TIMEOUT = DEFAULT_TIMEOUT

# Terminal text formatting
BOLD = "\033[1m"
ITALIC = "\033[3m"
RESET = "\033[0m"


def format_terminal_markdown(text: str) -> str:
    """Format markdown headings, bold, and italic text for terminal display."""
    m = re.match(r"^(\s*)#{1,6}\s*(.*?)\s*$", text)
    if m:
        indent, content = m.groups()
        content = content.rstrip("#").strip().replace("**", "").replace("*", "")
        return f"{indent}{BOLD}{content}{RESET}"
    # Bold + Italic (***text***)
    text = re.sub(r"\*\*\*(.*?)\*\*\*", rf"{BOLD}{ITALIC}\1{RESET}", text)
    # Bold (**text**)
    text = re.sub(r"\*\*(.*?)\*\*", rf"{BOLD}\1{RESET}", text)
    # Italic (*text* or _text_)
    text = re.sub(r"\*([^\s*](?:[^*]*?[^\s*])?)\*", rf"{ITALIC}\1{RESET}", text)
    text = re.sub(r"(?<!\w)_([^\s_](?:[^_]*?[^\s_])?)_(?!\w)", rf"{ITALIC}\1{RESET}", text)
    return text.replace("**", "")


TAG_MAP = {
    "PREF": "приставка (prefix)",
    "ROOT": "корень (root)",
    "SUFF": "суффикс (suffix)",
    "END": "окончание (inflection/ending)",
    "POSTFIX": "постфикс (postfix)",
    "LINK": "соединительная гласная (linking vowel)",
    "HYPH": "дефис (hyphen)",
}


def remove_diacritics(text: str) -> str:
    """Remove diacritical marks (e.g. stress marks like acute/grave accents) from text.

    Preserves distinct Russian letters such as 'й' and 'ё'.
    """
    if not text:
        return text

    # Precomposed Cyrillic characters with grave accents (used for secondary stress)
    grave_map = {
        "\u0400": "\u0415",  # Ѐ -> Е
        "\u0450": "\u0435",  # ѐ -> е
        "\u040d": "\u0418",  # Ѝ -> И
        "\u045d": "\u0438",  # ѝ -> и
    }
    for char, repl in grave_map.items():
        if char in text:
            text = text.replace(char, repl)

    # Normalize to NFC so base letters like 'й' (U+0439) and 'ё' (U+0451)
    # are composed and not represented as base letter + combining mark.
    text = unicodedata.normalize("NFC", text)

    # Filter out combining marks (Unicode category 'M*') and spacing accents
    spacing_accents = {"\u00b4", "\u0060", "\u02ca", "\u02cb", "\u02c6", "\u02dc", "\u02c9"}
    cleaned = [
        char
        for char in text
        if not unicodedata.category(char).startswith("M") and char not in spacing_accents
    ]
    return "".join(cleaned)


def get_tikhonov_breakdown(word: str, db_path: str):
    """Query SQLite database for exact Tikhonov breakdown."""
    if not os.path.exists(db_path):
        return None

    word_clean = remove_diacritics(word).strip().lower()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT breakdown FROM morphemes WHERE word=?", (word_clean,))
    row = c.fetchone()
    if not row and "ё" in word_clean:
        c.execute("SELECT breakdown FROM morphemes WHERE word=?", (word_clean.replace("ё", "е"),))
        row = c.fetchone()
    conn.close()
    return row[0] if row else None


def format_raw_breakdown(raw: str):
    """Format raw Tikhonov string like 'о:PREF/дум:ROOT/а:SUFF/ть:SUFF/ся:POSTFIX'."""
    tokens = raw.split("/")
    formatted_parts = []
    structured_list = []

    for t in tokens:
        if ":" in t:
            morpheme, tag = t.split(":", 1)
            desc = TAG_MAP.get(tag, tag)
            formatted_parts.append(f"{morpheme} [{desc}]")
            structured_list.append(f"- '{morpheme}' ({desc})")
        else:
            formatted_parts.append(t)
            structured_list.append(f"- '{t}'")

    summary_line = " + ".join(formatted_parts)
    return summary_line, "\n".join(structured_list)


def stream_ollama_explanation(
    word: str,
    raw_breakdown: str = None,
    model: str = DEFAULT_MODEL,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    timeout: int = DEFAULT_TIMEOUT,
):
    """Stream explanation from local Ollama model."""
    if raw_breakdown:
        summary_line, structured_list = format_raw_breakdown(raw_breakdown)
        system_prompt = (
            "You are an expert Russian lexicologist, etymologist, and English translator.\n"
            "Your task is to explain the semantic and morphological breakdown of Russian words for an English speaker.\n"
            "Be terse, precise, clear, and structured."
        )
        user_prompt = f"""Word to analyze: "{word}"
Verified Morphemes (Tikhonov Academic Standard):
{structured_list}

Analyze EVERY SINGLE morpheme listed above but focus on the root. The rest is less important.

1. **Overall Word Meaning**:
   - **Definition**: English translation & part of speech.
   - **Nuance/Context**: How it is used.

2. **Morpheme Breakdown**:
   - For EACH prefix: its meaning and how it alters the word (e.g. пере- = re-/over-, под- = sub-/additional).
   - For EACH root: core meaning, English translation, and key related words (e.g. готов -> готовить "to prepare", готовый "ready").
   - For EACH suffix / linking vowel: exact grammatical role (e.g. noun nominalizer, diminutive, verbal aspect, adjective marker).
   - For the ending / postfix: inflection (gender, case, number, or reflexive marker like -ся).

3. **Linguistic Synthesis**:
   - In 1-2 sentences, explain how these components combine logically to produce the word's meaning.
"""
    else:
        system_prompt = (
            "You are an expert Russian lexicologist, etymologist, and English translator.\n"
            "Your task is to identify the morphemes of a Russian word and explain their meanings in English."
        )
        user_prompt = f"""Analyze the Russian word "{word}".
Note: This word was not found in the dictionary (it may be an inflected form, colloquialism, or neologism).

Please provide:
1. **Overall Meaning**: English definition & part of speech.
2. **Morphemic Breakdown**:
   - Identify Prefix(es), Root(s), Suffix(es), and Ending/Postfix.
   - For each morpheme, provide its English translation or grammatical role.
3. **Root & Word Family**: Key related Russian words sharing this root.
"""

    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": True,
            "options": {
                "temperature": 0.3,  # Low temperature for factual linguistic consistency
            },
        }
    ).encode("utf-8")

    api_endpoint = f"{ollama_url.rstrip('/')}/api/chat"

    stop_spinner = threading.Event()
    dots_printed = False

    def spinner_worker():
        nonlocal dots_printed
        sys.stdout.write("Analyzing")
        sys.stdout.flush()
        dots_printed = True
        while not stop_spinner.wait(1.0):
            sys.stdout.write(".")
            sys.stdout.flush()

    spinner_thread = threading.Thread(target=spinner_worker, daemon=True)

    def end_spinner():
        if not stop_spinner.is_set():
            stop_spinner.set()
            if spinner_thread.is_alive():
                spinner_thread.join()
            if dots_printed:
                if sys.stdout.isatty():
                    sys.stdout.write("\r\033[K")
                else:
                    sys.stdout.write("\n")
                sys.stdout.flush()

    try:
        req = urllib.request.Request(
            api_endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        spinner_thread.start()
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            line_buffer = ""
            for line in resp:
                if not line:
                    continue
                chunk = json.loads(line.decode("utf-8"))
                msg = chunk.get("message", {})
                content = msg.get("content", "")
                if content:
                    end_spinner()
                    line_buffer += content
                    while "\n" in line_buffer:
                        curr_line, line_buffer = line_buffer.split("\n", 1)
                        sys.stdout.write(format_terminal_markdown(curr_line) + "\n")
                        sys.stdout.flush()
            if line_buffer:
                sys.stdout.write(format_terminal_markdown(line_buffer))
                sys.stdout.flush()
        end_spinner()
        sys.stdout.write("\n")
    except (urllib.error.URLError, TimeoutError, socket.timeout) as e:
        end_spinner()
        is_timeout = (
            isinstance(e, (TimeoutError, socket.timeout))
            or isinstance(getattr(e, "reason", None), (TimeoutError, socket.timeout))
            or "timed out" in str(e).lower()
        )
        if is_timeout:
            print(f"\n[!] Timeout has been reached (waited {timeout}s).")
        else:
            print(
                f"\n[!] Could not connect to Ollama at {ollama_url}. Is 'ollama serve' running?",
                file=sys.stderr,
            )
            print(f"    Error details: {e}", file=sys.stderr)
    finally:
        end_spinner()


def analyze_word(
    word: str,
    db_path: str = DEFAULT_DB_PATH,
    model: str = DEFAULT_MODEL,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    timeout: int = DEFAULT_TIMEOUT,
):
    word = remove_diacritics(word).strip()
    if not word:
        return

    raw_breakdown = get_tikhonov_breakdown(word, db_path)

    if raw_breakdown:
        summary_line, _ = format_raw_breakdown(raw_breakdown)
        print(f"{BOLD}{summary_line}{RESET}\n")
    else:
        print(f"{BOLD}(no morphemic breakdown found){RESET}\n")

    stream_ollama_explanation(
        word=word,
        raw_breakdown=raw_breakdown,
        model=model,
        ollama_url=ollama_url,
        timeout=timeout,
    )
    print(f"\n")


def main():
    parser = argparse.ArgumentParser(
        description="Russian Morphemic Analyzer with English Semantics"
    )
    parser.add_argument(
        "word",
        nargs="?",
        help="Russian word to analyze (if omitted, starts interactive shell)",
    )
    parser.add_argument(
        "--db",
        default=DEFAULT_DB_PATH,
        help=f"Path to SQLite morphemes.db (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Ollama model to use (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_OLLAMA_URL,
        help=f"Ollama URL (default: {DEFAULT_OLLAMA_URL})",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Ollama request timeout in seconds (default: {DEFAULT_TIMEOUT})",
    )

    args = parser.parse_args()

    # Check if database exists
    if not os.path.exists(args.db):
        print(f"[!] Warning: Database not found at '{args.db}'.", file=sys.stderr)
        print(
            f"    Please run 'python3 {os.path.join(SCRIPT_DIR, 'build_db.py')}' first to index 96,000 words.\n",
            file=sys.stderr,
        )

    if args.word:
        analyze_word(
            args.word,
            db_path=args.db,
            model=args.model,
            ollama_url=args.url,
            timeout=args.timeout,
        )
    else:
        print("\n" + "=" * 60)
        print("  RUSSIAN MORPHEMIC ANALYZER (Interactive Mode)")
        print(f"  Model: {args.model} | Database: {os.path.basename(args.db)}")
        print("  Type any Russian word to analyze, or 'exit' / 'q' to quit.")
        print("=" * 60)

        while True:
            try:
                user_input = input("RusMorph > ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ("exit", "quit", "q", ":q"):
                    print("Goodbye!")
                    break
                analyze_word(
                    user_input,
                    db_path=args.db,
                    model=args.model,
                    ollama_url=args.url,
                    timeout=args.timeout,
                )
            except (KeyboardInterrupt, EOFError):
                print("\nExiting.")
                break


if __name__ == "__main__":
    main()
