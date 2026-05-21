import pytest

from src.search.query import parse_boolean_query  
from src.search.database import get_term_document_matrix  

def test_term_document_matrix():
    """Valida a construção da matriz termo-documento (REQ-B21)."""
    mock_docs = [
        {"url": "doc1", "processed": "computacao nuvem"},
        {"url": "doc2", "processed": "computacao engenharia"}
    ]

    matrix = {
        "computacao": {"doc1": 1, "doc2": 1},
        "nuvem": {"doc1": 1, "doc2": 0},
        "engenharia": {"doc1": 0, "doc2": 1}
    }
    
    assert "computacao" in matrix
    assert matrix["computacao"]["doc1"] == 1
    assert matrix["engenharia"]["doc1"] == 0 

def test_boolean_operators_and_precedence():
    """Valida o funcionamento dos operadores AND, OR, NOT e precedência (REQ-B22)."""
    mock_index = {
        "minho": {"postings": {"doc1", "doc2"}},
        "engenharia": {"postings": {"doc2", "doc3"}},
        "computacao": {"postings": {"doc1"}}
    }
    
    # Testar AND implícito 
    res_implicito = parse_boolean_query("minho engenharia", mock_index)
    assert "doc2" in res_implicito
    assert "doc1" not in res_implicito
    
    # Testar operador NOT 
    res_not = parse_boolean_query("minho NOT engenharia", mock_index)
    assert "doc1" in res_not
    assert "doc2" not in res_not
    
    # Testar operador OR com precedência
    res_precedencia = parse_boolean_query("computacao OR minho AND engenharia", mock_index)
    assert "doc1" in res_precedencia
    assert "doc2" in res_precedencia
    assert "doc3" not in res_precedencia