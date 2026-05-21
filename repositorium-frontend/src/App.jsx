import { useState, useEffect, useCallback, useRef } from "react";
import "./styles/main.css";

const API_BASE = "http://localhost:8000";

// ─── API ──────────────────────────────────────────────────────────────────────
async function apiFetch(endpoint, params = {}) {
  const url = new URL(`${API_BASE}${endpoint}`);
  Object.entries(params).forEach(([k, v]) => {
    if (v !== null && v !== undefined && v !== "") url.searchParams.set(k, v);
  });
  const res = await fetch(url);
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

// ─── REQ-F81: URL ROUTING UTILITIES ──────────────────────────────────────────
function readSearchParams() {
  const p = new URLSearchParams(window.location.search);
  return {
    q: p.get("q") || "",
    mode: p.get("mode") || "tfidf",
    rankMode: p.get("rank") || "custom",
    year: p.get("year") || "",
    docType: p.get("type") || "",
    page: parseInt(p.get("page") || "1", 10),
  };
}

function writeSearchParams(params) {
  const p = new URLSearchParams();
  if (params.q) p.set("q", params.q);
  if (params.mode && params.mode !== "tfidf") p.set("mode", params.mode);
  if (params.rankMode && params.rankMode !== "custom") p.set("rank", params.rankMode);
  if (params.year) p.set("year", params.year);
  if (params.docType) p.set("type", params.docType);
  if (params.page && params.page > 1) p.set("page", params.page);
  const qs = p.toString();
  const newUrl = qs ? `${window.location.pathname}?${qs}` : window.location.pathname;
  window.history.replaceState(null, "", newUrl);
}

// ─── REQ-F63/F64: USER PREFERENCES ───────────────────────────────────────────
const PREF_KEY = "pri_user_prefs";
const DEFAULT_PREFS = {
  rankMode: "custom",
  reductionMode: "both",
  removeStopwords: true,
  pageSize: 10,
  language: "pt",
  compactView: false,
};

function loadPrefs() {
  try { return { ...DEFAULT_PREFS, ...JSON.parse(localStorage.getItem(PREF_KEY) || "{}") }; }
  catch { return DEFAULT_PREFS; }
}

function savePrefs(prefs) {
  localStorage.setItem(PREF_KEY, JSON.stringify(prefs));
}

function usePreferences() {
  const [prefs, setPrefs] = useState(loadPrefs);
  const update = useCallback((patch) => {
    setPrefs(prev => {
      const next = { ...prev, ...patch };
      savePrefs(next);
      return next;
    });
  }, []);
  return { prefs, update };
}

// ─── REQ-F10: QUERY VALIDATION ────────────────────────────────────────────────
const BOOLEAN_OPS = ["AND", "OR", "NOT"];

function validateQuery(query, mode) {
  if (!query.trim()) return null;
  if (query.length > 500) return { type: "error", msg: "Query demasiado longa (máx. 500 caracteres)." };

  if (mode === "boolean") {
    // Unbalanced parentheses
    let depth = 0;
    for (const ch of query) {
      if (ch === "(") depth++;
      if (ch === ")") depth--;
      if (depth < 0) return { type: "error", msg: "Parêntese de fecho sem abertura correspondente." };
    }
    if (depth > 0) return { type: "error", msg: `${depth} parêntese(s) por fechar.` };

    // Operator at start or end
    const tokens = query.trim().toUpperCase().split(/\s+/);
    if (BOOLEAN_OPS.includes(tokens[0]) && tokens[0] !== "NOT")
      return { type: "error", msg: `Não pode começar com o operador "${tokens[0]}".` };
    if (BOOLEAN_OPS.includes(tokens[tokens.length - 1]))
      return { type: "error", msg: `Não pode terminar com o operador "${tokens[tokens.length - 1]}".` };

    // Consecutive operators
    for (let i = 0; i < tokens.length - 1; i++) {
      if (BOOLEAN_OPS.includes(tokens[i]) && BOOLEAN_OPS.includes(tokens[i + 1]) && tokens[i + 1] !== "NOT")
        return { type: "error", msg: `Operadores consecutivos: "${tokens[i]} ${tokens[i + 1]}".` };
    }

    // Hint: operators must be uppercase
    const lowerOps = ["and", "or", "not"];
    for (const op of lowerOps) {
      if (query.split(" ").includes(op))
        return { type: "warning", msg: `Operadores em minúsculas detectados — usa AND, OR, NOT em maiúsculas.` };
    }
  }

  if (mode === "tfidf" && query.trim().split(/\s+/).length > 20)
    return { type: "warning", msg: "Query muito longa. Considera usar apenas os termos mais relevantes." };

  return { type: "ok", msg: "Query válida." };
}

const QueryValidation = ({ query, mode }) => {
  const result = validateQuery(query, mode);
  if (!query || !result || result.type === "ok") return null;
  const colors = { error: "#dc2626", warning: "#d97706" };
  return (
    <div style={{ fontSize: ".78rem", marginTop: "4px", color: colors[result.type], display: "flex", alignItems: "center", gap: "4px" }}>
      {result.type === "error" ? "✕" : "⚠"} {result.msg}
    </div>
  );
};

// ─── ICONS ────────────────────────────────────────────────────────────────────
const Icon = ({ name, size = 16 }) => {
  const icons = {
    search: <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>,
    book: <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>,
    user: <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>,
    chart: <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>,
    info: <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>,
    filter: <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>,
    chevronDown: <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"/></svg>,
    chevronUp: <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="18 15 12 9 6 15"/></svg>,
    externalLink: <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>,
    pdf: <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>,
    x: <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>,
    help: <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>,
    save: <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>,
    clock: <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>,
    zap: <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>,
    compare: <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="8" height="18" rx="1"/><rect x="13" y="3" width="8" height="18" rx="1"/></svg>,
    settings: <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>,
    globe: <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>,
    share: <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>,
    network: <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="5" r="2"/><circle cx="5" cy="19" r="2"/><circle cx="19" cy="19" r="2"/><line x1="12" y1="7" x2="5" y2="17"/><line x1="12" y1="7" x2="19" y2="17"/><line x1="5" y1="19" x2="19" y2="19"/></svg>,
  };
  return icons[name] || null;
};

// ─── REQ-F68: CONTEXTUAL TOOLTIP ─────────────────────────────────────────────
const Tooltip = ({ text, children }) => {
  const [show, setShow] = useState(false);
  return (
    <span className="tooltip-wrap" onMouseEnter={() => setShow(true)} onMouseLeave={() => setShow(false)}>
      {children}
      {show && <div className="tooltip-box">{text}</div>}
    </span>
  );
};

// ─── SCORE BAR ────────────────────────────────────────────────────────────────
const ScoreBar = ({ score }) => {
  if (!score) return null;
  const pct = Math.min(score * 100 * 5, 100);
  return (
    <div className="score-bar">
      <div className="score-bar-fill" style={{ width: `${pct}%` }} />
      <span className="score-val">{score.toFixed(4)}</span>
    </div>
  );
};

// ─── SEARCH HISTORY ───────────────────────────────────────────────────────────
function useSearchHistory() {
  const [history, setHistory] = useState(() => {
    try { return JSON.parse(localStorage.getItem("pri_history") || "[]"); }
    catch { return []; }
  });
  const add = useCallback((entry) => {
    setHistory(prev => {
      const next = [entry, ...prev.filter(h => h.q !== entry.q)].slice(0, 20);
      localStorage.setItem("pri_history", JSON.stringify(next));
      return next;
    });
  }, []);
  const clear = useCallback(() => {
    setHistory([]);
    localStorage.removeItem("pri_history");
  }, []);
  return { history, add, clear };
}

// ─── SAVED RESULTS ────────────────────────────────────────────────────────────
function useSaved() {
  const [saved, setSaved] = useState(() => {
    try { return JSON.parse(localStorage.getItem("pri_saved") || "[]"); }
    catch { return []; }
  });
  const toggle = useCallback((pub) => {
    setSaved(prev => {
      const exists = prev.some(p => p.url === pub.url);
      const next = exists ? prev.filter(p => p.url !== pub.url) : [pub, ...prev];
      localStorage.setItem("pri_saved", JSON.stringify(next));
      return next;
    });
  }, []);
  const isSaved = (url) => saved.some(p => p.url === url);
  return { saved, toggle, isSaved };
}

// ─── SNIPPET ─────────────────────────────────────────────────────────────────
const Snippet = ({ html }) => {
  if (!html) return null;
  return <p className="snippet" dangerouslySetInnerHTML={{ __html: html }} />;
};

// ─── RESULT CARD ──────────────────────────────────────────────────────────────
const ResultCard = ({ result, rank, isSaved, onSave, onAuthorClick, compact }) => {
  const [expanded, setExpanded] = useState(false);
  return (
    <article className={`result-card ${compact ? "compact" : ""}`} style={{ animationDelay: `${rank * 40}ms` }}>
      <div className="result-rank">
        <span className="rank-num">{rank}</span>
        <ScoreBar score={result.score} />
      </div>
      <div className="result-body">
        <h3 className="result-title">
          {result.url ? (
            <a href={result.url} target="_blank" rel="noopener noreferrer">
              {result.title || "Sem título"}
              <Icon name="externalLink" size={13} />
            </a>
          ) : (result.title || "Sem título")}
        </h3>
        {result.authors?.length > 0 && (
          <div className="result-authors">
            {result.authors.map((a, i) => (
              <button key={i} className="author-chip" onClick={() => onAuthorClick(a)}>{a}</button>
            ))}
          </div>
        )}
        {result.date && <span className="result-date">{result.date}</span>}
        {result.snippet
          ? <Snippet html={result.snippet} />
          : result.abstract && !expanded && (
              <p className="snippet">{result.abstract.slice(0, 200)}{result.abstract.length > 200 ? "…" : ""}</p>
            )
        }
        {result.abstract && (
          <button className="btn-text" onClick={() => setExpanded(e => !e)}>
            <Icon name={expanded ? "chevronUp" : "chevronDown"} size={13} />
            {expanded ? "Ocultar resumo" : "Ver resumo completo"}
          </button>
        )}
        {expanded && <p className="abstract-full">{result.abstract}</p>}
        <div className="result-actions">
          {result.pdf_link && (
            <a className="btn-action" href={result.pdf_link} target="_blank" rel="noopener noreferrer">
              <Icon name="pdf" size={13} /> PDF
            </a>
          )}
          {result.doi && (
            <a className="btn-action" href={`https://doi.org/${result.doi}`} target="_blank" rel="noopener noreferrer">
              DOI
            </a>
          )}
          <button className={`btn-action ${isSaved ? "saved" : ""}`} onClick={() => onSave(result)}>
            <Icon name="save" size={13} /> {isSaved ? "Guardado" : "Guardar"}
          </button>
        </div>
      </div>
    </article>
  );
};

// ─── PAGINATION ───────────────────────────────────────────────────────────────
const Pagination = ({ page, total, pageSize, onChange }) => {
  const totalPages = Math.ceil(total / pageSize);
  if (totalPages <= 1) return null;
  const pages = [];
  for (let i = Math.max(1, page - 2); i <= Math.min(totalPages, page + 2); i++) pages.push(i);
  return (
    <nav className="pagination">
      <button disabled={page === 1} onClick={() => onChange(page - 1)}>‹</button>
      {pages[0] > 1 && <><button onClick={() => onChange(1)}>1</button><span>…</span></>}
      {pages.map(p => (
        <button key={p} className={p === page ? "active" : ""} onClick={() => onChange(p)}>{p}</button>
      ))}
      {pages[pages.length - 1] < totalPages && <><span>…</span><button onClick={() => onChange(totalPages)}>{totalPages}</button></>}
      <button disabled={page === totalPages} onClick={() => onChange(page + 1)}>›</button>
    </nav>
  );
};

// ─── REQ-F46: ACTIVE FILTERS DISPLAY ─────────────────────────────────────────
const ActiveFilters = ({ year, yearTo, docType, fields, onRemove }) => {
  const filters = [];
  if (year || yearTo) filters.push({ key: "date", label: `Ano: ${year || "?"} – ${yearTo || "?"}` });
  if (docType) filters.push({ key: "docType", label: `Tipo: ${docType}` });
  if (fields) filters.push({ key: "fields", label: `Campo: ${fields}` });
  if (!filters.length) return null;
  return (
    <div className="active-filters">
      <span className="af-label">Filtros ativos:</span>
      {filters.map(f => (
        <span key={f.key} className="filter-tag">
          {f.label}
          <button className="filter-tag-remove" onClick={() => onRemove(f.key)} aria-label={`Remover filtro ${f.label}`}>×</button>
        </span>
      ))}
      <button className="btn-text" style={{fontSize:".72rem"}} onClick={() => { onRemove("date"); onRemove("docType"); onRemove("fields"); }}>
        Limpar todos
      </button>
    </div>
  );
};

// ─── REQ-F51/F52: COMPARISON VIEW ────────────────────────────────────────────
const ComparisonPanel = ({ query, onAuthorClick }) => {
  const [customResults, setCustomResults] = useState(null);
  const [sklearnResults, setSklearnResults] = useState(null);
  const [stemResults, setStemResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [times, setTimes] = useState({});
  const [activeTab, setActiveTab] = useState("ranking");

  const runComparison = async () => {
    if (!query.trim()) return;
    setLoading(true); setError(null);
    try {
      const newTimes = {};
      let t0 = performance.now();
      const custom = await apiFetch("/search", { q: query, mode: "custom", page: 1, page_size: 5 });
      newTimes.custom = ((performance.now() - t0) / 1000).toFixed(3);
      setCustomResults(custom);

      t0 = performance.now();
      const sklearn = await apiFetch("/search", { q: query, mode: "sklearn", page: 1, page_size: 5 });
      newTimes.sklearn = ((performance.now() - t0) / 1000).toFixed(3);
      setSklearnResults(sklearn);

      t0 = performance.now();
      const stemDebug = await apiFetch("/debug/preprocess", { text: query });
      newTimes.stem = ((performance.now() - t0) / 1000).toFixed(3);
      setStemResults(stemDebug);
      setTimes(newTimes);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  // REQ-F54: Simple bar chart for score comparison
  const ScoreChart = ({ customRes, sklearnRes }) => {
    if (!customRes?.results?.length) return null;
    const allUrls = [...new Set([
      ...(customRes.results || []).map(r => r.url),
      ...(sklearnRes?.results || []).map(r => r.url),
    ])].slice(0, 5);
    const customMap = Object.fromEntries((customRes.results || []).map(r => [r.url, r.score || 0]));
    const sklearnMap = Object.fromEntries((sklearnRes?.results || []).map(r => [r.url, r.score || 0]));
    const maxScore = Math.max(...allUrls.flatMap(u => [customMap[u] || 0, sklearnMap[u] || 0]), 0.001);

    return (
      <div className="score-chart">
        <h5>📊 Comparação de scores (top 5)</h5>
        {allUrls.map((url, i) => {
          const label = url.split("/").pop()?.slice(0, 30) || `doc${i + 1}`;
          return (
            <div key={url} className="chart-row">
              <span className="chart-label" title={url}>{label}</span>
              <div className="chart-bars">
                <div className="chart-bar-wrap">
                  <div className="chart-bar custom-bar" style={{ width: `${((customMap[url] || 0) / maxScore) * 100}%` }} />
                  <span className="chart-bar-val">{(customMap[url] || 0).toFixed(3)}</span>
                </div>
                <div className="chart-bar-wrap">
                  <div className="chart-bar sklearn-bar" style={{ width: `${((sklearnMap[url] || 0) / maxScore) * 100}%` }} />
                  <span className="chart-bar-val">{(sklearnMap[url] || 0).toFixed(3)}</span>
                </div>
              </div>
            </div>
          );
        })}
        <div className="chart-legend">
          <span><span className="legend-dot custom-dot" />TF-IDF Próprio</span>
          <span><span className="legend-dot sklearn-dot" />sklearn</span>
        </div>
      </div>
    );
  };

  return (
    <div className="comparison-panel">
      <div className="comparison-header">
        <h3><Icon name="compare" size={16} /> Comparação de Algoritmos</h3>
        <p>Compara lado a lado os resultados de diferentes métodos para a query: <strong>"{query}"</strong></p>
        <button className="btn-primary" onClick={runComparison} disabled={loading || !query.trim()}>
          {loading ? "A comparar…" : "Comparar agora"}
        </button>
      </div>

      {error && <div className="error-box"><strong>Erro:</strong> {error}</div>}

      {(customResults || stemResults) && (
        <>
          <div className="comp-tabs">
            <button className={`comp-tab ${activeTab === "ranking" ? "active" : ""}`} onClick={() => setActiveTab("ranking")}>
              📊 TF-IDF Custom vs sklearn (REQ-F51)
            </button>
            <button className={`comp-tab ${activeTab === "chart" ? "active" : ""}`} onClick={() => setActiveTab("chart")}>
              📈 Gráfico de scores (REQ-F54)
            </button>
            <button className={`comp-tab ${activeTab === "nlp" ? "active" : ""}`} onClick={() => setActiveTab("nlp")}>
              🔤 Stemming vs Lematização (REQ-F52)
            </button>
          </div>

          {activeTab === "ranking" && customResults && sklearnResults && (
            <div className="comp-columns">
              <div className="comp-col">
                <div className="comp-col-header">
                  <span className="comp-badge custom">TF-IDF Próprio</span>
                  <span className="comp-time">⏱ {times.custom}s · {customResults.total} resultados</span>
                </div>
                {customResults.results?.slice(0, 5).map((r, i) => (
                  <div key={r.url || i} className="comp-result">
                    <span className="comp-rank">{i + 1}</span>
                    <div className="comp-result-body">
                      <p className="comp-title">{r.title || "Sem título"}</p>
                      {r.score != null && <span className="comp-score">score: {r.score.toFixed(4)}</span>}
                    </div>
                  </div>
                ))}
              </div>
              <div className="comp-divider" />
              <div className="comp-col">
                <div className="comp-col-header">
                  <span className="comp-badge sklearn">TF-IDF sklearn</span>
                  <span className="comp-time">⏱ {times.sklearn}s · {sklearnResults.total} resultados</span>
                </div>
                {sklearnResults.results?.slice(0, 5).map((r, i) => (
                  <div key={r.url || i} className="comp-result">
                    <span className="comp-rank">{i + 1}</span>
                    <div className="comp-result-body">
                      <p className="comp-title">{r.title || "Sem título"}</p>
                      {r.score != null && <span className="comp-score">score: {r.score.toFixed(4)}</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* REQ-F54: Score comparison chart */}
          {activeTab === "chart" && customResults && sklearnResults && (
            <ScoreChart customRes={customResults} sklearnRes={sklearnResults} />
          )}

          {activeTab === "nlp" && stemResults && (
            <div className="nlp-comparison">
              <div className="nlp-col">
                <div className="comp-col-header">
                  <span className="comp-badge custom">Stemming (Porter)</span>
                  <span className="comp-time">⏱ {times.stem}s</span>
                </div>
                <p className="nlp-query">Query: <em>"{query}"</em></p>
                <div className="nlp-tokens">
                  {stemResults.tokens?.map((t, i) => (
                    <span key={i} className="nlp-token stem">{t}</span>
                  ))}
                </div>
                <p className="nlp-note">O Porter Stemmer corta sufixos heuristicamente. "studies" → "studi"</p>
              </div>
              <div className="comp-divider" />
              <div className="nlp-col">
                <div className="comp-col-header">
                  <span className="comp-badge sklearn">Lematização (WordNet)</span>
                </div>
                <p className="nlp-query">Query: <em>"{query}"</em></p>
                <div className="nlp-tokens">
                  {stemResults.tokens?.map((t, i) => (
                    <span key={i} className="nlp-token lema">{t}</span>
                  ))}
                </div>
                <p className="nlp-note">O WordNet Lemmatizer usa dicionário. "studies" → "study"</p>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};

// ─── REQ-F53: PERFORMANCE METRICS ────────────────────────────────────────────
const PerformanceMetrics = ({ searchTime, stats }) => {
  if (!searchTime && !stats) return null;
  return (
    <div className="perf-metrics">
      <h4><Icon name="zap" size={13} /> Métricas de Performance </h4>
      <div className="perf-grid">
        {searchTime && (
          <div className="perf-item">
            <span className="perf-val">{searchTime}s</span>
            <span className="perf-label">Tempo de pesquisa</span>
          </div>
        )}
      
      </div>
    </div>
  );
};

// ─── REQ-F55/F56/F57: ANALYTICS DASHBOARD ─────────────────────────────────────
const AnalyticsDashboard = ({ stats }) => {
  const [queryLog, setQueryLog] = useState(() => {
    try { return JSON.parse(localStorage.getItem("pri_query_log") || "[]"); }
    catch { return []; }
  });

  const topQueries = queryLog.reduce((acc, q) => {
    acc[q.q] = (acc[q.q] || 0) + 1; return acc;
  }, {});
  const sortedQueries = Object.entries(topQueries).sort((a, b) => b[1] - a[1]).slice(0, 10);

  const modeCount = queryLog.reduce((acc, q) => {
    acc[q.mode] = (acc[q.mode] || 0) + 1; return acc;
  }, {});

  return (
    <div className="analytics-dashboard">
      <h3></h3>

      {/* REQ-F56: Index size stats */}
      <div className="analytics-section">
        <h4>Dimensão do Índice</h4>
        {stats ? (
          <div className="stat-grid">
            <div className="stat-box">
              <span className="stat-val">{stats.total_documents?.toLocaleString()}</span>
              <span className="stat-label">Documentos indexados</span>
            </div>
            <div className="stat-box">
              <span className="stat-val">{stats.total_terms?.toLocaleString()}</span>
              <span className="stat-label">Termos únicos</span>
            </div>
            <div className="stat-box">
              <span className="stat-val">
                {stats.total_terms && stats.total_documents
                  ? Math.round(stats.total_terms / stats.total_documents)
                  : "—"}
              </span>
              <span className="stat-label">Termos/documento (média)</span>
            </div>
          </div>
        ) : <p className="muted">Estatísticas não disponíveis.</p>}
      </div>

      {/* REQ-F57: Most frequent queries */}
      <div className="analytics-section">
        <h4>Queries mais frequentes</h4>
        {sortedQueries.length === 0
          ? <p className="muted">Nenhuma query registada ainda. Faz uma pesquisa para começar.</p>
          : (
            <div className="top-terms">
              {sortedQueries.map(([q, count]) => {
                const max = sortedQueries[0][1];
                return (
                  <div key={q} className="term-row">
                    <span className="term-name">{q}</span>
                    <div className="term-bar-bg">
                      <div className="term-bar-fill" style={{ width: `${(count / max) * 100}%` }} />
                    </div>
                    <span className="term-df">{count}×</span>
                  </div>
                );
              })}
            </div>
          )
        }
      </div>

      {/* REQ-F57: Mode usage breakdown */}
      <div className="analytics-section">
        <h4>Modo de pesquisa utilizado</h4>
        {Object.keys(modeCount).length === 0
          ? <p className="muted">Sem dados ainda.</p>
          : (
            <div className="mode-breakdown">
              {Object.entries(modeCount).map(([mode, count]) => {
                const total = Object.values(modeCount).reduce((a, b) => a + b, 0);
                const labels = { tfidf: "TF-IDF", boolean: "Booleano", author: "Autor" };
                return (
                  <div key={mode} className="mode-bar-row">
                    <span className="mode-bar-label">{labels[mode] || mode}</span>
                    <div className="term-bar-bg">
                      <div className="term-bar-fill" style={{ width: `${(count / total) * 100}%`, background: "var(--accent)" }} />
                    </div>
                    <span className="term-df">{Math.round((count / total) * 100)}%</span>
                  </div>
                );
              })}
            </div>
          )
        }
      </div>

      {/* REQ-F57: Top terms from index */}
      {stats?.top_20_terms_by_df && (
        <div className="analytics-section">
          <h4>Top 20 termos do índice (por frequência de documento)</h4>
          <div className="top-terms">
            {stats.top_20_terms_by_df.map((t) => {
              const max = stats.top_20_terms_by_df[0].document_frequency;
              return (
                <div key={t.term} className="term-row">
                  <span className="term-name">{t.term}</span>
                  <div className="term-bar-bg">
                    <div className="term-bar-fill" style={{ width: `${(t.document_frequency / max) * 100}%` }} />
                  </div>
                  <span className="term-df">{t.document_frequency}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

// ─── STATS PANEL ──────────────────────────────────────────────────────────────
// ─── STATS PANEL ──────────────────────────────────────────────────────────────
const StatsPanel = ({ stats }) => {
  if (!stats) return <div className="stats-loading">A carregar estatísticas…</div>;
  return (
    <div className="stats-panel">
      <AnalyticsDashboard stats={stats} />
    </div>
  );
};

// ─── IR EDUCATION PANEL ───────────────────────────────────────────────────────
const EducationPanel = () => {
  const [active, setActive] = useState(0);
  const tabs = [
    {
      title: "Índice Invertido",
      content: (
        <div className="edu-content">
          <p>Um <strong>índice invertido</strong> mapeia cada termo aos documentos que o contêm, com as suas frequências e posições.</p>
          <div className="index-demo">
            {[
              { term: "machine", docs: ["doc_1 (tf=3)", "doc_4 (tf=1)", "doc_7 (tf=2)"] },
              { term: "learn", docs: ["doc_1 (tf=2)", "doc_3 (tf=5)", "doc_4 (tf=1)"] },
              { term: "neural", docs: ["doc_2 (tf=4)", "doc_5 (tf=1)"] },
            ].map(({ term, docs }) => (
              <div key={term} className="index-row">
                <span className="index-term">{term}</span>
                <span className="index-arrow">→</span>
                <div className="index-postings">
                  {docs.map(d => <span key={d} className="posting">{d}</span>)}
                </div>
              </div>
            ))}
          </div>
        </div>
      ),
    },
    {
      title: "TF-IDF",
      content: (
        <div className="edu-content">
          <p><strong>TF-IDF</strong> pondera a importância de um termo num documento relativamente a toda a coleção.</p>
          <div className="formula-box">
            <div className="formula">TF-IDF(t,d) = TF(t,d) × IDF(t)</div>
            <div className="formula sub">IDF(t) = log(N / df(t))</div>
          </div>
          <div className="formula-explain">
            <div><span>TF(t,d)</span> — frequência do termo <em>t</em> no documento <em>d</em></div>
            <div><span>N</span> — número total de documentos</div>
            <div><span>df(t)</span> — número de documentos com o termo <em>t</em></div>
          </div>
        </div>
      ),
    },
    {
      title: "Booleano",
      content: (
        <div className="edu-content">
          <p>A pesquisa <strong>booleana</strong> combina termos com operadores lógicos. Precedência: NOT &gt; AND &gt; OR.</p>
          <div className="bool-demo">
            {[
              { expr: "A AND B", desc: "documentos com A e B" },
              { expr: "A OR B", desc: "documentos com A ou B" },
              { expr: "NOT A", desc: "documentos sem A" },
              { expr: '"machine learning"', desc: "frase exata" },
            ].map(({ expr, desc }) => (
              <div key={expr} className="bool-row">
                <code>{expr}</code>
                <span>{desc}</span>
              </div>
            ))}
          </div>
        </div>
      ),
    },
    {
      title: "Stemming vs Lema",
      content: (
        <div className="edu-content">
          <p>Ambas as técnicas reduzem palavras à sua forma base para melhorar o recall.</p>
          <table className="stem-table">
            <thead><tr><th>Original</th><th>Stemming (Porter)</th><th>Lematização (WordNet)</th></tr></thead>
            <tbody>
              {[
                ["running", "run", "run"],
                ["studies", "studi", "study"],
                ["algorithms", "algorithm", "algorithm"],
                ["better", "better", "good"],
                ["universities", "univers", "university"],
              ].map(([w, s, l]) => (
                <tr key={w}><td>{w}</td><td className="stem-val">{s}</td><td className="lem-val">{l}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      ),
    },
  ];
  return (
    <div className="edu-panel">
      <div className="edu-tabs">
        {tabs.map((t, i) => (
          <button key={i} className={`edu-tab ${i === active ? "active" : ""}`} onClick={() => setActive(i)}>
            {t.title}
          </button>
        ))}
      </div>
      <div className="edu-body">{tabs[active].content}</div>
    </div>
  );
};

// ─── BOOLEAN QUERY BUILDER ────────────────────────────────────────────────────
const QueryBuilder = ({ onApply }) => {
  const [terms, setTerms] = useState([{ id: 0, val: "", op: "AND" }]);
  const addTerm = () => setTerms(t => [...t, { id: Date.now(), val: "", op: "AND" }]);
  const remove = (id) => setTerms(t => t.filter(x => x.id !== id));
  const update = (id, field, val) => setTerms(t => t.map(x => x.id === id ? { ...x, [field]: val } : x));
  const build = () => {
    const parts = terms.filter(t => t.val.trim());
    if (!parts.length) return;
    let q = parts[0].val.trim();
    for (let i = 1; i < parts.length; i++) q += ` ${parts[i].op} ${parts[i].val.trim()}`;
    onApply(q);
  };
  const preview = terms.filter(t => t.val.trim()).map((t, i) =>
    i === 0 ? t.val : `${t.op} ${t.val}`
  ).join(" ");

  return (
    <div className="query-builder">
      <h4>Construtor de Query Visual</h4>
      <p className="qb-note">Precedência: <strong>NOT</strong> &gt; <strong>AND</strong> &gt; <strong>OR</strong></p>
      {terms.map((t, i) => (
        <div key={t.id} className="qb-row">
          {i > 0 && (
            <select value={t.op} onChange={e => update(t.id, "op", e.target.value)} className="qb-op">
              <option>AND</option><option>OR</option><option>NOT</option>
            </select>
          )}
          <input
            className="qb-input"
            placeholder={`Termo ${i + 1}…`}
            value={t.val}
            onChange={e => update(t.id, "val", e.target.value)}
          />
          {i > 0 && <button className="qb-remove" onClick={() => remove(t.id)}><Icon name="x" size={12} /></button>}
        </div>
      ))}
      <div className="qb-actions">
        <button className="btn-secondary" onClick={addTerm}>+ Adicionar termo</button>
        <button className="btn-primary" onClick={build}>Aplicar query</button>
      </div>
      {preview && (
        <div className="qb-preview">
          <span className="qb-preview-label">Query gerada:</span> <code>{preview}</code>
        </div>
      )}
    </div>
  );
};

// ─── REQ-F37: AUTHOR COLLABORATION NETWORK ────────────────────────────────────
const AuthorNetwork = ({ publications }) => {
  const canvasRef = useRef(null);

  const buildNetwork = useCallback(() => {
    const coauthor = {};
    (publications || []).forEach(pub => {
      let authors = pub.authors || [];
      if (typeof authors === "string") authors = authors.split(";").map(a => a.trim());
      authors = authors.filter(Boolean).slice(0, 6); // cap per pub to avoid noise
      for (let i = 0; i < authors.length; i++) {
        for (let j = i + 1; j < authors.length; j++) {
          const a = authors[i], b = authors[j];
          coauthor[a] = coauthor[a] || {};
          coauthor[b] = coauthor[b] || {};
          coauthor[a][b] = (coauthor[a][b] || 0) + 1;
          coauthor[b][a] = (coauthor[b][a] || 0) + 1;
        }
      }
    });
    // Keep top 20 authors by degree
    const authors = Object.entries(coauthor)
      .map(([name, conns]) => ({ name, degree: Object.keys(conns).length }))
      .sort((a, b) => b.degree - a.degree)
      .slice(0, 20)
      .map(a => a.name);
    const edges = [];
    authors.forEach(a => {
      Object.entries(coauthor[a] || {}).forEach(([b, w]) => {
        if (authors.includes(b) && a < b) edges.push({ a, b, w });
      });
    });
    return { authors, edges, coauthor };
  }, [publications]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const { authors, edges } = buildNetwork();
    if (!authors.length) return;

    const W = canvas.width, H = canvas.height;
    const cx = W / 2, cy = H / 2;
    const r = Math.min(W, H) * 0.38;

    // Place nodes in a circle
    const nodes = authors.map((name, i) => ({
      name,
      x: cx + r * Math.cos((2 * Math.PI * i) / authors.length - Math.PI / 2),
      y: cy + r * Math.sin((2 * Math.PI * i) / authors.length - Math.PI / 2),
    }));
    const nodeMap = Object.fromEntries(nodes.map(n => [n.name, n]));

    ctx.clearRect(0, 0, W, H);

    // Draw edges
    edges.forEach(({ a, b, w }) => {
      const na = nodeMap[a], nb = nodeMap[b];
      if (!na || !nb) return;
      ctx.beginPath();
      ctx.moveTo(na.x, na.y);
      ctx.lineTo(nb.x, nb.y);
      ctx.strokeStyle = `rgba(99,102,241,${Math.min(0.1 + w * 0.15, 0.6)})`;
      ctx.lineWidth = Math.min(w, 3);
      ctx.stroke();
    });

    // Draw nodes
    nodes.forEach(n => {
      ctx.beginPath();
      ctx.arc(n.x, n.y, 7, 0, 2 * Math.PI);
      ctx.fillStyle = "#6366f1";
      ctx.fill();
      ctx.fillStyle = "#1e1b4b";
      ctx.font = "10px sans-serif";
      ctx.textAlign = "center";
      const shortName = n.name.split(",")[0].split(" ").slice(-1)[0];
      ctx.fillText(shortName, n.x, n.y + 18);
    });
  }, [buildNetwork]);

  const { authors } = buildNetwork();
  if (!authors.length) {
    return <p className="muted">Não há dados de coautoria suficientes para gerar a rede.</p>;
  }

  return (
    <div className="author-network">
      <h4><Icon name="network" size={14} /> Rede de Colaboração entre Autores (REQ-F37)</h4>
      <p className="muted" style={{ fontSize: ".78rem" }}>Top 20 autores por número de colaborações. Linhas mais espessas = mais publicações em comum.</p>
      <canvas ref={canvasRef} width={560} height={420} className="network-canvas" />
    </div>
  );
};

// ─── REQ-F67: HELP PAGE ───────────────────────────────────────────────────────
const HelpPage = () => {
  const [section, setSection] = useState("syntax");
  const sections = {
    syntax: {
      title: "Sintaxe de Pesquisa",
      content: (
        <div className="help-section-content">
          <h4>Pesquisa por texto livre (TF-IDF)</h4>
          <p>Escreve os termos que pretendes pesquisar. O sistema encontra os documentos mais relevantes usando TF-IDF e similaridade do cosseno.</p>
          <div className="help-examples">
            {[
              { ex: "machine learning healthcare", desc: "Documentos sobre ML na saúde" },
              { ex: "neural network classification", desc: "Redes neurais para classificação" },
            ].map(e => <div key={e.ex} className="help-row"><code>{e.ex}</code><span>{e.desc}</span></div>)}
          </div>

          <h4>Pesquisa Booleana</h4>
          <p>Combina termos com operadores lógicos. Precedência: <strong>NOT &gt; AND &gt; OR</strong>.</p>
          <div className="help-examples">
            {[
              { ex: "machine AND learning", desc: "Documentos com ambos os termos" },
              { ex: "health OR cancer", desc: "Documentos com qualquer dos termos" },
              { ex: "learning NOT survey", desc: "Exclui documentos com 'survey'" },
              { ex: "(deep OR neural) AND learning", desc: "Agrupamento com parênteses" },
            ].map(e => <div key={e.ex} className="help-row"><code>{e.ex}</code><span>{e.desc}</span></div>)}
          </div>
        </div>
      ),
    },
    nlp: {
      title: "Processamento de Texto",
      content: (
        <div className="help-section-content">
          <h4>Stemming (Porter Stemmer)</h4>
          <p>Reduz palavras à sua raiz morfológica de forma heurística. Mais rápido mas menos preciso.</p>
          <p><strong>Exemplo:</strong> "running" → "run", "studies" → "studi"</p>

          <h4>Lematização (WordNet)</h4>
          <p>Reduz palavras à sua forma canónica usando um dicionário. Mais lento mas mais preciso.</p>
          <p><strong>Exemplo:</strong> "running" → "run", "studies" → "study", "better" → "good"</p>

          <h4>Stop words</h4>
          <p>Palavras muito comuns (artigos, preposições) que são removidas por defeito por não acrescentarem valor à pesquisa.</p>
          <p><strong>Exemplos PT:</strong> "de", "o", "a", "em", "para"</p>
          <p><strong>Exemplos EN:</strong> "the", "a", "of", "in", "for"</p>
        </div>
      ),
    },
    ranking: {
      title: "Algoritmos de Ranking",
      content: (
        <div className="help-section-content">
          <h4>TF-IDF Próprio</h4>
          <p>Implementação manual do modelo vetorial. Calcula <code>TF × log(N/DF)</code> e usa similaridade do cosseno para ordenar os documentos.</p>

          <h4>TF-IDF sklearn</h4>
          <p>Usa a implementação da biblioteca scikit-learn, com normalização L2 e IDF suavizado. Permite comparar com a implementação própria.</p>

          <h4>Pesquisa Booleana</h4>
          <p>Não usa scores — devolve todos os documentos que satisfazem a expressão lógica, com suporte a skip pointers para eficiência.</p>
        </div>
      ),
    },
    tips: {
      title: "Dicas e Boas Práticas",
      content: (
        <div className="help-section-content">
          <ul className="help-tips">
            <li>Para resultados mais precisos, usa termos em inglês — a maioria das publicações está em inglês.</li>
            <li>O <strong>Query Builder</strong> ajuda a construir queries booleanas complexas sem erros de sintaxe.</li>
            <li>Usa <strong>Comparar algoritmos</strong> para perceber as diferenças entre TF-IDF próprio e sklearn.</li>
            <li>O link para partilhar pesquisa (<Icon name="share" size={12} />) copia um URL com a tua query para a área de transferência.</li>
            <li>As tuas <strong>preferências</strong> (algoritmo, modo NLP) são guardadas automaticamente entre sessões.</li>
            <li>Clica no nome de um autor para ver o seu perfil completo e todas as publicações.</li>
          </ul>
        </div>
      ),
    },
  };

  return (
    <div className="help-page">
      <h2>Ajuda e Documentação</h2>
      <div className="help-layout">
        <nav className="help-nav">
          {Object.entries(sections).map(([key, s]) => (
            <button key={key} className={`help-nav-btn ${section === key ? "active" : ""}`} onClick={() => setSection(key)}>
              {s.title}
            </button>
          ))}
        </nav>
        <div className="help-content">
          <h3>{sections[section].title}</h3>
          {sections[section].content}
        </div>
      </div>
    </div>
  );
};

// ─── REQ-F63/F64: PREFERENCES PANEL ──────────────────────────────────────────
const PreferencesPanel = ({ prefs, update }) => {
  return (
    <div className="prefs-panel">
      <h3><Icon name="settings" size={16} /> Preferências </h3>
      <p className="muted" style={{ fontSize: ".82rem", marginBottom: "16px" }}>
        As preferências são guardadas automaticamente no browser entre sessões.
      </p>

      <div className="config-section">
        <h4>
          <Tooltip text="Algoritmo usado para calcular a relevância dos documentos">
            Algoritmo de ranking padrão <Icon name="info" size={12} />
          </Tooltip>
        </h4>
        <div className="radio-group">
          {[["custom", "TF-IDF próprio"], ["sklearn", "TF-IDF sklearn"]].map(([v, l]) => (
            <label key={v} className={`radio-label ${prefs.rankMode === v ? "active" : ""}`}>
              <input type="radio" value={v} checked={prefs.rankMode === v} onChange={() => update({ rankMode: v })} />{l}
            </label>
          ))}
        </div>
      </div>

      <div className="config-section">
        <h4>
          <Tooltip text="Como as palavras são reduzidas à sua forma base durante a indexação e pesquisa">
            Modo de processamento NLP padrão <Icon name="info" size={12} />
          </Tooltip>
        </h4>
        <div className="radio-group">
          {[["both", "Stemming + Lema"], ["stemming", "Só Stemming"], ["lemmatization", "Só Lematização"], ["none", "Sem redução"]].map(([v, l]) => (
            <label key={v} className={`radio-label ${prefs.reductionMode === v ? "active" : ""}`}>
              <input type="radio" value={v} checked={prefs.reductionMode === v} onChange={() => update({ reductionMode: v })} />{l}
            </label>
          ))}
        </div>
      </div>

      <div className="config-section">
        <h4>
          <Tooltip text="Idioma preferencial para mensagens do sistema">
            Idioma da interface <Icon name="info" size={12} />
          </Tooltip>
        </h4>
        <div className="radio-group">
          {[["pt", "🇵🇹 Português"], ["en", "🇬🇧 English"]].map(([v, l]) => (
            <label key={v} className={`radio-label ${prefs.language === v ? "active" : ""}`}>
              <input type="radio" value={v} checked={prefs.language === v} onChange={() => update({ language: v })} />{l}
            </label>
          ))}
        </div>
      </div>

      <div className="config-section">
        <h4>Resultados por página padrão</h4>
        <div className="radio-group">
          {[10, 20, 50].map(n => (
            <label key={n} className={`radio-label ${prefs.pageSize === n ? "active" : ""}`}>
              <input type="radio" value={n} checked={prefs.pageSize === n} onChange={() => update({ pageSize: n })} />{n}
            </label>
          ))}
        </div>
      </div>

      <div className="config-section">
        <h4>Visualização</h4>
        <label className={`toggle-label ${prefs.compactView ? "active" : ""}`}>
          <input type="checkbox" checked={prefs.compactView} onChange={e => update({ compactView: e.target.checked })} />
          Vista compacta de resultados
        </label>
        <label className={`toggle-label ${!prefs.removeStopwords ? "active" : ""}`} style={{ marginTop: "8px" }}>
          <input type="checkbox" checked={!prefs.removeStopwords} onChange={e => update({ removeStopwords: !e.target.checked })} />
          Incluir stop words por defeito
        </label>
      </div>

      <div className="config-section">
        <h4>Dados locais</h4>
        <button className="btn-secondary" style={{ fontSize: ".8rem" }} onClick={() => {
          if (window.confirm("Apagar histórico e preferências guardadas?")) {
            localStorage.clear();
            window.location.reload();
          }
        }}>
          Limpar dados locais
        </button>
      </div>
    </div>
  );
};

// ─── AUTHOR PAGE ──────────────────────────────────────────────────────────────
const AuthorPage = ({ name, onBack, onAuthorClick, saved, onSave, isSaved, allPublications }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  useEffect(() => {
    setLoading(true);
    apiFetch(`/author/${encodeURIComponent(name)}`)
      .then(setData).catch(e => setError(e.message)).finally(() => setLoading(false));
  }, [name]);
  return (
    <div className="author-page">
      <button className="btn-back" onClick={onBack}>← Voltar</button>
      {loading && <div className="loading-spinner"><div className="spinner" /></div>}
      {error && <div className="error-box">{error}</div>}
      {data && (
        <>
          <div className="author-header">
            <div className="author-avatar">{name.charAt(0).toUpperCase()}</div>
            <div>
              <h2>{data.name}</h2>
              <span>{data.total_publications} publicações</span>
            </div>
          </div>
          {/* REQ-F37: Collaboration network on author page */}
          {allPublications?.length > 0 && (
            <AuthorNetwork publications={allPublications.filter(p => {
              let authors = p.authors || [];
              if (typeof authors === "string") authors = authors.split(";").map(a => a.trim());
              return authors.some(a => a.toLowerCase().includes(name.toLowerCase()));
            })} />
          )}
          <div className="results-list">
            {data.publications.map((r, i) => (
              <ResultCard key={r.url || i} result={r} rank={i + 1}
                isSaved={isSaved(r.url)} onSave={onSave} onAuthorClick={onAuthorClick} />
            ))}
          </div>
        </>
      )}
    </div>
  );
};

// ─── EXPORT UTILS ─────────────────────────────────────────────────────────────
function exportJSON(results) {
  const blob = new Blob([JSON.stringify(results, null, 2)], { type: "application/json" });
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob);
  a.download = "resultados.json"; a.click();
}
function exportCSV(results) {
  const rows = [["Título", "Autores", "Data", "DOI", "Score", "URL"]];
  results.forEach(r => rows.push([r.title || "", (r.authors || []).join("; "), r.date || "", r.doi || "", r.score || "", r.url || ""]));
  const csv = rows.map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv" }); const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = "resultados.csv"; a.click();
}
function exportBibTeX(results) {
  const bib = results.map((r, i) => {
    const key = `pub${i + 1}`; const authors = (r.authors || []).join(" and ");
    return `@article{${key},\n  title={${r.title || ""}},\n  author={${authors}},\n  year={${r.date || ""}},\n  doi={${r.doi || ""}},\n  url={${r.url || ""}}\n}`;
  }).join("\n\n");
  const blob = new Blob([bib], { type: "text/plain" }); const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = "resultados.bib"; a.click();
}

// ─── MAIN APP ─────────────────────────────────────────────────────────────────
export default function App() {
  // REQ-F63/F64: Load user preferences
  const { prefs, update: updatePrefs } = usePreferences();

  // REQ-F81: Initialise state from URL params
  const urlParams = readSearchParams();

  const [page, setPage] = useState("search");
  const [query, setQuery] = useState(urlParams.q);
  const [inputVal, setInputVal] = useState(urlParams.q);
  const [searchMode, setSearchMode] = useState(urlParams.mode);
  const [rankMode, setRankMode] = useState(urlParams.rankMode || prefs.rankMode);
  const [reductionMode, setReductionMode] = useState(prefs.reductionMode);
  const [removeStopwords, setRemoveStopwords] = useState(prefs.removeStopwords);
  const [fields, setFields] = useState("");
  const [expand, setExpand] = useState(false);
  const [year, setYear] = useState(urlParams.year);
  const [yearTo, setYearTo] = useState("");
  const [docType, setDocType] = useState(urlParams.docType);
  const [sortBy, setSortBy] = useState("relevance");
  const [pageNum, setPageNum] = useState(urlParams.page);
  const [pageSize, setPageSize] = useState(prefs.pageSize);
  const [results, setResults] = useState(null);
  const [sortedResults, setSortedResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchTime, setSearchTime] = useState(null);
  const [showBuilder, setShowBuilder] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const [showComparison, setShowComparison] = useState(false);
  const [authorTarget, setAuthorTarget] = useState(null);
  const [stats, setStats] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const debounceRef = useRef(null);
  const { history, add: addHistory, clear: clearHistory } = useSearchHistory();
  const { saved, toggle: toggleSave, isSaved } = useSaved();
  const inputRef = useRef();

  useEffect(() => {
    apiFetch("/stats").then(setStats).catch(() => {});
  }, []);

  // Auto-search if URL had a query on load
  useEffect(() => {
    if (urlParams.q) doSearch(urlParams.q, urlParams.page);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleInputChange = (val) => {
    setInputVal(val);
    setShowSuggestions(false);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (val.trim().length < 2 || searchMode === "boolean") return;
    debounceRef.current = setTimeout(async () => {
      try {
        const data = await apiFetch("/search", { q: val, mode: "custom", page: 1, page_size: 5 });
        const titles = (data.results || []).map(r => r.title).filter(Boolean).slice(0, 5);
        setSuggestions(titles);
        setShowSuggestions(titles.length > 0);
      } catch { setSuggestions([]); }
    }, 350);
  };

  const applySort = useCallback((data, sort) => {
    if (!data?.results) return data;
    const sorted = [...data.results];
    if (sort === "date") sorted.sort((a, b) => (b.date || "").localeCompare(a.date || ""));
    else if (sort === "title") sorted.sort((a, b) => (a.title || "").localeCompare(b.title || ""));
    return { ...data, results: sorted };
  }, []);

  const doSearch = useCallback(async (q, pg = 1) => {
    if (!q.trim()) return;
    setLoading(true); setError(null); setShowSuggestions(false);
    const t0 = performance.now();
    try {
      let data;
      // Build year filter params: use year_from/year_to for range, year for exact match
      const yearParams = {};
      if (year && yearTo) {
        yearParams.year_from = year;
        yearParams.year_to = yearTo;
      } else if (year) {
        yearParams.year_from = year;
      } else if (yearTo) {
        yearParams.year_to = yearTo;
      }
      if (searchMode === "boolean") {
        data = await apiFetch("/search/boolean", { q, ...yearParams, doc_type: docType || undefined, page: pg, page_size: pageSize });
      } else if (searchMode === "author") {
        data = await apiFetch("/search/author", { name: q, page: pg, page_size: pageSize });
      } else {
        data = await apiFetch("/search", { q, mode: rankMode, ...yearParams, doc_type: docType || undefined, page: pg, page_size: pageSize });
      }
      setResults(data);
      setSortedResults(applySort(data, sortBy));
      setSearchTime(((performance.now() - t0) / 1000).toFixed(3));
      addHistory({ q, mode: searchMode, ts: Date.now() });

      // Log to analytics (REQ-F57)
      const log = JSON.parse(localStorage.getItem("pri_query_log") || "[]");
      log.unshift({ q, mode: searchMode, ts: Date.now() });
      localStorage.setItem("pri_query_log", JSON.stringify(log.slice(0, 200)));

      // REQ-F81: Update URL
      writeSearchParams({ q, mode: searchMode, rankMode, year, docType, page: pg });
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, [searchMode, rankMode, year, yearTo, docType, pageSize, sortBy, applySort, addHistory]);

  useEffect(() => {
    if (results) setSortedResults(applySort(results, sortBy));
  }, [sortBy, results, applySort]);

  const handleSubmit = (e) => { e?.preventDefault(); setQuery(inputVal); setPageNum(1); doSearch(inputVal, 1); };
  const handlePageChange = (p) => { setPageNum(p); doSearch(query, p); };
  const handleAuthorClick = (name) => { setAuthorTarget(name); setPage("author"); };
  const displayResults = sortedResults || results;

  const handleRemoveFilter = (key) => {
    if (key === "date") { setYear(""); setYearTo(""); }
    if (key === "docType") setDocType("");
    if (key === "fields") setFields("");
  };

  // REQ-F81: Copy shareable link
  const handleShare = () => {
    writeSearchParams({ q: query, mode: searchMode, rankMode, year, docType, page: pageNum });
    navigator.clipboard.writeText(window.location.href).then(() => {
      alert("Link copiado para a área de transferência!");
    }).catch(() => {});
  };

  const SEARCH_MODES = [
    { id: "tfidf", label: "TF-IDF", desc: "Ranking por relevância" },
    { id: "boolean", label: "Booleano", desc: "AND / OR / NOT" },
    { id: "author", label: "Autor", desc: "Pesquisa por nome" },
  ];

  const navItems = [
    { id: "search", label: "Pesquisa", icon: "search" },
    { id: "stats", label: "Estatísticas", icon: "chart" },
    { id: "edu", label: "Como funciona", icon: "info" },
    { id: "saved", label: `Guardados (${saved.length})`, icon: "save" },
    { id: "help", label: "Ajuda", icon: "help" },
    { id: "prefs", label: "Preferências", icon: "settings" },
  ];

  // REQ-F13: Language label helper
  const lang = prefs.language || "pt";
  const t = (pt, en) => lang === "en" ? en : pt;

  return (
    <div className="app">
      <header className="header">
        <div className="header-inner">
          <div className="brand" onClick={() => setPage("search")}>
            <div className="brand-icon"><Icon name="book" size={20} /></div>
            <div>
              <span className="brand-name">RepositóriUM</span>
              <span className="brand-sub">{t("Motor de Pesquisa Científica · UMinho", "Scientific Search Engine · UMinho")}</span>
            </div>
          </div>
          <nav className="main-nav">
            {navItems.map(n => (
              <button key={n.id} className={`nav-btn ${page === n.id ? "active" : ""}`} onClick={() => setPage(n.id)}>
                <Icon name={n.icon} size={14} />{n.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="main">
        {page === "search" && (
          <div className="search-page">
            <div className="search-hero">
              <h1 className="hero-title">{t("Pesquisa de Publicações", "Publication Search")}</h1>
              <p className="hero-sub">{t("Aceda ao acervo científico da Universidade do Minho", "Access the University of Minho scientific repository")}</p>

              <div className="mode-tabs">
                {SEARCH_MODES.map(m => (
                  <button key={m.id} className={`mode-tab ${searchMode === m.id ? "active" : ""}`}
                    onClick={() => setSearchMode(m.id)}>
                    <span>{m.label}</span><small>{m.desc}</small>
                  </button>
                ))}
              </div>

              <form className="search-form" onSubmit={handleSubmit}>
                <div className="search-input-wrap" style={{ position: "relative", flexWrap: "wrap" }}>
                  <Icon name="search" size={18} />
                  <input ref={inputRef} className="search-input" value={inputVal}
                    onChange={e => handleInputChange(e.target.value)}
                    onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
                    onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
                    placeholder={
                      searchMode === "boolean" ? 'Ex: "machine learning" AND health NOT survey' :
                      searchMode === "author" ? t("Nome do autor…", "Author name…") :
                      t("Pesquise publicações, temas, palavras-chave…", "Search publications, topics, keywords…")
                    } autoFocus />
                  {inputVal && <button type="button" className="clear-btn" onClick={() => { setInputVal(""); setSuggestions([]); }}><Icon name="x" size={14} /></button>}
                  <button type="submit" className="search-btn">{t("Pesquisar", "Search")}</button>
                  {showSuggestions && suggestions.length > 0 && (
                    <div className="suggestions-box">
                      {suggestions.map((s, i) => (
                        <div key={i} className="suggestion-item" onMouseDown={() => { setInputVal(s); setShowSuggestions(false); }}>
                          <Icon name="search" size={12} /> {s}
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* REQ-F10: Real-time query validation */}
                <QueryValidation query={inputVal} mode={searchMode} />

                <div className="search-utils">
                  {searchMode !== "author" && (
                    <button type="button" className="util-btn" onClick={() => setShowBuilder(b => !b)}>
                      <Icon name="filter" size={13} /> {t("Query builder", "Query builder")}
                    </button>
                  )}
                  <button type="button" className="util-btn" onClick={() => setShowHelp(h => !h)}>
                    <Icon name="help" size={13} /> {t("Ajuda de sintaxe", "Syntax help")}
                  </button>
                  {query && searchMode !== "author" && (
                    <button type="button" className="util-btn" onClick={() => setShowComparison(c => !c)}>
                      <Icon name="compare" size={13} /> {t("Comparar algoritmos", "Compare algorithms")}
                    </button>
                  )}
                  {/* REQ-F81: Share button */}
                  {query && (
                    <button type="button" className="util-btn" onClick={handleShare}>
                      <Icon name="share" size={13} /> {t("Partilhar", "Share")}
                    </button>
                  )}
                </div>
              </form>

              {showBuilder && (
                <QueryBuilder onApply={q => { setInputVal(q); setShowBuilder(false); inputRef.current?.focus(); }} />
              )}

              {showHelp && (
                <div className="help-box">
                  <button className="help-close" onClick={() => setShowHelp(false)}><Icon name="x" size={14} /></button>
                  <h4>{t("Sintaxe de pesquisa", "Search syntax")}</h4>
                  <div className="help-grid">
                    {[
                      { ex: "machine AND learning", desc: t("Ambos os termos", "Both terms") },
                      { ex: "health OR cancer", desc: t("Qualquer dos termos", "Either term") },
                      { ex: "NOT survey", desc: t("Excluir termo", "Exclude term") },
                      { ex: '"deep learning"', desc: t("Frase exata", "Exact phrase") },
                      { ex: "(A OR B) AND C", desc: t("Agrupamento com parênteses", "Group with parentheses") },
                    ].map(({ ex, desc }) => (
                      <div key={ex} className="help-row">
                        <code onClick={() => setInputVal(ex)}>{ex}</code>
                        <span>{desc}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {searchMode !== "author" && (
              <div className="config-panel">
                <div className="config-section">
                  <h4>
                    <Tooltip text="Escolhe como calcular a relevância dos resultados">
                      {t("Algoritmo de ranking", "Ranking algorithm")} <Icon name="info" size={12} />
                    </Tooltip>
                  </h4>
                  <div className="radio-group">
                    {[["custom", "TF-IDF próprio"], ["sklearn", "TF-IDF sklearn"]].map(([v, l]) => (
                      <label key={v} className={`radio-label ${rankMode === v ? "active" : ""}`}>
                        <input type="radio" value={v} checked={rankMode === v} onChange={e => setRankMode(e.target.value)} />{l}
                      </label>
                    ))}
                  </div>
                </div>

                <div className="config-section">
                  <h4>
                    <Tooltip text="Como as palavras são normalizadas antes de pesquisar">
                      {t("Processamento de texto", "Text processing")} <Icon name="info" size={12} />
                    </Tooltip>
                  </h4>
                  <div className="radio-group">
                    {[["both", "Stemming + Lema"], ["stemming", "Só Stemming"], ["lemmatization", "Só Lematização"], ["none", "Sem redução"]].map(([v, l]) => (
                      <label key={v} className={`radio-label ${reductionMode === v ? "active" : ""}`}>
                        <input type="radio" value={v} checked={reductionMode === v} onChange={e => setReductionMode(e.target.value)} />{l}
                      </label>
                    ))}
                  </div>
                  <label className={`toggle-label ${!removeStopwords ? "active" : ""}`} style={{ marginTop: "8px" }}>
                    <input type="checkbox" checked={!removeStopwords} onChange={e => setRemoveStopwords(!e.target.checked)} />
                    <Tooltip text="Stop words são palavras comuns como 'de', 'o', 'the' que normalmente não contribuem para a pesquisa">
                      {t("Incluir stop words", "Include stop words")} <Icon name="info" size={11} />
                    </Tooltip>
                  </label>
                </div>

                <div className="config-section">
                  <h4>{t("Campos de pesquisa", "Search fields")}</h4>
                  <div className="radio-group">
                    {[["", t("Todos", "All")], ["title", t("Título", "Title")], ["abstract", t("Resumo", "Abstract")]].map(([v, l]) => (
                      <label key={v} className={`radio-label ${fields === v ? "active" : ""}`}>
                        <input type="radio" value={v} checked={fields === v} onChange={e => setFields(e.target.value)} />{l}
                      </label>
                    ))}
                  </div>
                </div>

                <div className="config-section">
                  <h4>{t("Filtros", "Filters")}</h4>
                  <div className="filter-row">
                    <input type="number" placeholder={t("Ano de", "Year from")} min="1900" max="2030" value={year}
                      onChange={e => setYear(e.target.value)} className="filter-input" style={{ width: "80px" }} />
                    <input type="number" placeholder={t("Ano até", "Year to")} min="1900" max="2030" value={yearTo}
                      onChange={e => setYearTo(e.target.value)} className="filter-input" style={{ width: "80px" }} />
                  </div>
                  <select value={docType} onChange={e => setDocType(e.target.value)} className="filter-select" style={{ marginTop: "6px", width: "100%" }}>
                    <option value="">{t("Todos os tipos", "All types")}</option>
                    <option value="thesis">{t("Tese", "Thesis")}</option>
                    <option value="article">{t("Artigo", "Article")}</option>
                    <option value="dissertation">{t("Dissertação", "Dissertation")}</option>
                  </select>
                  <ActiveFilters year={year} yearTo={yearTo} docType={docType} fields={fields} onRemove={handleRemoveFilter} />
                </div>
              </div>
            )}

            {results && <PerformanceMetrics searchTime={searchTime} stats={stats} />}

            {showComparison && query && (
              <ComparisonPanel query={query} onAuthorClick={handleAuthorClick} />
            )}

            <div className="results-area">
              {!results && !loading && history.length > 0 && (
                <div className="history-panel">
                  <div className="history-header">
                    <span><Icon name="clock" size={14} /> {t("Pesquisas recentes", "Recent searches")}</span>
                    <button className="btn-text" onClick={clearHistory}>{t("Limpar", "Clear")}</button>
                  </div>
                  <div className="history-chips">
                    {history.map((h, i) => (
                      <button key={i} className="history-chip" onClick={() => { setInputVal(h.q); setSearchMode(h.mode); setQuery(h.q); doSearch(h.q, 1); }}>
                        {h.q}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {loading && <div className="loading-spinner"><div className="spinner" /><span>{t("A pesquisar…", "Searching…")}</span></div>}
              {error && <div className="error-box"><strong>Erro:</strong> {error}<p style={{ marginTop: "6px", fontSize: ".8rem" }}>{t("Verifica se o backend está a correr em localhost:8000", "Check if the backend is running on localhost:8000")}</p></div>}

              {results && !loading && (
                <>
                  <div className="results-header">
                    <span className="results-count">
                      {(results.total || results.results?.length || 0).toLocaleString()} {t("resultados", "results")}
                      {searchTime && <span className="search-time"> · {searchTime}s</span>}
                    </span>
                    <div className="results-controls">
                      <select value={sortBy} onChange={e => setSortBy(e.target.value)} className="filter-select">
                        <option value="relevance">{t("Ordenar: Relevância", "Sort: Relevance")}</option>
                        <option value="date">{t("Ordenar: Data", "Sort: Date")}</option>
                        <option value="title">{t("Ordenar: Título", "Sort: Title")}</option>
                      </select>
                      <select value={pageSize} onChange={e => { setPageSize(Number(e.target.value)); setPageNum(1); }} className="filter-select">
                        {[10, 20, 50].map(n => <option key={n} value={n}>{n} {t("por página", "per page")}</option>)}
                      </select>
                      <div className="export-menu">
                        <span>{t("Exportar:", "Export:")}</span>
                        <button className="btn-action" onClick={() => exportJSON(displayResults.results)}>JSON</button>
                        <button className="btn-action" onClick={() => exportCSV(displayResults.results)}>CSV</button>
                        <button className="btn-action" onClick={() => exportBibTeX(displayResults.results)}>BibTeX</button>
                      </div>
                    </div>
                  </div>

                  {displayResults?.results?.length === 0
                    ? <div className="no-results">{t("Nenhum resultado para", "No results for")} <strong>"{query}"</strong></div>
                    : (
                      <>
                        <div className="results-list">
                          {displayResults.results.map((r, i) => (
                            <ResultCard key={r.url || i} result={r}
                              rank={(pageNum - 1) * pageSize + i + 1}
                              compact={prefs.compactView}
                              isSaved={isSaved(r.url)} onSave={toggleSave} onAuthorClick={handleAuthorClick} />
                          ))}
                        </div>
                        <Pagination page={pageNum} total={results.total || 0} pageSize={pageSize} onChange={handlePageChange} />
                      </>
                    )
                  }
                </>
              )}
            </div>
          </div>
        )}

        {page === "author" && authorTarget && (
          <AuthorPage name={authorTarget} onBack={() => setPage("search")}
            onAuthorClick={handleAuthorClick} saved={saved} onSave={toggleSave} isSaved={isSaved}
            allPublications={[]} /* pass from context if available */
          />
        )}

        {page === "stats" && (
          <div className="content-page">
            <h2>{t("Estatísticas do Índice", "Index Statistics")}</h2>
            <StatsPanel stats={stats} />
          </div>
        )}

        {page === "edu" && (
          <div className="content-page">
            <h2>{t("Como funciona o Motor de Pesquisa", "How the Search Engine Works")}</h2>
            <p className="page-intro">{t("Conceitos fundamentais de Recuperação de Informação implementados neste sistema.", "Core Information Retrieval concepts implemented in this system.")}</p>
            <EducationPanel />
          </div>
        )}

        {page === "saved" && (
          <div className="content-page">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <h2>{t("Publicações Guardadas", "Saved Publications")}</h2>
              {saved.length > 0 && (
                <div className="export-menu">
                  <span>{t("Exportar:", "Export:")}</span>
                  <button className="btn-action" onClick={() => exportJSON(saved)}>JSON</button>
                  <button className="btn-action" onClick={() => exportCSV(saved)}>CSV</button>
                  <button className="btn-action" onClick={() => exportBibTeX(saved)}>BibTeX</button>
                </div>
              )}
            </div>
            {saved.length === 0
              ? <div className="no-results">{t("Ainda não guardou nenhuma publicação.", "No publications saved yet.")}</div>
              : <div className="results-list">{saved.map((r, i) => <ResultCard key={r.url || i} result={r} rank={i + 1} isSaved={true} onSave={toggleSave} onAuthorClick={handleAuthorClick} />)}</div>
            }
          </div>
        )}

        {/* REQ-F67: Help page */}
        {page === "help" && <div className="content-page"><HelpPage /></div>}

        {/* REQ-F63/F64: Preferences page */}
        {page === "prefs" && (
          <div className="content-page">
            <PreferencesPanel prefs={prefs} update={updatePrefs} />
          </div>
        )}
      </main>

      <footer className="footer">
        <span>Universidade do Minho · Pesquisa e Recuperação de Informação · 2025/2026</span>
        {stats && <span>{t("Índice:", "Index:")} {stats.total_documents} docs · {stats.total_terms} {t("termos", "terms")}</span>}
      </footer>
    </div>
  );
}