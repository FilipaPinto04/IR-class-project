import nltk
from nltk.corpus import stopwords, wordnet
from nltk.tokenize import word_tokenize
from nltk.stem import PorterStemmer, WordNetLemmatizer
from unidecode import unidecode
import string
from enum import Enum

# Required NLTK resources download
nltk.download('punkt_tab', quiet=True)   
nltk.download('stopwords', quiet=True)  
nltk.download('wordnet', quiet=True)   
nltk.download('omw-1.4', quiet=True)    


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
    else:
        stop_words = set()

    # Initialize Linguistic Reducers
    stemmer = PorterStemmer() if reduction_mode in (ReductionMode.STEMMING, ReductionMode.BOTH) else None
    lemmatizer = WordNetLemmatizer() if reduction_mode in (ReductionMode.LEMMATIZATION, ReductionMode.BOTH) else None

    filtered_tokens = []
    for w in tokens:
        if w in stop_words or w in string.punctuation or len(w) <= 2:
            continue

        # REQ-B18 — Apply the configured reduction strategy
        if reduction_mode == ReductionMode.BOTH:
            w = lemmatizer.lemmatize(w)
            w = stemmer.stem(w)
        elif reduction_mode == ReductionMode.LEMMATIZATION:
            w = lemmatizer.lemmatize(w)
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

                if len(raw) <= 2 or raw.lower() == token.lower():
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