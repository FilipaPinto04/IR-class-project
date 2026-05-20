"""
tfidf.py — TF-IDF Ranking & Document Similarity
Universidade do Minho · PRI

Changes vs previous version:
  REQ-B46  get_custom_ranking() accepts optional ``fields`` param — scores
           only TF from the requested field(s) (title_tf / abstract_tf).
  REQ-B47  get_custom_ranking() accepts optional ``expand`` param — expands
           query tokens via WordNet before scoring.
"""

import json
import math
import os
import numpy as np
from src.search.nlp import preprocess, expand_query
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def load_resources(
    index_path: str = 'data/index.json',
    pubs_path: str  = 'data/scraper_results.json',
) -> tuple[dict, list]:
    with open(index_path, 'r', encoding='utf-8') as f:
        index = json.load(f)
    with open(pubs_path, 'r', encoding='utf-8') as f:
        publications = json.load(f)
    return index, publications


# ---------------------------------------------------------------------------
# REQ-B46 helper — extract the right TF from a posting dict
# ---------------------------------------------------------------------------

def _posting_tf(posting: dict | int, fields: list[str] | None) -> int:
    """
    Returns the TF to use for a given posting, respecting the field filter.

    Old index format: posting is a plain int (total TF) — fields ignored.
    New index format: posting is a dict with keys tf / title_tf / abstract_tf.
    """
    if isinstance(posting, int):
        return posting

    if fields is None:
        return posting.get("tf", 0)

    total = 0
    if "title" in fields:
        total += posting.get("title_tf", 0)
    if "abstract" in fields:
        total += posting.get("abstract_tf", 0)
    return total


# ---------------------------------------------------------------------------
# Custom TF-IDF ranking
# ---------------------------------------------------------------------------

def get_custom_ranking(
    query: str,
    index: dict,
    total_docs: int,
    fields: list[str] | None = None,
    expand: bool = False,
) -> list[tuple[str, float]]:
    """
    Calculates TF-IDF scores manually and ranks documents by cosine similarity.

    Args:
        query:      Raw query string.
        index:      Inverted index.
        total_docs: Total number of documents in the corpus (for IDF).
        fields:     Restrict scoring to 'title' and/or 'abstract'. (REQ-B46)
                    None means all fields.
        expand:     Expand query terms via WordNet synonyms. (REQ-B47)

    Returns:
        List of (url, score) sorted by descending score.
    """
    query_tokens = preprocess(query)
    if not query_tokens:
        return []

    # REQ-B47: optional query expansion
    if expand:
        query_tokens = expand_query(query_tokens, max_synonyms_per_token=2)

    # Build query vector (raw TF per token)
    query_vector: dict[str, int] = {}
    for token in query_tokens:
        query_vector[token] = query_vector.get(token, 0) + 1

    scores: dict[str, float] = {}

    for token, q_tf in query_vector.items():
        if token not in index:
            continue
        df = index[token]['df']
        if df == 0:
            continue
        idf = math.log10(total_docs / df)

        for url, posting in index[token]['postings'].items():
            # REQ-B46: use field-specific TF if requested
            doc_tf = _posting_tf(posting, fields)
            if doc_tf == 0:
                continue
            tfidf_score = doc_tf * idf
            scores[url] = scores.get(url, 0) + (tfidf_score * (q_tf * idf))

    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


# ---------------------------------------------------------------------------
# Sklearn TF-IDF ranking
# ---------------------------------------------------------------------------

def get_sklearn_ranking(
    query: str,
    publications: list[dict],
    fields: list[str] | None = None,
) -> list[tuple[str, float]]:
    """
    Uses scikit-learn TF-IDF + cosine similarity for comparison ranking.

    Args:
        query:        Raw query string.
        publications: List of publication dicts.
        fields:       Restrict corpus text to 'title' and/or 'abstract'.
                      None means title + abstract (original behaviour). (REQ-B46)
    """
    def _doc_text(p: dict) -> str:
        parts = []
        if fields is None or "title" in fields:
            parts.append(p.get('title', ''))
        if fields is None or "abstract" in fields:
            parts.append(p.get('abstract', ''))
        return " ".join(parts)

    corpus = [_doc_text(p) for p in publications]
    urls   = [p.get('url') for p in publications]

    # Filter out empty/placeholder documents
    non_empty = [(c, u) for c, u in zip(corpus, urls) if c.strip() and c.strip() not in ("N/A", "")]
    if not non_empty:
        return []
    corpus_clean, urls_clean = zip(*non_empty)

    from unidecode import unidecode
    vectorizer = TfidfVectorizer(
        stop_words=None,
        lowercase=True,
        preprocessor=lambda t: unidecode(t),
        min_df=1,
    )
    tfidf_matrix  = vectorizer.fit_transform(corpus_clean)
    query_vec     = vectorizer.transform([unidecode(query)])
    cosine_sim    = cosine_similarity(query_vec, tfidf_matrix).flatten()
    ranked_indices = cosine_sim.argsort()[::-1]
    return [(urls_clean[i], float(cosine_sim[i])) for i in ranked_indices if cosine_sim[i] > 0]


# ---------------------------------------------------------------------------
# REQ-B39 — Alternative weighting schemes: BM25 and TF-only
# ---------------------------------------------------------------------------

def get_bm25_ranking(
    query: str,
    index: dict,
    total_docs: int,
    k1: float = 1.5,
    b: float = 0.75,
) -> list[tuple[str, float]]:
    """
    REQ-B39: BM25 — industry-standard probabilistic weighting scheme.
    Improves on TF-IDF by saturating term frequency and normalizing by doc length.

    Args:
        k1: Term frequency saturation (typically 1.2–2.0).
        b:  Document length normalization (0 = none, 1 = full).
    """
    query_tokens = preprocess(query)
    if not query_tokens:
        return []

    # Estimate average document length from index
    all_tfs = [
        tf if isinstance(tf, int) else tf.get("tf", 0)
        for entry in index.values()
        for tf in entry['postings'].values()
    ]
    avg_dl = (sum(all_tfs) / len(all_tfs)) if all_tfs else 1

    scores: dict[str, float] = {}
    for token in query_tokens:
        if token not in index:
            continue
        df = index[token]['df']
        idf = math.log((total_docs - df + 0.5) / (df + 0.5) + 1)

        for url, posting in index[token]['postings'].items():
            doc_tf = posting if isinstance(posting, int) else posting.get("tf", 0)
            tf_saturated = (doc_tf * (k1 + 1)) / (doc_tf + k1 * (1 - b + b * (doc_tf / avg_dl)))
            scores[url] = scores.get(url, 0) + idf * tf_saturated

    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


def get_tf_ranking(
    query: str,
    index: dict,
) -> list[tuple[str, float]]:
    """
    REQ-B39: TF-only ranking — no IDF weighting.
    Useful as a baseline to compare against TF-IDF and BM25.
    """
    query_tokens = preprocess(query)
    if not query_tokens:
        return []

    scores: dict[str, float] = {}
    for token in query_tokens:
        if token not in index:
            continue
        for url, posting in index[token]['postings'].items():
            doc_tf = posting if isinstance(posting, int) else posting.get("tf", 0)
            scores[url] = scores.get(url, 0) + doc_tf

    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


# ---------------------------------------------------------------------------
# REQ-B40 — Document-Document Similarity Matrix (unchanged)
# ---------------------------------------------------------------------------

def build_similarity_matrix(
    publications: list[dict],
    output_dir: str = 'data',
    top_k: int | None = None,
) -> tuple[list[str], np.ndarray]:
    """
    Builds a Document × Document cosine-similarity matrix (REQ-B40).
    Saves both a .npy binary and a sparse .json neighbour list.
    """
    corpus  = [f"{p.get('title', '')} {p.get('abstract', '')}" for p in publications]
    doc_ids = [p.get('url') for p in publications]

    if not corpus:
        print("[REQ-B40] No publications found — similarity matrix not built.")
        return doc_ids, np.empty((0, 0))

    vectorizer   = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(corpus)
    sim_matrix   = cosine_similarity(tfidf_matrix)

    os.makedirs(output_dir, exist_ok=True)

    npy_path = os.path.join(output_dir, "similarity_matrix.npy")
    np.save(npy_path, sim_matrix)

    sparse: dict[str, list[dict]] = {}
    for i, url in enumerate(doc_ids):
        row = sim_matrix[i]
        neighbours = [
            {"url": doc_ids[j], "score": round(float(row[j]), 6)}
            for j in range(len(doc_ids))
            if j != i and row[j] > 0.0
        ]
        neighbours.sort(key=lambda x: x["score"], reverse=True)
        if top_k is not None:
            neighbours = neighbours[:top_k]
        sparse[url] = neighbours

    json_path = os.path.join(output_dir, "similarity_matrix.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({"doc_ids": doc_ids, "neighbours": sparse}, f, ensure_ascii=False, indent=2)

    n = len(doc_ids)
    print(f"[REQ-B40] Similarity matrix built: {n}×{n} docs")
    print(f"          Binary  → {npy_path}")
    print(f"          Sparse  → {json_path}")
    return doc_ids, sim_matrix


def load_similarity_matrix(output_dir: str = 'data') -> tuple[list[str], np.ndarray]:
    npy_path  = os.path.join(output_dir, "similarity_matrix.npy")
    json_path = os.path.join(output_dir, "similarity_matrix.json")
    matrix = np.load(npy_path)
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data["doc_ids"], matrix


def get_similar_documents(
    url: str,
    top_k: int = 10,
    output_dir: str = 'data',
) -> list[tuple[str, float]]:
    doc_ids, matrix = load_similarity_matrix(output_dir)
    if url not in doc_ids:
        print(f"[Warning] URL not found in similarity matrix: {url}")
        return []
    idx = doc_ids.index(url)
    row = matrix[idx]
    neighbours = [
        (doc_ids[j], float(row[j]))
        for j in range(len(doc_ids))
        if j != idx and row[j] > 0.0
    ]
    neighbours.sort(key=lambda x: x[1], reverse=True)
    return neighbours[:top_k]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    index, publications = load_resources()
    total_docs = len(publications)

    print("=== Advanced Search Engine: TF-IDF & Similarity ===")

    while True:
        query = input("\nEnter query (or 'exit'): ").strip()
        if query.lower() == 'exit':
            break

        mode = input(
            "Choose: [1] Custom TF-IDF  [2] Sklearn  [3] Similarity Matrix  "
            "[4] Custom (title only)  [5] Custom (expanded)  "
            "[6] BM25 (REQ-B39)  [7] TF-only (REQ-B39): "
        ).strip()

        if mode == '1':
            results = get_custom_ranking(query, index, total_docs)
        elif mode == '2':
            results = get_sklearn_ranking(query, publications)
        elif mode == '3':
            build_similarity_matrix(publications)
            lookup = input("URL to find similar docs (Enter to skip): ").strip()
            if lookup:
                similar = get_similar_documents(lookup, top_k=10)
                for i, (u, s) in enumerate(similar, 1):
                    print(f"  {i}. [{s:.4f}] {u}")
            continue
        elif mode == '4':
            results = get_custom_ranking(query, index, total_docs, fields=['title'])
        elif mode == '5':
            results = get_custom_ranking(query, index, total_docs, expand=True)
        elif mode == '6':
            results = get_bm25_ranking(query, index, total_docs)
        elif mode == '7':
            results = get_tf_ranking(query, index)
        else:
            continue

        if not results:
            print("No relevant documents found.")
        else:
            for i, (url, score) in enumerate(results[:10], 1):
                print(f"{i}. [{score:.4f}] {url}")


if __name__ == "__main__":
    main()