"""
query.py — Boolean & Phrase/Proximity Retrieval Engine
Universidade do Minho · PRI
"""

import json
import math
import re
from src.search.nlp import preprocess, expand_query, ReductionMode


def load_resources(
    index_path: str = 'data/index.json',
    pubs_path: str  = 'data/scraper_results.json',
) -> tuple[dict, set]:
    try:
        with open(index_path, 'r', encoding='utf-8') as f:
            index = json.load(f)
        with open(pubs_path, 'r', encoding='utf-8') as f:
            pubs = json.load(f)
        all_doc_ids = {p.get('url') for p in pubs if p.get('url')}
        return index, all_doc_ids
    except FileNotFoundError:
        print("Error: Index files not found. Run the indexer first.")
        return None, None


def intersect_with_skips(list1: list, list2: list) -> list:
    answer = []
    i = j = 0
    skip1 = max(1, int(math.sqrt(len(list1))))
    skip2 = max(1, int(math.sqrt(len(list2))))

    while i < len(list1) and j < len(list2):
        if list1[i] == list2[j]:
            answer.append(list1[i])
            i += 1
            j += 1
        elif list1[i] < list2[j]:
            if i + skip1 < len(list1) and list1[i + skip1] <= list2[j]:
                while i + skip1 < len(list1) and list1[i + skip1] <= list2[j]:
                    i += skip1
            else:
                i += 1
        else:
            if j + skip2 < len(list2) and list2[j + skip2] <= list1[i]:
                while j + skip2 < len(list2) and list2[j + skip2] <= list1[i]:
                    j += skip2
            else:
                j += 1
    return answer


def _get_docs_for_term(
    term: str,
    index: dict,
    fields: list[str] | None = None,
) -> set[str]:
    entry = index.get(term, {})
    postings = entry.get("postings", {})

    if fields is None:
        return set(postings.keys())

    matching = set()
    for url, posting in postings.items():
        if isinstance(posting, dict):
            doc_fields = posting.get("fields", [])
            if any(f in doc_fields for f in fields):
                matching.add(url)
        else:
            matching.add(url)
    return matching


def execute_phrase_query(
    phrase: str,
    index: dict,
    fields: list[str] | None = None,
) -> set[str]:
    tokens = preprocess(phrase)
    if not tokens:
        return set()

    if len(tokens) == 1:
        return _get_docs_for_term(tokens[0], index, fields)

    candidate_docs = _get_docs_for_term(tokens[0], index, fields)
    for token in tokens[1:]:
        candidate_docs &= _get_docs_for_term(token, index, fields)

    if not candidate_docs:
        return set()

    results = set()
    for url in candidate_docs:
        pos_lists = []
        valid = True
        for token in tokens:
            posting = index.get(token, {}).get("postings", {}).get(url)
            if posting is None:
                valid = False
                break
            positions = posting["positions"] if isinstance(posting, dict) else []
            pos_lists.append(sorted(positions))

        if not valid or not all(pos_lists):
            continue

        for start_pos in pos_lists[0]:
            if all(
                (start_pos + offset) in set(pos_lists[offset])
                for offset in range(1, len(tokens))
            ):
                results.add(url)
                break

    return results


def execute_proximity_query(
    term1: str,
    term2: str,
    max_distance: int,
    index: dict,
    fields: list[str] | None = None,
) -> set[str]:
    t1_tokens = preprocess(term1)
    t2_tokens = preprocess(term2)
    if not t1_tokens or not t2_tokens:
        return set()

    t1 = t1_tokens[0]
    t2 = t2_tokens[0]

    candidates = _get_docs_for_term(t1, index, fields) & _get_docs_for_term(t2, index, fields)
    results = set()

    for url in candidates:
        p1_posting = index.get(t1, {}).get("postings", {}).get(url)
        p2_posting = index.get(t2, {}).get("postings", {}).get(url)
        if p1_posting is None or p2_posting is None:
            continue

        positions1 = sorted(p1_posting["positions"] if isinstance(p1_posting, dict) else [])
        positions2 = sorted(p2_posting["positions"] if isinstance(p2_posting, dict) else [])

        i = j = 0
        found = False
        while i < len(positions1) and j < len(positions2) and not found:
            gap = abs(positions1[i] - positions2[j])
            if gap <= max_distance:
                found = True
            elif positions1[i] < positions2[j]:
                i += 1
            else:
                j += 1

        if found:
            results.add(url)

    return results


class _Lexer:
    _NEAR_RE    = re.compile(r'near/(\d+)', re.IGNORECASE)
    _PHRASE_RE  = re.compile(r'"([^"]*)"')
    _OPERATORS  = {'and', 'or', 'not'}

    def __init__(self, query: str):
        self._tokens: list[tuple[str, object]] = []
        self._pos = 0
        self._tokenise(query)

    def _tokenise(self, query: str) -> None:
        phrase_map: dict[str, str] = {}
        def _replace_phrase(m: re.Match) -> str:
            key = f"__PHRASE_{len(phrase_map)}__"
            phrase_map[key] = m.group(1)
            return f" {key} "

        query = self._PHRASE_RE.sub(_replace_phrase, query)
        query = query.replace('(', ' ( ').replace(')', ' ) ')
        raw_tokens = query.split()

        for raw in raw_tokens:
            raw_lower = raw.lower()

            if raw in phrase_map:
                self._tokens.append(('PHRASE', phrase_map[raw]))
            elif raw_lower in self._OPERATORS:
                self._tokens.append(('OP', raw_lower.upper()))
            elif self._NEAR_RE.fullmatch(raw_lower):
                k = int(self._NEAR_RE.fullmatch(raw_lower).group(1))
                self._tokens.append(('NEAR', k))
            elif raw == '(':
                self._tokens.append(('LPAREN', '('))
            elif raw == ')':
                self._tokens.append(('RPAREN', ')'))
            else:
                self._tokens.append(('WORD', raw))

    def peek(self) -> tuple[str, object] | None:
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        return None

    def consume(self) -> tuple[str, object]:
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def match_op(self, *ops: str) -> bool:
        tok = self.peek()
        return tok is not None and tok[0] == 'OP' and tok[1] in ops

    def is_operand(self) -> bool:
        tok = self.peek()
        return tok is not None and tok[0] in ('WORD', 'PHRASE', 'LPAREN', 'NEAR') or (
            tok is not None and tok[0] == 'OP' and tok[1] == 'NOT'
        )


class BooleanParser:
    def __init__(
        self,
        index: dict,
        all_doc_ids: set[str],
        fields: list[str] | None = None,
        expand: bool = False,
    ):
        self._index        = index
        self._all_doc_ids  = all_doc_ids
        self._fields       = fields
        self._expand       = expand

    def parse(self, query: str) -> set[str]:
        lexer = _Lexer(query)
        result = self._expr(lexer)
        return result if result is not None else set()

    def _expr(self, lex: _Lexer) -> set[str]:
        left = self._term(lex)
        while lex.match_op('OR'):
            lex.consume()
            right = self._term(lex)
            left = (left if left is not None else set()) | (right if right is not None else set())
        return left if left is not None else set()

    def _term(self, lex: _Lexer) -> set[str]:
        left = self._factor(lex)
        # Track whether left was explicitly initialised (even if empty).
        # We use a sentinel None to distinguish "not yet set" from "empty set".
        left_initialised = left is not None

        while lex.is_operand() and not lex.match_op('OR'):
            if lex.match_op('AND'):
                lex.consume()
            right = self._factor(lex)

            if not left_initialised:
                # First operand was None (shouldn't happen, but guard anyway)
                left = right if right is not None else set()
                left_initialised = True
            else:
                # Both sides are real sets — intersect even if one is empty.
                # Do NOT use `left or []` because set() is falsy and would
                # incorrectly skip the intersection with a genuinely empty set.
                l_sorted = sorted(left)   if left  is not None else []
                r_sorted = sorted(right)  if right is not None else []
                left = set(intersect_with_skips(l_sorted, r_sorted))

        return left if left is not None else set()

    def _factor(self, lex: _Lexer) -> set[str]:
        tok = lex.peek()
        if tok is None:
            return set()

        kind, value = tok

        if kind == 'OP' and value == 'NOT':
            lex.consume()
            operand = self._factor(lex)
            return self._all_doc_ids - (operand if operand is not None else set())

        if kind == 'LPAREN':
            lex.consume()
            result = self._expr(lex)
            if lex.peek() and lex.peek()[0] == 'RPAREN':
                lex.consume()
            return result if result is not None else set()

        if kind == 'PHRASE':
            lex.consume()
            return execute_phrase_query(value, self._index, self._fields)

        if kind == 'WORD':
            tokens_ahead = lex._tokens
            pos = lex._pos
            if (pos + 2 < len(tokens_ahead)
                    and tokens_ahead[pos + 1][0] == 'NEAR'
                    and tokens_ahead[pos + 2][0] == 'WORD'):
                word1 = lex.consume()[1]
                k     = lex.consume()[1]
                word2 = lex.consume()[1]
                return execute_proximity_query(word1, word2, k, self._index, self._fields)

            lex.consume()
            return self._resolve_word(value)

        lex.consume()
        return set()

    def _resolve_word(self, raw: str) -> set[str]:
        """
        Preprocess the raw word and look it up in the index.
        If preprocessing removes the word (e.g. it's a stopword like 'silva'),
        fall back to searching the raw lowercased form directly in the index.
        This ensures proper nouns used as author names are still found.
        """
        from nltk.stem import PorterStemmer
        from unidecode import unidecode

        base_tokens = preprocess(raw)

        # Fallback: if preprocessing eliminated the word (stopword / too short),
        # try the raw form and common stemmed variants directly in the index
        if not base_tokens:
            raw_norm = unidecode(raw.lower())
            # Try exact match in index
            if raw_norm in self._index:
                return _get_docs_for_term(raw_norm, self._index, self._fields)
            # Try stemmed form
            stemmer = PorterStemmer()
            stemmed = stemmer.stem(raw_norm)
            if stemmed in self._index:
                return _get_docs_for_term(stemmed, self._index, self._fields)
            return set()

        if self._expand:
            tokens = expand_query(base_tokens, max_synonyms_per_token=2)
        else:
            tokens = base_tokens

        docs: set[str] = set()
        for token in tokens:
            docs |= _get_docs_for_term(token, self._index, self._fields)
        return docs


def execute_boolean_query(
    query: str,
    index: dict,
    all_doc_ids: set[str],
    fields: list[str] | None = None,
    expand: bool = False,
) -> set[str]:
    parser = BooleanParser(index, all_doc_ids, fields=fields, expand=expand)
    return parser.parse(query)


def main() -> None:
    index, all_doc_ids = load_resources()
    if not index:
        return

    print("\n" + "=" * 55)
    print("   BILINGUAL BOOLEAN SEARCH ENGINE (v3.0)   ")
    print("=" * 55)

    while True:
        raw = input("\nEnter query (or 'exit'): ").strip()
        if raw.lower() in ('exit', 'quit', 'sair'):
            break

        fields = None
        expand = False
        if '--title' in raw:
            fields = ['title']
            raw = raw.replace('--title', '').strip()
        elif '--abstract' in raw:
            fields = ['abstract']
            raw = raw.replace('--abstract', '').strip()
        if '--expand' in raw:
            expand = True
            raw = raw.replace('--expand', '').strip()

        matches = execute_boolean_query(raw, index, all_doc_ids, fields=fields, expand=expand)

        if matches:
            print(f"\n[Success] Found {len(matches)} document(s):")
            for url in sorted(matches)[:20]:
                print(f"  -> {url}")
        else:
            print("\n[Notice] No documents found matching that query.")


if __name__ == "__main__":
    main()