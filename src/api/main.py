"""
API REST — Motor de Pesquisa de Publicações Científicas
Universidade do Minho — Pesquisa e Recuperação de Informação
"""

import json
import os
import re
import unicodedata
import xml.etree.ElementTree as ET
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from src.search.nlp import preprocess
from src.search.query import execute_boolean_query, execute_phrase_query, execute_proximity_query
from src.search.tfidf import get_custom_ranking, get_sklearn_ranking

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="RepositóriUM Search Engine",
    description=(
        "Motor de pesquisa de publicações científicas da Universidade do Minho. "
        "Suporta pesquisa por texto livre (TF-IDF), pesquisa booleana (AND/OR/NOT), "
        "pesquisa por frase, pesquisa por proximidade e pesquisa por autor. "
        "Respostas em JSON e XML (REQ-B52)."
    ),
    version="2.0.0",
    contact={"name": "PRI — UMinho"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

INDEX_PATH = "data/index.json"
PUBS_PATH  = "data/scraper_results.json"


def _load_data():
    if not os.path.exists(INDEX_PATH):
        raise RuntimeError(f"Index not found at '{INDEX_PATH}'. Run the indexer first.")
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        index = json.load(f)
    publications: List[dict] = []
    if os.path.exists(PUBS_PATH):
        with open(PUBS_PATH, "r", encoding="utf-8") as f:
            publications = json.load(f)
    all_doc_ids = {p.get("url") for p in publications if p.get("url")}
    pub_lookup  = {p.get("url"): p for p in publications if p.get("url")}
    return index, publications, all_doc_ids, pub_lookup


try:
    INDEX, PUBLICATIONS, ALL_DOC_IDS, PUB_LOOKUP = _load_data()
except Exception as _e:
    INDEX, PUBLICATIONS, ALL_DOC_IDS, PUB_LOOKUP = {}, [], set(), {}
    print(f"[WARNING] Could not load data at startup: {_e}")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class PublicationResult(BaseModel):
    url: str
    title: Optional[str] = None
    authors: Optional[List[str]] = None
    abstract: Optional[str] = None
    snippet: Optional[str] = None
    date: Optional[str] = None
    doi: Optional[str] = None
    pdf_link: Optional[str] = None
    score: Optional[float] = None


class SearchResponse(BaseModel):
    query: str
    total: int
    page: int
    page_size: int
    results: List[PublicationResult]


class AuthorProfile(BaseModel):
    name: str
    total_publications: int
    publications: List[PublicationResult]


# ---------------------------------------------------------------------------
# REQ-B66 — Query sanitization
# ---------------------------------------------------------------------------

_FORBIDDEN_PATTERN = re.compile(r"[<>{}\[\]\\|`~@#$%^*]")
_REPEATED_OPERATOR = re.compile(r"\b(AND|OR|NOT)\b(?:\s+\b(?:AND|OR|NOT)\b)+", re.IGNORECASE)
_MAX_QUERY_LEN     = 512


def sanitize_query(raw: str) -> str:
    if len(raw) > _MAX_QUERY_LEN:
        raise HTTPException(
            status_code=400,
            detail=f"Query too long: {len(raw)} chars (max {_MAX_QUERY_LEN}).",
        )
    q = unicodedata.normalize("NFC", raw.strip())
    q = _FORBIDDEN_PATTERN.sub(" ", q)
    q = re.sub(r"\s+", " ", q).strip()
    q = _REPEATED_OPERATOR.sub(lambda m: m.group(1).upper(), q)
    q = re.sub(r"^(AND|OR|NOT)\s+", "", q, flags=re.IGNORECASE)
    q = re.sub(r"\s+(AND|OR|NOT)$", "", q, flags=re.IGNORECASE).strip()
    if not q:
        raise HTTPException(status_code=400, detail="Query is empty after sanitization.")
    return q


# ---------------------------------------------------------------------------
# REQ-B50 — Snippet generation
# ---------------------------------------------------------------------------

_SNIPPET_MAX_CHARS = 300


def _extract_snippet(text: str, query_tokens: List[str]) -> Optional[str]:
    if not text:
        return None
    if not query_tokens:
        snippet = text[:_SNIPPET_MAX_CHARS]
        return snippet + ("…" if len(text) > _SNIPPET_MAX_CHARS else "")

    token_pattern = re.compile(
        r"\b(" + "|".join(re.escape(t) for t in query_tokens) + r")\b",
        re.IGNORECASE,
    )
    sentences = re.split(r"(?<=[.!?])\s+", text)
    best_idx, best_count = 0, -1
    for i, sent in enumerate(sentences):
        count = len(token_pattern.findall(sent))
        if count > best_count:
            best_count, best_idx = count, i

    start  = max(0, best_idx - 1)
    end    = min(len(sentences), best_idx + 2)
    window = " ".join(sentences[start:end])

    if len(window) > _SNIPPET_MAX_CHARS:
        window     = window[:_SNIPPET_MAX_CHARS]
        last_space = window.rfind(" ")
        if last_space > _SNIPPET_MAX_CHARS // 2:
            window = window[:last_space]
        window += "…"

    return token_pattern.sub(r"<mark>\1</mark>", window)


def _query_surface_tokens(q: str) -> List[str]:
    cleaned   = re.sub(r"\b(AND|OR|NOT)\b", " ", q, flags=re.IGNORECASE)
    raw_words = [w for w in re.split(r"\s+", cleaned) if len(w) > 1]
    try:
        nlp_tokens = preprocess(q)
    except Exception:
        nlp_tokens = []
    seen: set = set()
    combined  = []
    for tok in sorted(raw_words + nlp_tokens, key=len, reverse=True):
        tl = tok.lower()
        if tl not in seen and tl not in {"and", "or", "not"}:
            seen.add(tl)
            combined.append(tok)
    return combined


# ---------------------------------------------------------------------------
# REQ-B52 — XML serialisation helpers
# ---------------------------------------------------------------------------

def _result_to_xml_elem(r: PublicationResult) -> ET.Element:
    doc = ET.Element("document")
    for field in ("url", "title", "date", "doi", "pdf_link", "score", "snippet", "abstract"):
        val = getattr(r, field, None)
        if val is not None:
            ET.SubElement(doc, field).text = str(val)
    if r.authors:
        authors_el = ET.SubElement(doc, "authors")
        for a in r.authors:
            ET.SubElement(authors_el, "author").text = a
    return doc


def _search_response_to_xml(resp: SearchResponse) -> Response:
    root = ET.Element("searchResponse")
    ET.SubElement(root, "query").text    = resp.query
    ET.SubElement(root, "total").text    = str(resp.total)
    ET.SubElement(root, "page").text     = str(resp.page)
    ET.SubElement(root, "pageSize").text = str(resp.page_size)
    results_el = ET.SubElement(root, "results")
    for r in resp.results:
        results_el.append(_result_to_xml_elem(r))
    xml_str = ET.tostring(root, encoding="unicode", xml_declaration=False)
    return Response(
        content=f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_str}',
        media_type="application/xml",
    )


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _build_result(
    url: str,
    score: Optional[float],
    pub: Optional[dict],
    query_tokens: Optional[List[str]] = None,
) -> PublicationResult:
    if pub is None:
        pub = {}
    authors = pub.get("authors", [])
    if isinstance(authors, str):
        authors = [a.strip() for a in authors.split(";") if a.strip()]
    abstract = pub.get("abstract")
    snippet  = _extract_snippet(abstract or "", query_tokens) if query_tokens is not None else None
    return PublicationResult(
        url=url,
        title=pub.get("title"),
        authors=authors or None,
        abstract=abstract,
        snippet=snippet,
        date=pub.get("date") or pub.get("publication_date") or pub.get("year"),
        doi=pub.get("doi"),
        pdf_link=pub.get("pdf_link") or pub.get("pdf_url"),
        score=round(score, 6) if score is not None else None,
    )


def _paginate(items, page: int, page_size: int):
    start = (page - 1) * page_size
    return items[start: start + page_size]


def _apply_filters(urls: List[str], year: Optional[int], doc_type: Optional[str]) -> List[str]:
    if not year and not doc_type:
        return urls
    filtered = []
    for url in urls:
        pub = PUB_LOOKUP.get(url, {})
        if year:
            pub_date = str(pub.get("date", "") or pub.get("publication_date", ""))
            if str(year) not in pub_date:
                continue
        if doc_type:
            if doc_type.lower() not in str(pub.get("type", "")).lower():
                continue
        filtered.append(url)
    return filtered


def _parse_fields(fields: Optional[str]) -> Optional[List[str]]:
    """Parse the ``fields`` query param into a list or None (= all fields)."""
    if not fields:
        return None
    parsed = [f.strip() for f in fields.split(",") if f.strip() in ("title", "abstract")]
    return parsed if parsed else None


def _respond(resp: SearchResponse, fmt: str):
    """Return a FastAPI-compatible JSON model or an XML Response."""
    return _search_response_to_xml(resp) if fmt == "xml" else resp


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/", tags=["Info"])
def root():
    """Health check / welcome."""
    return {
        "message": "RepositóriUM Search Engine is running.",
        "docs": "/docs",
        "total_documents_indexed": len(ALL_DOC_IDS),
        "total_terms_indexed": len(INDEX),
    }


# ── 1. Free-text search (TF-IDF) ───────────────────────────────────────────

@app.get("/search", tags=["Search"])
def search(
    q: str = Query(..., description="Texto a pesquisar"),
    mode: str = Query(
        "custom",
        description="'custom' (implementação própria) ou 'sklearn'",
        pattern="^(custom|sklearn)$",
    ),
    fields: Optional[str] = Query(
        None,
        description="REQ-B46 — Restringir a 'title', 'abstract' ou 'title,abstract' (omitir = todos).",
    ),
    expand: bool = Query(False, description="REQ-B47 — Expandir termos com sinónimos WordNet."),
    year: Optional[int] = Query(None, description="Filtrar por ano de publicação"),
    doc_type: Optional[str] = Query(None, description="Filtrar por tipo de documento"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    format: str = Query("json", pattern="^(json|xml)$", description="REQ-B52 — 'json' ou 'xml'."),
):
    """
    **Pesquisa por texto livre** com ranking TF-IDF.

    Suporta filtragem por campo (`fields`), expansão de query (`expand`) e
    resposta em JSON ou XML (`format`).
    """
    if not INDEX:
        raise HTTPException(status_code=503, detail="Index not loaded.")

    q          = sanitize_query(q)
    field_list = _parse_fields(fields)

    if mode == "custom":
        raw_results = get_custom_ranking(q, INDEX, max(len(PUBLICATIONS), 1), fields=field_list, expand=expand)
    else:
        if not PUBLICATIONS:
            raise HTTPException(status_code=503, detail="Publications data not available.")
        raw_results = get_sklearn_ranking(q, PUBLICATIONS, fields=field_list)

    urls_ordered = [url for url, _ in raw_results]
    scores       = {url: score for url, score in raw_results}
    filtered     = _apply_filters(urls_ordered, year, doc_type)
    paginated    = _paginate(filtered, page, page_size)
    hl_tokens    = _query_surface_tokens(q)
    results      = [_build_result(url, scores.get(url), PUB_LOOKUP.get(url), hl_tokens) for url in paginated]

    resp = SearchResponse(query=q, total=len(filtered), page=page, page_size=page_size, results=results)
    return _respond(resp, format)


# ── 2. Boolean search ───────────────────────────────────────────────────────

@app.get("/search/boolean", tags=["Search"])
def search_boolean(
    q: str = Query(..., description="Query booleana — AND / OR / NOT, parênteses, frases, NEAR/k"),
    fields: Optional[str] = Query(None, description="REQ-B46 — 'title', 'abstract' ou ambos."),
    expand: bool = Query(False, description="REQ-B47 — Expandir termos com sinónimos WordNet."),
    year: Optional[int] = Query(None),
    doc_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    format: str = Query("json", pattern="^(json|xml)$", description="REQ-B52 — 'json' ou 'xml'."),
):
    """
    **Pesquisa booleana** — NOT > AND > OR (precedência correcta), parênteses,
    frases ("…") e proximidade (word NEAR/k word) incluídos.
    """
    if not INDEX:
        raise HTTPException(status_code=503, detail="Index not loaded.")

    q          = sanitize_query(q)
    field_list = _parse_fields(fields)

    matching_urls = execute_boolean_query(q, INDEX, ALL_DOC_IDS, fields=field_list, expand=expand)
    urls_list     = sorted(list(matching_urls))
    filtered      = _apply_filters(urls_list, year, doc_type)
    paginated     = _paginate(filtered, page, page_size)
    hl_tokens     = _query_surface_tokens(q)
    results       = [_build_result(url, None, PUB_LOOKUP.get(url), hl_tokens) for url in paginated]

    resp = SearchResponse(query=q, total=len(filtered), page=page, page_size=page_size, results=results)
    return _respond(resp, format)


# ── 3. Phrase search ─────────────────────────────────────────────────────── REQ-B48

@app.get("/search/phrase", tags=["Search"])
def search_phrase(
    q: str = Query(..., description='Frase exacta, ex: "deep learning"'),
    fields: Optional[str] = Query(None, description="REQ-B46 — 'title', 'abstract' ou ambos."),
    year: Optional[int] = Query(None),
    doc_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    format: str = Query("json", pattern="^(json|xml)$", description="REQ-B52 — 'json' ou 'xml'."),
):
    """
    **Pesquisa por frase exacta** (REQ-B48).

    Os tokens devem aparecer consecutivos e na ordem correcta.
    Requer índice com listas de posições (novo `indexer.py`).
    """
    if not INDEX:
        raise HTTPException(status_code=503, detail="Index not loaded.")

    q          = sanitize_query(q)
    field_list = _parse_fields(fields)

    matching_urls = execute_phrase_query(q, INDEX, field_list)
    urls_list     = sorted(list(matching_urls))
    filtered      = _apply_filters(urls_list, year, doc_type)
    paginated     = _paginate(filtered, page, page_size)
    hl_tokens     = _query_surface_tokens(q)
    results       = [_build_result(url, None, PUB_LOOKUP.get(url), hl_tokens) for url in paginated]

    resp = SearchResponse(query=q, total=len(filtered), page=page, page_size=page_size, results=results)
    return _respond(resp, format)


# ── 4. Proximity search ──────────────────────────────────────────────────── REQ-B48

@app.get("/search/proximity", tags=["Search"])
def search_proximity(
    term1: str = Query(..., description="Primeiro termo"),
    term2: str = Query(..., description="Segundo termo"),
    distance: int = Query(5, ge=1, le=50, description="Distância máxima em tokens (NEAR/k)"),
    fields: Optional[str] = Query(None, description="REQ-B46 — 'title', 'abstract' ou ambos."),
    year: Optional[int] = Query(None),
    doc_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    format: str = Query("json", pattern="^(json|xml)$", description="REQ-B52 — 'json' ou 'xml'."),
):
    """
    **Pesquisa por proximidade** (REQ-B48) — `term1 NEAR/distance term2`.

    Devolve documentos onde os dois termos estão a no máximo `distance`
    posições de distância (em qualquer ordem).
    Requer índice com listas de posições (novo `indexer.py`).
    """
    if not INDEX:
        raise HTTPException(status_code=503, detail="Index not loaded.")

    term1      = sanitize_query(term1)
    term2      = sanitize_query(term2)
    field_list = _parse_fields(fields)

    matching_urls = execute_proximity_query(term1, term2, distance, INDEX, field_list)
    urls_list     = sorted(list(matching_urls))
    filtered      = _apply_filters(urls_list, year, doc_type)
    paginated     = _paginate(filtered, page, page_size)
    hl_tokens     = _query_surface_tokens(f"{term1} {term2}")
    results       = [_build_result(url, None, PUB_LOOKUP.get(url), hl_tokens) for url in paginated]

    query_str = f"{term1} NEAR/{distance} {term2}"
    resp = SearchResponse(query=query_str, total=len(filtered), page=page, page_size=page_size, results=results)
    return _respond(resp, format)


# ── 5. Author search ─────────────────────────────────────────────────────── REQ-B53/54/55

@app.get("/search/author", tags=["Search"])
def search_author(
    name: str = Query(..., description="Nome do autor (pesquisa parcial, case-insensitive)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    format: str = Query("json", pattern="^(json|xml)$", description="REQ-B52 — 'json' ou 'xml'."),
):
    """
    **Pesquisa por autor** com correspondência parcial case-insensitive. (REQ-B53/B54/B55)
    """
    if not PUBLICATIONS:
        raise HTTPException(status_code=503, detail="Publications data not available.")

    name       = sanitize_query(name)
    name_lower = name.lower()
    matched: List[PublicationResult] = []

    for pub in PUBLICATIONS:
        authors = pub.get("authors", [])
        if isinstance(authors, str):
            authors = [a.strip() for a in authors.split(";")]
        if any(name_lower in (a or "").lower() for a in authors):
            matched.append(_build_result(pub.get("url", ""), None, pub))

    paginated = _paginate(matched, page, page_size)

    if format == "xml":
        root = ET.Element("authorSearch")
        ET.SubElement(root, "queryAuthor").text = name
        ET.SubElement(root, "total").text       = str(len(matched))
        ET.SubElement(root, "page").text        = str(page)
        ET.SubElement(root, "pageSize").text    = str(page_size)
        results_el = ET.SubElement(root, "results")
        for r in paginated:
            results_el.append(_result_to_xml_elem(r))
        xml_str = ET.tostring(root, encoding="unicode")
        return Response(
            content=f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_str}',
            media_type="application/xml",
        )

    return {
        "query_author": name,
        "total":        len(matched),
        "page":         page,
        "page_size":    page_size,
        "results":      paginated,
    }


# ── 6. Author profile ────────────────────────────────────────────────────── REQ-B55

@app.get("/author/{author_name}", response_model=AuthorProfile, tags=["Authors"])
def author_profile(author_name: str):
    """**Perfil de um autor** — lista todas as publicações associadas. (REQ-B55)"""
    if not PUBLICATIONS:
        raise HTTPException(status_code=503, detail="Publications data not available.")

    name_lower = author_name.lower()
    pubs = []
    for pub in PUBLICATIONS:
        authors = pub.get("authors", [])
        if isinstance(authors, str):
            authors = [a.strip() for a in authors.split(";")]
        if any(name_lower in (a or "").lower() for a in authors):
            pubs.append(_build_result(pub.get("url", ""), None, pub))

    if not pubs:
        raise HTTPException(status_code=404, detail=f"No publications found for author '{author_name}'.")

    return AuthorProfile(name=author_name, total_publications=len(pubs), publications=pubs)


# ── 7. Document detail ──────────────────────────────────────────────────────

@app.get("/document", response_model=PublicationResult, tags=["Documents"])
def get_document(url: str = Query(..., description="URL/handle do documento")):
    """**Detalhes de um documento** a partir do seu URL."""
    pub = PUB_LOOKUP.get(url)
    if pub is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return _build_result(url, None, pub)


# ── 8. Index stats ──────────────────────────────────────────────────────────

@app.get("/stats", tags=["Info"])
def stats():
    """**Estatísticas do índice** — termos, documentos, top 20 por DF."""
    if not INDEX:
        raise HTTPException(status_code=503, detail="Index not loaded.")
    top_terms = sorted(INDEX.items(), key=lambda x: x[1]["df"], reverse=True)[:20]
    return {
        "total_terms":        len(INDEX),
        "total_documents":    len(ALL_DOC_IDS),
        "top_20_terms_by_df": [
            {"term": t, "document_frequency": d["df"]} for t, d in top_terms
        ],
    }


# ── 9. NLP debug ────────────────────────────────────────────────────────────

@app.get("/debug/preprocess", tags=["Debug"])
def debug_preprocess(text: str = Query(..., description="Texto a pré-processar")):
    """**Debug NLP** — tokens do pipeline de pré-processamento."""
    tokens = preprocess(text)
    return {"input": text, "tokens": tokens, "token_count": len(tokens)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)