"""
Implement Multinomial Naïve Bayes classifier
Train classifier on research publication categories
Categorize documents into subject areas automatically
Evaluate classification performance metrics
"""

import json
import os

from sklearn.naive_bayes import MultinomialNB
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    accuracy_score,
)
from sklearn.pipeline import Pipeline
import numpy as np

from src.search.nlp import preprocess

CATEGORIES: dict[str, list[str]] = {
    "computer_science": [
        "machine learning", "neural network", "deep learning", "algorithm",
        "data mining", "artificial intelligence", "computer", "software",
        "programming", "database", "classification", "clustering", "nlp",
        "natural language", "information retrieval", "search engine",
    ],
    "health_medicine": [
        "health", "medical", "clinical", "patient", "disease", "cancer",
        "drug", "treatment", "hospital", "diagnosis", "therapy", "virus",
        "infection", "epidemiology", "pharmacology", "nursing", "surgery",
    ],
    "engineering": [
        "engineering", "mechanical", "electrical", "civil", "structural",
        "bridge", "sensor", "battery", "electrode", "circuit", "robot",
        "automation", "manufacturing", "material", "energy", "power",
    ],
    "social_sciences": [
        "social", "education", "school", "teacher", "student", "pedagogy",
        "society", "culture", "identity", "policy", "governance", "law",
        "economics", "management", "organization", "psychology", "behavior",
    ],
    "natural_sciences": [
        "physics", "chemistry", "biology", "ecology", "environment",
        "climate", "species", "genome", "protein", "cell", "molecular",
        "quantum", "optical", "laser", "astronomy", "mathematics",
    ],
    "arts_humanities": [
        "history", "art", "music", "literature", "philosophy", "language",
        "linguistic", "cultural heritage", "museum", "theatre", "cinema",
        "architecture", "design", "media", "journalism", "communication",
    ],
}


def _assign_label(text: str) -> str:
    """
    Assigns a category label to a document based on keyword matching.
    Returns the category with the most keyword hits, or 'other' if none match.
    """
    text_lower = text.lower()
    scores = {cat: 0 for cat in CATEGORIES}

    for cat, keywords in CATEGORIES.items():
        for kw in keywords:
            if kw in text_lower:
                scores[cat] += 1

    best_cat = max(scores, key=lambda c: scores[c])
    return best_cat if scores[best_cat] > 0 else "other"


def label_publications(
    pubs_path: str = "data/scraper_results.json",
    output_path: str = "data/labelled_publications.json",
) -> list[dict]:
    """
    Labels all publications with a research category using keyword matching.
    Saves labelled data to disk for reuse.
    """
    with open(pubs_path, "r", encoding="utf-8") as f:
        publications = json.load(f)

    labelled = []
    category_counts: dict[str, int] = {}

    for pub in publications:
        text = f"{pub.get('title', '')} {pub.get('abstract', '')}"
        label = _assign_label(text)
        pub_copy = dict(pub)
        pub_copy["category"] = label
        labelled.append(pub_copy)
        category_counts[label] = category_counts.get(label, 0) + 1

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(labelled, f, ensure_ascii=False, indent=2)

    print("\n[REQ-B42] Category distribution:")
    for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
        print(f"  {cat:>20}: {count} documents")

    return labelled


# Build and train the Multinomial Naïve Bayes classifier

def train_classifier(
    labelled_path: str = "data/labelled_publications.json",
    model_output: str = "data/classifier_report.json",
    test_size: float = 0.2,
    random_state: int = 42,
) -> tuple[Pipeline, dict]:
    """
    Trains a Multinomial Naïve Bayes classifier.
    Uses keyword-labelled research publication categories.
    Evaluates and logs classification performance metrics.

    Returns the trained pipeline and the evaluation report dict.
    """
    print("\n" + "=" * 55)
    print("  REQ-B41/B42 — Training Multinomial Naïve Bayes")
    print("=" * 55)

    with open(labelled_path, "r", encoding="utf-8") as f:
        labelled = json.load(f)

    texts  = [f"{p.get('title', '')} {p.get('abstract', '')}" for p in labelled]
    labels = [p.get("category", "other") for p in labelled]

    unique_labels = sorted(set(labels))
    print(f"  Classes   : {unique_labels}")
    print(f"  Documents : {len(texts)}")

    if len(unique_labels) < 2 or len(texts) < 4:
        print("[Warning] Not enough data for train/test split. Training on full dataset.")
        X_train, X_test = texts, texts
        y_train, y_test = labels, labels
    else:
        X_train, X_test, y_train, y_test = train_test_split(
            texts, labels,
            test_size=test_size,
            random_state=random_state,
            stratify=labels if len(texts) >= len(unique_labels) * 2 else None,
        )

    print(f"  Train: {len(X_train)}  |  Test: {len(X_test)}")

    # TF-IDF vectorizer + Multinomial Naïve Bayes
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            preprocessor=lambda t: " ".join(preprocess(t)),
            token_pattern=None,        
            sublinear_tf=True,         
            min_df=1,
        )),
        ("clf", MultinomialNB(alpha=0.1)),   # alpha: Laplace smoothing
    ])

    pipeline.fit(X_train, y_train)
    print("\n  Model trained successfully.")

    # REQ-B44: Evaluation metrics
    report = evaluate_classifier(pipeline, X_test, y_test, unique_labels, model_output)
    return pipeline, report


# Evaluation metrics

def evaluate_classifier(
    pipeline: Pipeline,
    X_test: list[str],
    y_test: list[str],
    labels: list[str],
    output_path: str = "data/classifier_report.json",
) -> dict:
    """
    Computes and logs classification performance metrics:
      - Accuracy
      - Per-class Precision, Recall, F1
      - Confusion matrix
    """
    y_pred = pipeline.predict(X_test)

    accuracy = accuracy_score(y_test, y_pred)
    report   = classification_report(y_test, y_pred, labels=labels, output_dict=True, zero_division=0)
    cm       = confusion_matrix(y_test, y_pred, labels=labels).tolist()

    result = {
        "accuracy":           round(accuracy, 4),
        "classification_report": report,
        "confusion_matrix":   cm,
        "labels":             labels,
    }

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n[REQ-B44] Accuracy: {accuracy:.4f}")
    print("\n  Per-class metrics:")
    for cat in labels:
        if cat in report:
            m = report[cat]
            print(f"  {cat:>20}: P={m['precision']:.2f}  R={m['recall']:.2f}  F1={m['f1-score']:.2f}  support={int(m['support'])}")
    print(f"\n  Confusion matrix saved to: {output_path}")

    return result


# Categorize new documents automatically

def categorize_document(text: str, pipeline: Pipeline) -> str:
    """
    Predicts the research category of a new document.

    Args:
        text:     Raw title + abstract text of the document.
        pipeline: Trained Naïve Bayes pipeline.

    Returns:
        Predicted category string.
    """
    prediction = pipeline.predict([text])[0]
    proba      = pipeline.predict_proba([text])[0]
    classes    = pipeline.classes_

    print(f"\n[REQ-B43] Predicted category: '{prediction}'")
    print("  Confidence per class:")
    for cls, prob in sorted(zip(classes, proba), key=lambda x: -x[1]):
        bar = "█" * int(prob * 20)
        print(f"  {cls:>20}: {prob:.4f} {bar}")

    return prediction


def categorize_all(
    pipeline: Pipeline,
    pubs_path: str = "data/scraper_results.json",
    output_path: str = "data/categorized_publications.json",
) -> list[dict]:
    """
    Applies the trained classifier to all scraped publications
    and saves the results with predicted categories.
    """
    with open(pubs_path, "r", encoding="utf-8") as f:
        publications = json.load(f)

    categorized = []
    for pub in publications:
        text = f"{pub.get('title', '')} {pub.get('abstract', '')}"
        pub_copy = dict(pub)
        pub_copy["predicted_category"] = pipeline.predict([text])[0]
        categorized.append(pub_copy)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(categorized, f, ensure_ascii=False, indent=2)

    print(f"\n[REQ-B43] Categorized {len(categorized)} documents → {output_path}")
    return categorized


# CLI

if __name__ == "__main__":
    print("=== Multinomial Naïve Bayes Classifier ===")
    print("  [1] Label + Train + Evaluate  (REQ-B41/B42/B44)")
    print("  [2] Categorize all documents  (REQ-B43)")
    print("  [3] Classify a custom text    (REQ-B43)")
    print("  [4] Run all")

    choice = input("\nChoice: ").strip()

    pipeline = None

    if choice in ("1", "2", "3", "4"):
        label_publications()
        pipeline, report = train_classifier()

    if choice in ("2", "4") and pipeline:
        categorize_all(pipeline)

    if choice in ("3", "4") and pipeline:
        text = input("\nEnter title + abstract to classify: ").strip()
        if text:
            categorize_document(text, pipeline)