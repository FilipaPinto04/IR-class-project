import pytest
import os
import json
from src.search.classifier import train_classifier, categorize_all 

def test_classifier_training_and_output():
    """Valida se o classificador Naïve Bayes treina e gera o ficheiro categorizado."""
    pipeline, report = train_classifier()
    
    assert pipeline is not None
    assert "accuracy" in report or isinstance(report, dict)
    
    categorize_all(pipeline)
    
    output_path = "data/categorized_publications.json"
    assert os.path.exists(output_path), "O classificador falhou a criar o JSON categorizado!"
    
    with open(output_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert isinstance(data, list)
        if len(data) > 0:
            assert "research_area" in data[0], "O classificador não injetou a categoria de metadados!"