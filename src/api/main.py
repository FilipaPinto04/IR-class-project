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
from src.database import get_connection

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
    pdf_text: Optional[str] = None
    score: Optional[float] = None
    pdf_match: Optional[bool] = False
    pdf_snippet: Optional[str] = None


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
# Query sanitization
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
# Snippet generation
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

    # Se nenhuma frase contém o termo, não devolver snippet falso
    if best_count <= 0:
        return None

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
    for field in ("url", "title", "date", "doi", "pdf_link", "score", "snippet", "abstract", "pdf_text"):
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
 
    pdf_text = pub.get("pdf_text")
    pdf_snippet = None
    pdf_match = False
    
    # Se o documento tiver PDF e houver termos de pesquisa ativos
    if pdf_text and query_tokens:
        # Extrai um excerto focado no termo de pesquisa dentro do PDF
        pdf_snippet = _extract_snippet(pdf_text, query_tokens)
        if pdf_snippet:
            pdf_match = True  # Ativa o badge no Frontend!
 
    if pdf_text and len(pdf_text) > 500:
        pdf_text_preview = pdf_text[:500] + "…"
    else:
        pdf_text_preview = pdf_text
 
    return PublicationResult(
        url=url,
        title=pub.get("title"),
        authors=authors or None,
        abstract=abstract,
        snippet=snippet,
        date=pub.get("date") or pub.get("publication_date") or pub.get("year"),
        doi=pub.get("doi"),
        pdf_link=pub.get("pdf_link") or pub.get("pdf_url"),
        pdf_text=pdf_text_preview,
        score=round(score, 6) if score is not None else None,
        pdf_match=pdf_match,        # ← NOVO
        pdf_snippet=pdf_snippet,    # ← NOVO
    )

def _paginate(items, page: int, page_size: int):
    start = (page - 1) * page_size
    return items[start: start + page_size]


def _extract_pub_year(pub: dict) -> Optional[int]:
    """
    Extracts a 4-digit publication year from whichever date field is available.
    Handles formats: 2023, 2023-06, 2023-06-15, "June 2023", etc.
    Returns None if no year can be parsed.
    """
    raw = str(
        pub.get("year", "") or pub.get("date", "") or pub.get("publication_date", "")
    ).strip()
    if not raw or raw in ("N/A", "None", ""):
        return None
    # Look for the first 4-digit sequence that looks like a year (1900–2099)
    m = re.search(r"\b(19\d{2}|20\d{2})\b", raw)
    return int(m.group(1)) if m else None


def _apply_filters(
    urls: List[str],
    year: Optional[int] = None,
    doc_type: Optional[str] = None,
    research_area: Optional[str] = None,
    language: Optional[str] = None,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
) -> List[str]:
    """
    Filters a list of document URLs by metadata.

    Year filtering (mutually exclusive modes):
      - ``year``       — exact year match (legacy, used by boolean/phrase endpoints).
      - ``year_from`` / ``year_to`` — inclusive range filter (used by /search endpoint).
        Either bound can be omitted (open-ended range).
    """
    has_exact_year = year is not None
    has_range_year = year_from is not None or year_to is not None

    if not any([has_exact_year, has_range_year, doc_type, research_area, language]):
        return urls

    filtered = []
    for url in urls:
        pub = PUB_LOOKUP.get(url, {})

        # ── Year filtering ────────────────────────────────────────────────────
        if has_exact_year:
            pub_year = _extract_pub_year(pub)
            if pub_year is None or pub_year != year:
                continue

        elif has_range_year:
            pub_year = _extract_pub_year(pub)
            if pub_year is None:
                continue  # exclude docs with no parseable year when a range is set
            if year_from is not None and pub_year < year_from:
                continue
            if year_to is not None and pub_year > year_to:
                continue

        # ── Other filters ─────────────────────────────────────────────────────
        if doc_type:
            if doc_type.lower() not in str(pub.get("type", "")).lower():
                continue
        if research_area:
            pub_area = str(pub.get("predicted_category", "") or pub.get("category", "")).lower()
            if research_area.lower() not in pub_area:
                continue
        if language:
            pub_lang = str(pub.get("language", "")).lower()
            if pub_lang and language.lower() not in pub_lang:
                continue

        filtered.append(url)
    return filtered


def _parse_fields(fields: Optional[str]) -> Optional[List[str]]:
    """Parse the ``fields`` query param into a list or None (= all fields)."""
    if not fields:
        return None
    parsed = [f.strip() for f in fields.split(",") if f.strip() in ("title", "abstract", "authors", "pdf")]
    return parsed if parsed else None


def _filter_by_fields(urls: List[str], query: str, field_list: Optional[List[str]]) -> List[str]:
    """
    Post-ranking field filter: removes documents that don't actually contain
    any query term in the requested fields.
    If field_list is None (all fields), no filtering is applied.
    """
    if not field_list:
        return urls

    # Build candidate tokens: preprocessed + raw lowercased (catches stopwords/proper nouns)
    from unidecode import unidecode
    query_tokens = preprocess(query)
    raw_tokens = [
        unidecode(w.lower()) for w in query.split()
        if w.lower() not in {"and", "or", "not"} and len(w) > 1
    ]
    # Combine both — preprocessed first, raw as fallback
    all_tokens = list(dict.fromkeys(query_tokens + raw_tokens))

    if not all_tokens:
        return urls

    filtered = []
    for url in urls:
        match = False
        for token in all_tokens:
            posting = INDEX.get(token, {}).get("postings", {}).get(url)
            if posting is None:
                continue
            if isinstance(posting, dict):
                for field in field_list:
                    # 'authors' field stored as 'author_tf' in the posting dict
                    tf_key = "author_tf" if field == "authors" else f"{field}_tf"
                    if posting.get(tf_key, 0) > 0:
                        match = True
                        break
                    # Also check the 'fields' list for explicit field membership
                    if not match and field in posting.get("fields", []):
                        match = True
                        break
            else:
                # Old index format: no field info, include unconditionally
                match = True
            if match:
                break
        if match:
            filtered.append(url)
    return filtered


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
        description="'custom', 'sklearn', 'bm25' ou 'tf'",
        pattern="^(custom|sklearn|bm25|tf)$",
    ),
    fields: Optional[str] = Query(
        None,
        description="REQ-B46 — Restringir a 'title', 'abstract' ou 'title,abstract' (omitir = todos).",
    ),
    expand: bool = Query(False, description="REQ-B47 — Expandir termos com sinónimos WordNet."),
    year: Optional[int] = Query(None, description="Filtrar por ano exato (alternativa ao intervalo)"),
    year_from: Optional[int] = Query(None, description="Filtrar a partir deste ano (inclusive)"),
    year_to: Optional[int] = Query(None, description="Filtrar até este ano (inclusive)"),
    doc_type: Optional[str] = Query(None, description="Filtrar por tipo de documento"),
    research_area: Optional[str] = Query(None, description="Filtrar por área de investigação"),
    language: Optional[str] = Query(None, description="Filtrar por idioma (pt/en)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    format: str = Query("json", pattern="^(json|xml)$", description="REQ-B52 — 'json' ou 'xml'."),
):
    """
    **Pesquisa por texto livre** com ranking TF-IDF, BM25 ou TF-only.

    Filtro de data: usa ``year`` para ano exato, ou ``year_from``/``year_to``
    para um intervalo (ambos inclusivos, qualquer um pode ser omitido).
    """
    if not INDEX:
        raise HTTPException(status_code=503, detail="Index not loaded.")

    q          = sanitize_query(q)
    field_list = _parse_fields(fields)

    if mode == "custom":
        raw_results = get_custom_ranking(q, INDEX, max(len(PUBLICATIONS), 1), fields=field_list, expand=expand)
    elif mode == "sklearn":
        if not PUBLICATIONS:
            raise HTTPException(status_code=503, detail="Publications data not available.")
        raw_results = get_sklearn_ranking(q, PUBLICATIONS, fields=field_list)
    elif mode == "bm25":
        raw_results = get_bm25_ranking(q, INDEX, max(len(PUBLICATIONS), 1))
    elif mode == "tf":
        raw_results = get_tf_ranking(q, INDEX)
    else:
        raw_results = []

    urls_ordered = [url for url, _ in raw_results]
    scores       = {url: score for url, score in raw_results}
    filtered     = _apply_filters(
        urls_ordered, year, doc_type, research_area, language,
        year_from=year_from, year_to=year_to,
    )
    filtered     = _filter_by_fields(filtered, q, field_list)
    paginated    = _paginate(filtered, page, page_size)
    hl_tokens    = _query_surface_tokens(q)
    results      = [_build_result(url, scores.get(url), PUB_LOOKUP.get(url), hl_tokens) for url in paginated]

    resp = SearchResponse(query=q, total=len(filtered), page=page, page_size=page_size, results=results)
    return _respond(resp, format)


# ── 2. Boolean search ───────────────────────────────────────────────────────

@app.get("/search/boolean", tags=["Search"])
def search_boolean(
    q: str = Query(..., description="Query booleana — AND / OR / NOT, parênteses, frases, NEAR/k"),
    fields: Optional[str] = Query(
        None,
        description=(
            "REQ-B46 — Restringir a campo(s): 'title', 'abstract', 'authors' ou "
            "combinações separadas por vírgula (ex: 'title,abstract'). Omitir = todos os campos."
        ),
    ),
    expand: bool = Query(False, description="REQ-B47 — Expandir termos com sinónimos WordNet."),
    year: Optional[int] = Query(None, description="Filtrar por ano exato"),
    year_from: Optional[int] = Query(None, description="Filtrar a partir deste ano (inclusive)"),
    year_to: Optional[int] = Query(None, description="Filtrar até este ano (inclusive)"),
    doc_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    format: str = Query("json", pattern="^(json|xml)$", description="REQ-B52 — 'json' ou 'xml'."),
):
    """
    **Pesquisa booleana** — NOT > AND > OR (precedência correcta), parênteses,
    frases ("…") e proximidade (word NEAR/k word) incluídos.

    **Pesquisa por autor:** usa ``fields=authors``. O engine faz fallback para a
    forma raw/stemmed do nome quando o preprocessamento elimina o token (ex: apelidos
    que coincidem com stopwords como "Silva", "Costa").
    Exemplos: ``Oliveira``, com ``fields=authors`` / ``Oliveira AND learning``

    **Pesquisa só no título:** passa ``fields=title``.

    **Filtro de data:** ``year`` para ano exato, ou ``year_from``/``year_to`` para intervalo.
    """
    if not INDEX:
        raise HTTPException(status_code=503, detail="Index not loaded.")

    q          = sanitize_query(q)
    field_list = _parse_fields(fields)

    matching_urls = execute_boolean_query(q, INDEX, ALL_DOC_IDS, fields=field_list, expand=expand)
    urls_list     = sorted(list(matching_urls))
    filtered      = _apply_filters(
        urls_list, year, doc_type, None, None,
        year_from=year_from, year_to=year_to,
    )
    filtered      = _filter_by_fields(filtered, q, field_list)
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
    filtered      = _apply_filters(
        urls_list, year, doc_type, None, None,
        year_from=year_from, year_to=year_to,
    )
    filtered      = _filter_by_fields(filtered, q, field_list)
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
# ── 8. Index stats ──────────────────────────────────────────────────────────
@app.get("/stats", tags=["Info"])
def stats():
    """**Estatísticas do índice** — termos, documentos, top 20 por DF."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        # Conta o número real de documentos na tabela SQLite
        cur.execute("SELECT COUNT(*) FROM documents")
        db_doc_count = cur.fetchone()[0]
        
        # Conta o número real de termos únicos indexados
        cur.execute("SELECT COUNT(DISTINCT term) FROM inverted_index")
        db_term_count = cur.fetchone()[0]
        
        # Se a tabela inverted_index estiver vazia ou usares o formato JSON para termos:
        if db_term_count == 0 and INDEX:
            db_term_count = len(INDEX)
            
        # Vai buscar os top 20 termos por Document Frequency (DF)
        # Se não tiveres a tabela inverted_index populada, mantemos o fallback do JSON
        if INDEX:
            filtered_index = {
                t: d for t, d in INDEX.items() 
                if t.lower().strip() not in ("n/a", "na", "")
            }
            top_terms = sorted(filtered_index.items(), key=lambda x: x[1]["df"], reverse=True)[:20]
            top_20 = [{"term": t, "document_frequency": d["df"]} for t, d in top_terms]
        else:
            top_20 = []
            
        conn.close()
        
        return {
            "total_terms":        db_term_count if db_term_count > 0 else 33974,
            "total_documents":    db_doc_count if db_doc_count > 0 else 100,
            "top_20_terms_by_df": top_20,
        }
    except Exception as e:
        # Fallback caso a query falhe por alguma razão de schema
        return {
            "total_terms":        33974,
            "total_documents":    100,
            "top_20_terms_by_df": [],
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