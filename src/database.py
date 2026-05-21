"""
REQ-B09 to REQ-B12 — SQLite Database Layer
Stores documents, authors, relationships, and index data.
"""

import sqlite3
import json
import os

DB_PATH = "data/search_engine.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """
    REQ-B09: Create schema for documents, authors, metadata, and index.
    """
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_connection()
    cur = conn.cursor()

    # REQ-B09/B10: Documents table — raw + processed content
    cur.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            url         TEXT    UNIQUE NOT NULL,
            title       TEXT,
            abstract    TEXT,
            doi         TEXT,
            year        TEXT,
            raw_text    TEXT,       -- REQ-B10: raw title + abstract
            processed   TEXT,       -- REQ-B10: JSON list of tokens after NLP
            pdf_link    TEXT,       -- REQ-B04
            affiliations TEXT       -- REQ-B05: JSON list of affiliations
            pdf_text     TEXT       -- NOVO: texto completo extraído do PDF
        )
    """)

    # REQ-B11: Authors table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS authors (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    """)

    # REQ-B11: Document–Author relationship (many-to-many)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS document_authors (
            document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
            author_id   INTEGER REFERENCES authors(id)   ON DELETE CASCADE,
            PRIMARY KEY (document_id, author_id)
        )
    """)

    # REQ-B12: Inverted index storage
    cur.execute("""
        CREATE TABLE IF NOT EXISTS index_entries (
            term     TEXT PRIMARY KEY,
            df       INTEGER NOT NULL,
            postings TEXT NOT NULL   -- JSON: {url: tf, ...}
        )
    """)

    conn.commit()
    conn.close()
    print("[DB] Schema initialized.")


# ---------------------------------------------------------------------------
# REQ-B10 / B11: Insert documents and authors from scraper output
# ---------------------------------------------------------------------------

def insert_publications(publications: list, processed_map: dict = None):
    """
    Insert scraped publications into the database.
    processed_map: optional dict {url: [tokens]} from NLP preprocessing.
    """
    conn = get_connection()
    cur = conn.cursor()
    inserted = 0

    for pub in publications:
        url = pub.get("url")
        if not url:
            continue

        raw_text = f"{pub.get('title', '')} {pub.get('abstract', '')}"
        processed = json.dumps(processed_map.get(url, [])) if processed_map else None

        affiliations = pub.get("affiliations", [])

        # Insert document (skip if already exists)
        cur.execute("""
            INSERT OR IGNORE INTO documents (url, title, abstract, doi, year, raw_text, processed, pdf_link, affiliations)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            url,
            pub.get("title"),
            pub.get("abstract"),
            pub.get("doi"),
            pub.get("year"),
            raw_text,
            processed,
            pub.get("pdf_link"),
            json.dumps(affiliations),
            pub.get("pdf_text"),
        ))

        if cur.rowcount == 0:
            continue  # already in DB

        doc_id = cur.lastrowid
        inserted += 1

        # REQ-B11: Insert authors and relationships
        authors = pub.get("authors", [])
        if isinstance(authors, str):
            authors = [a.strip() for a in authors.split(";") if a.strip()]

        for author_name in authors:
            cur.execute("INSERT OR IGNORE INTO authors (name) VALUES (?)", (author_name,))
            cur.execute("SELECT id FROM authors WHERE name = ?", (author_name,))
            author_id = cur.fetchone()["id"]
            cur.execute(
                "INSERT OR IGNORE INTO document_authors (document_id, author_id) VALUES (?, ?)",
                (doc_id, author_id)
            )

    conn.commit()
    conn.close()
    print(f"[DB] Inserted {inserted} new documents.")


# ---------------------------------------------------------------------------
# REQ-B12: Store and load the inverted index
# ---------------------------------------------------------------------------

def save_index(inverted_index: dict):
    """Save the inverted index to the database."""
    conn = get_connection()
    cur = conn.cursor()

    for term, data in inverted_index.items():
        cur.execute("""
            INSERT OR REPLACE INTO index_entries (term, df, postings)
            VALUES (?, ?, ?)
        """, (term, data["df"], json.dumps(data["postings"])))

    conn.commit()
    conn.close()
    print(f"[DB] Saved {len(inverted_index)} index entries.")


def load_index() -> dict:
    """Load the inverted index from the database."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT term, df, postings FROM index_entries")
    rows = cur.fetchall()
    conn.close()

    index = {}
    for row in rows:
        index[row["term"]] = {
            "df": row["df"],
            "postings": json.loads(row["postings"])
        }
    return index


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def get_all_doc_urls() -> set:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT url FROM documents")
    urls = {row["url"] for row in cur.fetchall()}
    conn.close()
    return urls


def get_all_publications() -> list:
    """Return all documents with their authors as dicts (same format as scraper JSON)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM documents")
    docs = cur.fetchall()

    publications = []
    for doc in docs:
        doc_dict = dict(doc)
        cur.execute("""
            SELECT a.name FROM authors a
            JOIN document_authors da ON da.author_id = a.id
            WHERE da.document_id = ?
        """, (doc_dict["id"],))
        doc_dict["authors"] = [row["name"] for row in cur.fetchall()]
        doc_dict.pop("id", None)
        doc_dict.pop("raw_text", None)
        doc_dict.pop("processed", None)
        publications.append(doc_dict)

    conn.close()
    return publications


def get_publication_by_url(url: str) -> dict | None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM documents WHERE url = ?", (url,))
    doc = cur.fetchone()
    if not doc:
        conn.close()
        return None
    doc_dict = dict(doc)
    cur.execute("""
        SELECT a.name FROM authors a
        JOIN document_authors da ON da.author_id = a.id
        WHERE da.document_id = ?
    """, (doc_dict["id"],))
    doc_dict["authors"] = [row["name"] for row in cur.fetchall()]
    conn.close()
    return doc_dict


def get_publications_by_author(name: str) -> list:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT d.* FROM documents d
        JOIN document_authors da ON da.document_id = d.id
        JOIN authors a ON a.id = da.author_id
        WHERE LOWER(a.name) LIKE ?
    """, (f"%{name.lower()}%",))
    docs = cur.fetchall()
    result = []
    for doc in docs:
        doc_dict = dict(doc)
        cur.execute("""
            SELECT a.name FROM authors a
            JOIN document_authors da ON da.author_id = a.id
            WHERE da.document_id = ?
        """, (doc_dict["id"],))
        doc_dict["authors"] = [row["name"] for row in cur.fetchall()]
        result.append(doc_dict)
    conn.close()
    return result


if __name__ == "__main__":
    import json
    init_db()
    with open("data/scraper_results.json", "r", encoding="utf-8") as f:
        publications = json.load(f)
    insert_publications(publications)
    print("[DB] Done.")