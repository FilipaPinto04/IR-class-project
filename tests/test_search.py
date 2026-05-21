import pytest
from src.search.nlp import preprocess

def test_preprocess_basic():
    texto = "O Algoritmo de Pesquisa no RepositóriUM!"
    resultado = preprocess(texto)
    
    assert "algoritmo" in resultado
    assert "pesquisa" in resultado
    assert "repositorium" in resultado
    assert "o" not in resultado  
    assert "!" not in resultado  

def test_preprocess_empty():
    assert preprocess("") == []