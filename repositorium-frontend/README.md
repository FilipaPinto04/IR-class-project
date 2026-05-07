# RepositóriUM Frontend

Motor de pesquisa de publicações científicas — Universidade do Minho  
Unidade Curricular: Pesquisa e Recuperação de Informação · 2025/2026

## Requisitos
- Node.js 18+
- Backend FastAPI a correr em `http://localhost:8000`

## Instalação e arranque

```bash
# Instalar dependências
npm install

# Arrancar em modo de desenvolvimento
npm run dev
```

A aplicação fica disponível em **http://localhost:3000**.

## Build para produção

```bash
npm run build
# Ficheiros gerados em /dist
```

## Funcionalidades implementadas

### Pesquisa
- **TF-IDF** (implementação própria ou sklearn) com ranking por relevância
- **Booleana** — AND / OR / NOT com precedência correta, frases exatas (`"..."`) e proximidade (`NEAR/k`)
- **Por autor** — pesquisa parcial, case-insensitive

### Configuração de pesquisa
- Seleção do algoritmo de ranking (TF-IDF custom vs sklearn)
- Restrição de campos (título / resumo / todos)
- Expansão de query via WordNet
- Filtros por ano e tipo de documento

### Resultados
- Ranking com barra de pontuação visual por resultado
- Snippets com destaque dos termos pesquisados
- Perfis de autores clicáveis
- Expansão do resumo completo
- Links para PDF e DOI
- Exportação em JSON, CSV e BibTeX
- Paginação

### Funcionalidades educativas
- Painel "Como funciona" com 4 tabs:
  - Índice Invertido (visualização de postings)
  - TF-IDF (fórmulas interativas)
  - Pesquisa Booleana (operadores e exemplos)
  - Stemming vs Lematização (tabela comparativa)

### Outras
- Construtor visual de queries Boolean (drag-and-drop de operadores)
- Histórico de pesquisas (localStorage)
- Publicações guardadas (localStorage)
- Dashboard de estatísticas do índice (top termos por DF)
- Design responsivo (mobile + desktop)

## Estrutura

```
src/
├── App.jsx          # Componente principal + toda a lógica
├── main.jsx         # Entry point React
└── styles/
    └── main.css     # Sistema de design completo com CSS variables
```

## Requisitos cobertosr

| Requisito | Descrição | Status |
|-----------|-----------|--------|
| REQ-F01–F05 | Layout académico, responsivo, navegação, branding | ✅ |
| REQ-F06–F10 | Caixa de pesquisa, sintaxe, exemplos, validação | ✅ |
| REQ-F11–F14 | Stemming/lematização, stop words, idioma, config | ✅ |
| REQ-F15–F17 | Campos de pesquisa, área, modo autor | ✅ |
| REQ-F18–F20 | Seleção de algoritmo ranking | ✅ |
| REQ-F21–F26 | Lista resultados, scores, títulos, autores, datas, snippets | ✅ |
| REQ-F27–F30 | PDF, abstract, guardar, exportar | ✅ |
| REQ-F31–F34 | Paginação, resultados por página, total, tempo | ✅ |
| REQ-F35–F36 | Página de autor com lista de publicações | ✅ |
| REQ-F39–F42 | Query builder visual | ✅ |
| REQ-F43–F46 | Filtros data, tipo documento | ✅ |
| REQ-F47–F50 | Secções educativas IR | ✅ |
| REQ-F55–F58 | Dashboard estatísticas (termos, documentos, top DF) | ✅ |
| REQ-F59–F62 | Histórico de pesquisas, guardar, exportar | ✅ |
| REQ-F75–F78 | API REST, async, error handling, caching | ✅ |
| REQ-F87–F90 | Keyboard nav, HTML semântico, focus indicators | ✅ |
