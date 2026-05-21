"""
Indexer — Universidade do Minho · PRI
Builds an inverted index with:
  - Per-field postings: title / abstract  (REQ-B46)
  - Position lists per document           (REQ-B48 — phrase & proximity search)
  - Incremental update support
  - Term-Document Matrix                  (REQ-B24)
"""

import json
import os
import numpy as np
from src.search.nlp import preprocess


# ---------------------------------------------------------------------------
# REQ-B24 — Term-Document Matrix (defined first so build_index can call it)
# ---------------------------------------------------------------------------

def build_term_document_matrix(
    inverted_index: dict,
    output_dir: str = 'data',
) -> dict:
    """
    Builds a Term-Document Matrix (raw TF values) and persists it to disk.
    """
    all_doc_ids = sorted({
        url
        for entry in inverted_index.values()
        for url in entry["postings"]
    })

    doc_index = {url: idx for idx, url in enumerate(all_doc_ids)}
    n_docs = len(all_doc_ids)

    matrix: dict[str, list[int]] = {}
    for term, entry in inverted_index.items():
        row = [0] * n_docs
        for url, posting in entry["postings"].items():
            tf = posting["tf"] if isinstance(posting, dict) else posting
            row[doc_index[url]] = tf
        matrix[term] = row

    result = {"doc_ids": all_doc_ids, "matrix": matrix}

    os.makedirs(output_dir, exist_ok=True)
    matrix_path = os.path.join(output_dir, "term_document_matrix.json")
    with open(matrix_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"[REQ-B24] Term-document matrix: {len(matrix)} terms × {n_docs} docs → {matrix_path}")
    return result


def load_term_document_matrix(
    matrix_path: str = 'data/term_document_matrix.json',
) -> tuple[list, dict]:
    with open(matrix_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data["doc_ids"], data["matrix"]


# ---------------------------------------------------------------------------
# Main indexer
# ---------------------------------------------------------------------------

def build_index(
    json_path: str = 'data/scraper_results.json',
    output_path: str = 'data/index.json',
) -> None:
    """
    Builds or incrementally updates the inverted index.
    """
    print("--- Starting Indexer ---")

    inverted_index: dict = {}
    indexed_urls: set = set()

    if os.path.exists(output_path):
        try:
            with open(output_path, 'r', encoding='utf-8') as f:
                inverted_index = json.load(f)
            for term in inverted_index:
                for url in inverted_index[term]['postings']:
                    indexed_urls.add(url)
            print(f"[Incremental] Loaded existing index with {len(indexed_urls)} documents.")
        except Exception as e:
            print(f"[Warning] Could not load existing index: {e}")

    if not os.path.exists(json_path):
        print(f"[Error] Scraper results not found at: {json_path}")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        publications = json.load(f)

    print(f"Found {len(publications)} documents in scraper results.")

    new_docs_count = 0
    for pub in publications:
        url = pub.get('url')
        if not url or url in indexed_urls:
            continue

        new_docs_count += 1

        # REQ-B46: process each field independently
        title_tokens    = preprocess(pub.get('title', ''))
        abstract_tokens = preprocess(pub.get('abstract', ''))

        # Index author names
        authors = pub.get('authors', [])
        if isinstance(authors, str):
            authors = [a.strip() for a in authors.split(';') if a.strip()]
        author_tokens = preprocess(' '.join(authors))

        # Global token stream for position tracking (REQ-B48)
        all_tokens = title_tokens + abstract_tokens + author_tokens

        # Per-field TF
        title_tf: dict[str, int] = {}
        for t in title_tokens:
            title_tf[t] = title_tf.get(t, 0) + 1

        abstract_tf: dict[str, int] = {}
        for t in abstract_tokens:
            abstract_tf[t] = abstract_tf.get(t, 0) + 1

        author_tf: dict[str, int] = {}
        for t in author_tokens:
            author_tf[t] = author_tf.get(t, 0) + 1

        # Global positions (REQ-B48)
        positions: dict[str, list[int]] = {}
        for pos, token in enumerate(all_tokens):
            positions.setdefault(token, []).append(pos)

        all_terms = set(title_tf) | set(abstract_tf) | set(author_tf)

        for term in all_terms:
            if term not in inverted_index:
                inverted_index[term] = {"df": 0, "postings": {}}

            t_tf  = title_tf.get(term, 0)
            a_tf  = abstract_tf.get(term, 0)
            au_tf = author_tf.get(term, 0)
            total_tf = t_tf + a_tf + au_tf

            fields = []
            if t_tf  > 0: fields.append("title")
            if a_tf  > 0: fields.append("abstract")
            if au_tf > 0: fields.append("authors")

            inverted_index[term]["postings"][url] = {
                "tf":          total_tf,
                "fields":      fields,
                "title_tf":    t_tf,
                "abstract_tf": a_tf,
                "author_tf":   au_tf,
                "positions":   positions.get(term, []),
            }

    # Sort postings alphabetically (required by skip-pointer algorithm)
    for term in inverted_index:
        sorted_postings = dict(sorted(inverted_index[term]["postings"].items()))
        inverted_index[term]["postings"] = sorted_postings
        inverted_index[term]["df"] = len(sorted_postings)

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(inverted_index, f, ensure_ascii=False, indent=4)

    print(f"Success! {new_docs_count} new documents added to the index.")
    print(f"Final index saved at: {output_path}")

    build_term_document_matrix(inverted_index, output_dir=os.path.dirname(output_path) or '.')

    from src.database import init_db, insert_publications, save_index
    init_db()
    insert_publications(publications)
    save_index(inverted_index)


if __name__ == "__main__":
    build_index()