#!/usr/bin/env python3
"""
build_db.py
Downloads the digitized A.N. Tikhonov Morphemic-Orthographic Dictionary
(from open academic NLP repository) and indexes it into a local SQLite database.
"""

import os
import sqlite3
import sys
import urllib.request

DATA_URLS = [
    (
        "train_Tikhonov_reformat.txt",
        "https://raw.githubusercontent.com/AlexeySorokin/NeuralMorphemeSegmentation/master/data/train_Tikhonov_reformat.txt",
    ),
    (
        "test_Tikhonov_reformat.txt",
        "https://raw.githubusercontent.com/AlexeySorokin/NeuralMorphemeSegmentation/master/data/test_Tikhonov_reformat.txt",
    ),
]

DB_FILENAME = "morphemes.db"


def build_db(db_path: str = None):
    if db_path is None:
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), DB_FILENAME)

    print(f"[*] Target SQLite Database: {db_path}")

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute("DROP TABLE IF EXISTS morphemes")
    c.execute("""
        CREATE TABLE morphemes (
            word TEXT PRIMARY KEY,
            breakdown TEXT
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_word ON morphemes(word)")

    total_words = 0
    headers = {"User-Agent": "Mozilla/5.0 (compatible; RusMorph/1.0)"}

    for filename, url in DATA_URLS:
        print(f"[*] Downloading and indexing {filename}...")
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                batch = []
                file_count = 0
                for line in resp:
                    decoded = line.decode("utf-8").strip()
                    parts = decoded.split("\t")
                    if len(parts) == 2:
                        word, breakdown = parts[0].strip().lower(), parts[1].strip()
                        batch.append((word, breakdown))
                        file_count += 1

                        if len(batch) >= 10000:
                            c.executemany("INSERT OR IGNORE INTO morphemes VALUES (?, ?)", batch)
                            conn.commit()
                            batch = []

                if batch:
                    c.executemany("INSERT OR IGNORE INTO morphemes VALUES (?, ?)", batch)
                    conn.commit()

                print(f"    -> Added {file_count:,} words from {filename}")
                total_words += file_count

        except Exception as e:
            print(f"[!] Error downloading {filename}: {e}", file=sys.stderr)
            conn.close()
            return False

    c.execute("SELECT COUNT(*) FROM morphemes")
    count_in_db = c.fetchone()[0]
    conn.close()

    print(f"\n[+] Successfully built database with {count_in_db:,} entries!")
    print(f"[+] Database saved to: {db_path} ({os.path.getsize(db_path) / (1024*1024):.1f} MB)\n")
    return True


if __name__ == "__main__":
    build_db()
