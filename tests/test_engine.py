import pytest
from src.search.nlp import preprocess, ReductionMode
from src.search.tfidf import get_custom_ranking

def test_text_preprocessing():
    """Valida se a tokenização, remoção de stop words e stemming funcionam."""
    text = "O RepositóriUM tem publicações científicas sobre engenharia."
    
    tokens_stem = preprocess(text, reduction_mode=ReductionMode.STEMMING, remove_stopwords=True)
    assert len(tokens_stem) > 0
    assert "sobre" not in tokens_stem
    assert "tem" not in tokens_stem

def test_custom_tfidf_ranking():
    """Valida se o teu algoritmo TF-IDF calcula scores e ordena por relevância."""
    mock_index = {
        "computaca": {"df": 1, "postings": {"doc1": {"tf": 3}}},
        "nuvem": {"df": 2, "postings": {"doc1": {"tf": 1}, "doc2": {"tf": 4}}}
    }
    
    results = get_custom_ranking(query_text="computaca", index=mock_index, total_docs=2)
    
    assert len(results) > 0
    assert results[0][0] == "doc1"
    assert results[0][1] > 0 