#!/usr/bin/env python3
"""
rusmorph.py
Russian Morphemic Analyzer with English Semantics.
Combines A.N. Tikhonov's 96k-word Dictionary (SQLite) for 100% accurate segmentation
with local Qwen 2.5 (via Ollama) for contextual English explanations of roots, affixes, and nuances.
"""

import argparse
import json
import os
import readline  # enables arrow keys and history in interactive input
import sqlite3
import sys
import urllib.request
import urllib.error

DEFAULT_MODEL = os.environ.get("RUSMORPH_MODEL", "qwen2.5:3b")
DEFAULT_OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(SCRIPT_DIR, "morphemes.db")

TAG_MAP = {
    "PREF": "приставка (prefix)",
    "ROOT": "корень (root)",
    "SUFF": "суффикс (suffix)",
    "END": "окончание (inflection/ending)",
    "POSTFIX": "постфикс (postfix)",
    "LINK": "соединительная гласная (linking vowel)",
    "HYPH": "дефис (hyphen)",
}


def get_tikhonov_breakdown(word: str, db_path: str):
    """Query SQLite database for exact Tikhonov breakdown."""
    if not os.path.exists(db_path):
        return None

    word_clean = word.strip().lower()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT breakdown FROM morphemes WHERE word=?", (word_clean,))
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
):
    """Stream explanation from local Ollama model."""
    if raw_breakdown:
        summary_line, structured_list = format_raw_breakdown(raw_breakdown)
        system_prompt = (
            "You are an expert Russian lexicologist, etymologist, and English translator.\n"
            "Your task is to explain the semantic and morphological breakdown of Russian words for an English speaker.\n"
            "Be precise, clear, and structured."
        )
        user_prompt = f"""Word to analyze: "{word}"
Verified Morphemes (Tikhonov Academic Standard):
{structured_list}

Analyze EVERY SINGLE morpheme listed above but ignore any postfix, infliction or ending. Focus on the root. The rest is less important.

1. **Overall Word Meaning**:
   - **Definition**: English translation & part of speech.
   - **Nuance/Context**: How it is used.

2. **Morpheme Breakdown (Cover all elements listed above)**:
   - For EACH prefix: its meaning
   - For EACH root: core meaning, English translation, and key related words (e.g. готов -> готовить "to prepare", готовый "ready").
   - For EACH suffix: its meaning.

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
                "temperature": 0.2,  # Low temperature for factual linguistic consistency
            },
        }
    ).encode("utf-8")

    api_endpoint = f"{ollama_url.rstrip('/')}/api/chat"

    try:
        req = urllib.request.Request(
            api_endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            for line in resp:
                if not line:
                    continue
                chunk = json.loads(line.decode("utf-8"))
                msg = chunk.get("message", {})
                content = msg.get("content", "")
                sys.stdout.write(content)
                sys.stdout.flush()
        sys.stdout.write("\n")
    except urllib.error.URLError as e:
        print(
            f"\n[!] Could not connect to Ollama at {ollama_url}. Is 'ollama serve' running?",
            file=sys.stderr,
        )
        print(f"    Error details: {e}", file=sys.stderr)


def analyze_word(
    word: str,
    db_path: str = DEFAULT_DB_PATH,
    model: str = DEFAULT_MODEL,
    ollama_url: str = DEFAULT_OLLAMA_URL,
):
    word = word.strip()
    if not word:
        return

    raw_breakdown = get_tikhonov_breakdown(word, db_path)

    if raw_breakdown:
        summary_line, _ = format_raw_breakdown(raw_breakdown)
        print(f"📖 Tikhonov Segmentation: {summary_line}\n")
    else:
        print("ℹ️  Word not in Tikhonov base dictionary (querying Qwen directly)...\n")

    stream_ollama_explanation(
        word=word,
        raw_breakdown=raw_breakdown,
        model=model,
        ollama_url=ollama_url,
    )
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Russian Morphemic Analyzer with English Semantics (Tikhonov DB + Qwen)"
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
                )
            except (KeyboardInterrupt, EOFError):
                print("\nExiting.")
                break


if __name__ == "__main__":
    main()
