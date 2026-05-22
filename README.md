# RepositóriUM Search Engine

Motor de pesquisa de publicações científicas da Universidade do Minho.
Desenvolvido no âmbito da unidade curricular de Pesquisa e Recuperação de Informação (PRI) — 2025/2026.

---

## Estrutura do Projeto

```
IR-class-project/
├── data/                          # Dados gerados (JSON, índice, base de dados)
│   ├── scraper_results.json       # Publicações recolhidas pelo scraper
│   ├── index.json                 # Índice invertido
│   ├── term_document_matrix.json  # Matriz termo-documento
│   ├── search_engine.db           # Base de dados SQLite
│   └── similarity_matrix.json     # Matriz de similaridade entre documentos
├── repositorium-frontend/         # Aplicação React (frontend)
│   ├── src/
│   │   ├── App.jsx                # Componente principal
│   │   ├── main.jsx               # Entry point
│   │   └── styles/main.css        # Estilos
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
├── src/
│   ├── api/
│   │   └── main.py                # API REST (FastAPI)
│   ├── scraper/
│   │   └── scraper.py             # Web scraper (Selenium + DSpace 8)
│   ├── search/
│   │   ├── nlp.py                 # Pre-processamento NLP
│   │   ├── indexer.py             # Construção do índice invertido
│   │   ├── query.py               # Motor de pesquisa booleana
│   │   ├── tfidf.py               # TF-IDF, BM25 e ranking
│   │   ├── classifier.py          # Classificador Naive Bayes
│   │   └── performance.py         # Benchmarks de performance
│   └── database.py                # Camada SQLite
├── tests/
├── requirements.txt
├── docker-compose.yml
└── Dockerfile
```

---

## Requisitos

### Backend (Python 3.11+)

```
fastapi>=0.110.0
uvicorn>=0.28.0
pydantic>=2.6.0
nltk>=3.8.1
unidecode>=1.3.8
scikit-learn>=1.4.0
numpy>=1.26.0
selenium>=4.18.0
requests>=2.31.0
pdfplumber>=0.11.0
```

Instalar dependências:

```bash
pip install -r requirements.txt
```

### Frontend (Node.js 18+)

```bash
cd repositorium-frontend
npm install
```

---

## Instalacao e Execucao

### 1. Recolha de dados (Scraper)

Requer Google Chrome instalado.

```bash
python src/scraper/scraper.py
```

Recolhe até 100 publicações do RepositóriUM. Os primeiros 20 incluem extração de texto do PDF.
Resultado guardado em `data/scraper_results.json`.

### 2. Indexação

```bash
python -m src.search.indexer
```

Constrói o índice invertido com suporte a:
- Postings por campo (título, resumo, autores)
- Listas de posições para pesquisa por frase e proximidade
- Atualizações incrementais
- Matriz termo-documento

Resultado guardado em `data/index.json` e `data/search_engine.db`.

### 3. Classificador (opcional)

```bash
python -m src.search.classifier
```

Treina um classificador Naive Bayes para categorizar automaticamente as publicações por área de investigação.

### 4. Backend (API REST)

```bash
python -m uvicorn src.api.main:app --port 8000
```

A API fica disponível em `http://localhost:8000`.
Documentação interativa em `http://localhost:8000/docs`.

### 5. Frontend

```bash
cd repositorium-frontend
npm run dev
```

A aplicação fica disponível em `http://localhost:3000`.

---

## Funcionalidades

### Pesquisa

- **TF-IDF** (implementacao propria e sklearn) com ranking por relevancia
- **BM25** — esquema de pesagem probabilistico
- **TF puro** — baseline sem penalizacao IDF
- **Booleana** — AND, OR, NOT com precedencia correta (NOT > AND > OR), parenteses, AND implicito
- **Por frase** — termos consecutivos e ordenados (`"machine learning"`)
- **Por proximidade** — dois termos a no maximo k posicoes (`deep NEAR/3 learning`)
- **Por autor** — correspondencia parcial, case-insensitive

### Pre-processamento NLP

- Normalizacao e remocao de acentos
- Tokenizacao bilingue (PT + EN)
- Remocao de stopwords (PT + EN), configuravel
- Lematizacao (WordNet) e stemming (Porter), modo configuravel
- Expansao de query via sinonimos WordNet

### Indice

- Indice invertido com TF por campo (titulo, resumo, autores)
- Listas de posicoes para pesquisa por frase e proximidade
- Frequencia de documento (DF) e frequencia de termo (TF)
- Atualizacoes incrementais
- Skip pointers para intersecao otimizada de postings lists
- Matriz termo-documento

### API REST

| Endpoint | Descricao |
|---|---|
| `GET /search` | Pesquisa TF-IDF, BM25 ou TF-only |
| `GET /search/boolean` | Pesquisa booleana |
| `GET /search/phrase` | Pesquisa por frase exata |
| `GET /search/proximity` | Pesquisa por proximidade |
| `GET /search/author` | Pesquisa por autor |
| `GET /author/{name}` | Perfil de autor |
| `GET /document` | Detalhes de um documento |
| `GET /publications` | Todas as publicacoes |
| `GET /stats` | Estatisticas do indice |
| `GET /debug/preprocess` | Debug NLP |

Suporta resposta em JSON e XML (`?format=xml`).

### Frontend React

- Pesquisa TF-IDF, booleana e por autor com configuracao de algoritmo
- Selecao de modo de reducao: stemming, lematizacao, ambos ou nenhum
- Filtros por campo (titulo, resumo, autores), ano, tipo de documento e area de investigacao
- Expansao de query via WordNet
- Construtor visual de queries booleanas
- Resultados com score, snippet com highlight dos termos, expandir resumo
- Exportacao em JSON, CSV e BibTeX
- Historico de pesquisas e publicacoes guardadas
- Dashboard de estatisticas com graficos
- Painel educativo sobre IR (indice invertido, TF-IDF, booleano, stemming vs lematizacao)
- Design responsivo

---

## Performance e Avaliacao

```bash
python -m src.search.performance
```

Disponibiliza benchmarks de:
- Tempo e memoria de indexacao (REQ-B56, B58)
- Comparacao stemming vs lematizacao (REQ-B57)
- Processamento em batches (REQ-B59)
- Tempo de resposta por metodo de ranking (REQ-B60)
- Metricas de relevancia: Precision, Recall, F1, MAP (REQ-B61)
- Comparacao entre metodos de ranking (REQ-B62)

---

## Docker

```bash
docker-compose up
```

---

## Universidade do Minho — PRI 2025/2026
