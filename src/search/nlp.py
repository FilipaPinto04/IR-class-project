import nltk
from nltk.corpus import stopwords, wordnet
from nltk.tokenize import word_tokenize
from nltk.stem import PorterStemmer, WordNetLemmatizer
from nltk import pos_tag
from unidecode import unidecode
import string
from enum import Enum

# Required NLTK resources download
nltk.download('punkt_tab', quiet=True)
nltk.download('stopwords', quiet=True)
nltk.download('wordnet', quiet=True)
nltk.download('omw-1.4', quiet=True)
nltk.download('averaged_perceptron_tagger_eng', quiet=True)


class ReductionMode(str, Enum):
    """
    Controls which lexical reduction strategy is applied during preprocessing.

    - STEMMING:      Heuristic-based root extraction (faster, less precise).
    - LEMMATIZATION: Dictionary-based canonical form (slower, more accurate).
    - BOTH:          Lemmatization followed by stemming (default legacy behaviour).
    - NONE:          No reduction applied; tokens are kept as-is after filtering.
    """
    STEMMING = "stemming"
    LEMMATIZATION = "lemmatization"
    BOTH = "both"
    NONE = "none"


# Operadores booleanos e pontuação extra que não devem ser indexados
_BOOLEAN_OPERATORS = {'and', 'or', 'not', 'near'}


def _get_wordnet_pos(treebank_tag: str) -> str:
    """Converte POS tag do Penn Treebank para o formato do WordNet."""
    if treebank_tag.startswith('J'):
        return wordnet.ADJ
    elif treebank_tag.startswith('V'):
        return wordnet.VERB
    elif treebank_tag.startswith('R'):
        return wordnet.ADV
    else:
        return wordnet.NOUN


def preprocess(
    text: str,
    reduction_mode: ReductionMode = ReductionMode.BOTH,
    remove_stopwords: bool = True,
) -> list[str]:
    """
    Performs full text preprocessing for Bilingual Information Retrieval.
    Includes: Normalization, Tokenization, optional Stopword Removal,
    and configurable Lemmatization / Stemming.

    Returns:
        List of processed tokens.
    """
    # Validation: Ensure input is a valid non-empty string
    if not text or not isinstance(text, str):
        return []

    # Normalization & ASCII conversion
    text = unidecode(text.lower())

    # Tokenization
    tokens = word_tokenize(text)

    # Bilingual Stopword Removal
    if remove_stopwords:
        stop_words = set(stopwords.words('portuguese')).union(set(stopwords.words('english')))
        stop_words = {unidecode(sw) for sw in stop_words}
        # Garantir que operadores booleanos são sempre removidos
        stop_words.update(_BOOLEAN_OPERATORS)
    else:
        stop_words = set()

    # Initialize Linguistic Reducers
    stemmer = PorterStemmer() if reduction_mode in (ReductionMode.STEMMING, ReductionMode.BOTH) else None
    lemmatizer = WordNetLemmatizer() if reduction_mode in (ReductionMode.LEMMATIZATION, ReductionMode.BOTH) else None

    # POS tagging apenas se necessário para lematização
    pos_tags: dict[str, str] = {}
    if lemmatizer is not None:
        # Filtrar tokens candidatos antes do POS tag para não passar pontuação
        candidates = [w for w in tokens if w not in stop_words and w not in string.punctuation and len(w) > 1]
        if candidates:
            tagged = pos_tag(candidates)
            pos_tags = {w: _get_wordnet_pos(tag) for w, tag in tagged}

    filtered_tokens = []
    for w in tokens:
        # FIX: era `<= 2`, o que eliminava tokens de 2 caracteres como "ai", "ml"
        if w in stop_words or w in string.punctuation or len(w) <= 1:
            continue

        # REQ-B18 — Apply the configured reduction strategy
        if reduction_mode == ReductionMode.BOTH:
            # FIX: lematização com POS correto em vez de assumir sempre substantivo
            wn_pos = pos_tags.get(w, wordnet.NOUN)
            w = lemmatizer.lemmatize(w, pos=wn_pos)
            w = stemmer.stem(w)
        elif reduction_mode == ReductionMode.LEMMATIZATION:
            wn_pos = pos_tags.get(w, wordnet.NOUN)
            w = lemmatizer.lemmatize(w, pos=wn_pos)
        elif reduction_mode == ReductionMode.STEMMING:
            w = stemmer.stem(w)
        # ReductionMode.NONE: token kept as-is

        filtered_tokens.append(w)

    return filtered_tokens


# Query Expansion via WordNet

def expand_query(
    tokens: list[str],
    max_synonyms_per_token: int = 2,
    reduction_mode: ReductionMode = ReductionMode.BOTH,
) -> list[str]:
    """
    REQ-B47 — Expands a preprocessed token list with WordNet synonyms.

    For each input token, up to ``max_synonyms_per_token`` synonyms are
    retrieved from WordNet synsets, run through the same preprocessing
    pipeline (so they are in the same reduced form as index terms), and
    appended to the token list.  Duplicates and the original tokens are
    excluded from the expansion set to avoid redundancy.

    Strategy
    --------
    1. Look up all synsets for the surface form of the token (English only;
       WordNet coverage of Portuguese is partial via omw-1.4 but we don't
       rely on it here).
    2. Collect lemma names from those synsets, normalise underscores/hyphens,
       and filter out single-character strings and the token itself.
    3. Preprocess each candidate synonym with the same pipeline so it
       matches the index vocabulary.
    4. Take the first ``max_synonyms_per_token`` unique processed forms.

    Args:
        tokens:                  Preprocessed tokens from a user query.
        max_synonyms_per_token:  Maximum synonyms to add per original token.
        reduction_mode:          Must match the mode used when building the index
                                 so expanded terms are in the same form.

    Returns:
        The original token list extended with synonym tokens.
        Originals are always at the front; expansions follow.

    Example
    -------
    >>> expand_query(["cancer"], max_synonyms_per_token=2)
    ['cancer', 'malign', 'tumor']   # exact forms depend on WordNet + stemmer
    """
    if not tokens:
        return tokens

    expanded = list(tokens)
    seen = set(tokens)

    for token in tokens:
        synonyms_added = 0

        for synset in wordnet.synsets(token):
            if synonyms_added >= max_synonyms_per_token:
                break

            for lemma in synset.lemmas():
                if synonyms_added >= max_synonyms_per_token:
                    break

                raw = lemma.name().replace('_', ' ').replace('-', ' ').split()[0]

                # FIX: era `<= 2`, consistente com a correção no preprocess
                if len(raw) <= 1 or raw.lower() == token.lower():
                    continue

                processed = preprocess(raw, reduction_mode=reduction_mode)
                if not processed:
                    continue

                candidate = processed[0]
                if candidate not in seen:
                    expanded.append(candidate)
                    seen.add(candidate)
                    synonyms_added += 1

    return expanded
