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
  };
  return icons[name] || null;
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

// ─── SNIPPET with highlights ─────────────────────────────────────────────────
const Snippet = ({ html }) => {
  if (!html) return null;
  return <p className="snippet" dangerouslySetInnerHTML={{ __html: html }} />;
};

// ─── RESULT CARD ──────────────────────────────────────────────────────────────
const ResultCard = ({ result, rank, isSaved, onSave, onAuthorClick }) => {
  const [expanded, setExpanded] = useState(false);
  return (
    <article className="result-card" style={{ animationDelay: `${rank * 40}ms` }}>
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
              <button key={i} className="author-chip" onClick={() => onAuthorClick(a)}>
                {a}
              </button>
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

// ─── STATS PANEL ──────────────────────────────────────────────────────────────
const StatsPanel = ({ stats }) => {
  if (!stats) return <div className="stats-loading">A carregar estatísticas…</div>;
  return (
    <div className="stats-panel">
      <div className="stat-grid">
        <div className="stat-box">
          <span className="stat-val">{stats.total_documents?.toLocaleString()}</span>
          <span className="stat-label">Documentos</span>
        </div>
        <div className="stat-box">
          <span className="stat-val">{stats.total_terms?.toLocaleString()}</span>
          <span className="stat-label">Termos indexados</span>
        </div>
      </div>
      {stats.top_20_terms_by_df && (
        <div className="top-terms">
          <h4>Top 20 termos (por frequência de documento)</h4>
          <div className="term-bars">
            {stats.top_20_terms_by_df.map((t, i) => {
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
              { expr: "deep NEAR/3 learning", desc: "termos a ≤3 posições" },
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
  return (
    <div className="query-builder">
      <h4>Construtor de Query Visual</h4>
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
      <div className="qb-preview">
        {terms.filter(t => t.val.trim()).map((t, i) => (
          <span key={t.id}>
            {i > 0 && <strong> {t.op} </strong>}
            <em>{t.val}</em>
          </span>
        ))}
      </div>
    </div>
  );
};

// ─── AUTHOR PAGE ──────────────────────────────────────────────────────────────
const AuthorPage = ({ name, onBack, onAuthorClick, saved, onSave, isSaved }) => {
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
  // ── State ──
  const [page, setPage] = useState("search");
  const [query, setQuery] = useState("");
  const [inputVal, setInputVal] = useState("");
  const [searchMode, setSearchMode] = useState("tfidf");
  const [rankMode, setRankMode] = useState("custom");
  const [reductionMode, setReductionMode] = useState("both"); // both | stemming | lemmatization | none
  const [removeStopwords, setRemoveStopwords] = useState(true);
  const [fields, setFields] = useState("");
  const [expand, setExpand] = useState(false);
  const [year, setYear] = useState("");
  const [yearTo, setYearTo] = useState("");
  const [docType, setDocType] = useState("");
  const [sortBy, setSortBy] = useState("relevance"); // relevance | date | title
  const [pageNum, setPageNum] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [results, setResults] = useState(null);
  const [sortedResults, setSortedResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchTime, setSearchTime] = useState(null);
  const [showBuilder, setShowBuilder] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const [authorTarget, setAuthorTarget] = useState(null);
  const [stats, setStats] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const debounceRef = useRef(null);
  const { history, add: addHistory, clear: clearHistory } = useSearchHistory();
  const { saved, toggle: toggleSave, isSaved } = useSaved();
  const inputRef = useRef();

  // ── Load stats ──
  useEffect(() => {
    apiFetch("/stats").then(setStats).catch(() => {});
  }, []);

  // ── Autocomplete ──
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

  // ── Sort results client-side ──
  const applySort = useCallback((data, sort) => {
    if (!data?.results) return data;
    const sorted = [...data.results];
    if (sort === "date") sorted.sort((a, b) => (b.date || "").localeCompare(a.date || ""));
    else if (sort === "title") sorted.sort((a, b) => (a.title || "").localeCompare(b.title || ""));
    return { ...data, results: sorted };
  }, []);

  // ── Search ──
  const doSearch = useCallback(async (q, pg = 1) => {
    if (!q.trim()) return;
    setLoading(true); setError(null); setShowSuggestions(false);
    const t0 = performance.now();
    try {
      let data;
      if (searchMode === "boolean") {
        data = await apiFetch("/search/boolean", { q, fields: fields || undefined, expand, year: year || undefined, doc_type: docType || undefined, page: pg, page_size: pageSize });
      } else if (searchMode === "author") {
        data = await apiFetch("/search/author", { name: q, page: pg, page_size: pageSize });
      } else {
        data = await apiFetch("/search", { q, mode: rankMode, fields: fields || undefined, expand, year: year || undefined, doc_type: docType || undefined, page: pg, page_size: pageSize });
      }
      setResults(data);
      setSortedResults(applySort(data, sortBy));
      setSearchTime(((performance.now() - t0) / 1000).toFixed(3));
      addHistory({ q, mode: searchMode, ts: Date.now() });
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, [searchMode, rankMode, fields, expand, year, docType, pageSize, sortBy, applySort, addHistory]);

  // Re-sort when sortBy changes
  useEffect(() => {
    if (results) setSortedResults(applySort(results, sortBy));
  }, [sortBy, results, applySort]);

  const handleSubmit = (e) => { e?.preventDefault(); setQuery(inputVal); setPageNum(1); doSearch(inputVal, 1); };
  const handlePageChange = (p) => { setPageNum(p); doSearch(query, p); };
  const handleAuthorClick = (name) => { setAuthorTarget(name); setPage("author"); };
  const displayResults = sortedResults || results;

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
  ];

  return (
    <div className="app">
      {/* ── HEADER ── */}
      <header className="header">
        <div className="header-inner">
          <div className="brand" onClick={() => setPage("search")}>
            <div className="brand-icon">
              <Icon name="book" size={20} />
            </div>
            <div>
              <span className="brand-name">RepositóriUM</span>
              <span className="brand-sub">Motor de Pesquisa Científica · UMinho</span>
            </div>
          </div>
          <nav className="main-nav">
            {navItems.map(n => (
              <button key={n.id} className={`nav-btn ${page === n.id ? "active" : ""}`} onClick={() => setPage(n.id)}>
                <Icon name={n.icon} size={14} />
                {n.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="main">
        {/* ══ SEARCH PAGE ══ */}
        {page === "search" && (
          <div className="search-page">
            {/* Search hero */}
            <div className="search-hero">
              <h1 className="hero-title">Pesquisa de Publicações</h1>
              <p className="hero-sub">Aceda ao acervo científico da Universidade do Minho</p>

              {/* Mode selector */}
              <div className="mode-tabs">
                {SEARCH_MODES.map(m => (
                  <button key={m.id} className={`mode-tab ${searchMode === m.id ? "active" : ""}`}
                    onClick={() => setSearchMode(m.id)}>
                    <span>{m.label}</span>
                    <small>{m.desc}</small>
                  </button>
                ))}
              </div>

              {/* Search bar */}
              <form className="search-form" onSubmit={handleSubmit}>
                <div className="search-input-wrap" style={{position:"relative",flexWrap:"wrap"}}>
                  <Icon name="search" size={18} />
                  <input ref={inputRef} className="search-input" value={inputVal}
                    onChange={e => handleInputChange(e.target.value)}
                    onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
                    onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
                    placeholder={
                      searchMode === "boolean" ? 'Ex: "machine learning" AND health NOT survey' :
                      searchMode === "author" ? "Nome do autor…" :
                      "Pesquise publicações, temas, palavras-chave…"
                    } autoFocus />
                  {inputVal && <button type="button" className="clear-btn" onClick={() => { setInputVal(""); setSuggestions([]); }}><Icon name="x" size={14} /></button>}
                  <button type="submit" className="search-btn">Pesquisar</button>
                  {showSuggestions && suggestions.length > 0 && (
                    <div className="suggestions-box">
                      {suggestions.map((s, i) => (
                        <div key={i} className="suggestion-item" onMouseDown={() => { setInputVal(s); setShowSuggestions(false); handleInputChange(s); }}>
                          <Icon name="search" size={12} /> {s}
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="search-utils">
                  {searchMode !== "author" && (
                    <button type="button" className="util-btn" onClick={() => setShowBuilder(b => !b)}>
                      <Icon name="filter" size={13} /> Query builder
                    </button>
                  )}
                  <button type="button" className="util-btn" onClick={() => setShowHelp(h => !h)}>
                    <Icon name="help" size={13} /> Ajuda de sintaxe
                  </button>
                </div>
              </form>

              {/* Query builder */}
              {showBuilder && (
                <QueryBuilder onApply={q => { setInputVal(q); setShowBuilder(false); inputRef.current?.focus(); }} />
              )}

              {/* Help tooltip */}
              {showHelp && (
                <div className="help-box">
                  <button className="help-close" onClick={() => setShowHelp(false)}><Icon name="x" size={14} /></button>
                  <h4>Sintaxe de pesquisa</h4>
                  <div className="help-grid">
                    {[
                      { ex: 'machine AND learning', desc: 'Ambos os termos' },
                      { ex: 'health OR cancer', desc: 'Qualquer dos termos' },
                      { ex: 'NOT survey', desc: 'Excluir termo' },
                      { ex: '"deep learning"', desc: 'Frase exata' },
                      { ex: 'deep NEAR/3 learning', desc: 'Proximidade (≤3 posições)' },
                      { ex: '(A OR B) AND C', desc: 'Agrupamento com parênteses' },
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

            {/* ── CONFIG PANEL ── */}
            {searchMode !== "author" && (
              <div className="config-panel">
                <div className="config-section">
                  <h4>Algoritmo de ranking</h4>
                  <div className="radio-group">
                    {[["custom", "TF-IDF próprio"], ["sklearn", "TF-IDF sklearn"]].map(([v, l]) => (
                      <label key={v} className={`radio-label ${rankMode === v ? "active" : ""}`}>
                        <input type="radio" value={v} checked={rankMode === v} onChange={e => setRankMode(e.target.value)} />
                        {l}
                      </label>
                    ))}
                  </div>
                </div>

                <div className="config-section">
                  <h4>Processamento de texto</h4>
                  <div className="radio-group">
                    {[["both", "Stemming + Lema"], ["stemming", "Só Stemming"], ["lemmatization", "Só Lematização"], ["none", "Sem redução"]].map(([v, l]) => (
                      <label key={v} className={`radio-label ${reductionMode === v ? "active" : ""}`}>
                        <input type="radio" value={v} checked={reductionMode === v} onChange={e => setReductionMode(e.target.value)} />
                        {l}
                      </label>
                    ))}
                  </div>
                  <label className={`toggle-label ${!removeStopwords ? "active" : ""}`} style={{marginTop:"8px"}}>
                    <input type="checkbox" checked={!removeStopwords} onChange={e => setRemoveStopwords(!e.target.checked)} />
                    Incluir stop words
                  </label>
                </div>

                <div className="config-section">
                  <h4>Campos de pesquisa</h4>
                  <div className="radio-group">
                    {[["", "Todos"], ["title", "Título"], ["abstract", "Resumo"]].map(([v, l]) => (
                      <label key={v} className={`radio-label ${fields === v ? "active" : ""}`}>
                        <input type="radio" value={v} checked={fields === v} onChange={e => setFields(e.target.value)} />
                        {l}
                      </label>
                    ))}
                  </div>
                </div>

                <div className="config-section">
                  <h4>Opções avançadas</h4>
                  <label className={`toggle-label ${expand ? "active" : ""}`}>
                    <input type="checkbox" checked={expand} onChange={e => setExpand(e.target.checked)} />
                    Expansão de query (WordNet)
                  </label>
                </div>

                <div className="config-section">
                  <h4>Filtros</h4>
                  <div className="filter-row">
                    <input type="number" placeholder="Ano de" min="1900" max="2030" value={year}
                      onChange={e => setYear(e.target.value)} className="filter-input" style={{width:"80px"}} />
                    <input type="number" placeholder="Ano até" min="1900" max="2030" value={yearTo}
                      onChange={e => setYearTo(e.target.value)} className="filter-input" style={{width:"80px"}} />
                  </div>
                  <select value={docType} onChange={e => setDocType(e.target.value)} className="filter-select" style={{marginTop:"6px",width:"100%"}}>
                    <option value="">Todos os tipos</option>
                    <option value="thesis">Tese</option>
                    <option value="article">Artigo</option>
                    <option value="dissertation">Dissertação</option>
                  </select>
                </div>
              </div>
            )}

            {/* ── RESULTS ── */}
            <div className="results-area">
              {/* History */}
              {!results && !loading && history.length > 0 && (
                <div className="history-panel">
                  <div className="history-header">
                    <span><Icon name="clock" size={14} /> Pesquisas recentes</span>
                    <button className="btn-text" onClick={clearHistory}>Limpar</button>
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

              {loading && (
                <div className="loading-spinner">
                  <div className="spinner" />
                  <span>A pesquisar…</span>
                </div>
              )}

              {error && <div className="error-box"><strong>Erro:</strong> {error}</div>}

              {results && !loading && (
                <>
                  <div className="results-header">
                    <span className="results-count">
                      {(results.total || results.results?.length || 0).toLocaleString()} resultados
                      {searchTime && <span className="search-time"> · {searchTime}s</span>}
                    </span>
                    <div className="results-controls">
                      <select value={sortBy} onChange={e => setSortBy(e.target.value)} className="filter-select">
                        <option value="relevance">Ordenar: Relevância</option>
                        <option value="date">Ordenar: Data</option>
                        <option value="title">Ordenar: Título</option>
                      </select>
                      <select value={pageSize} onChange={e => { setPageSize(Number(e.target.value)); setPageNum(1); }} className="filter-select">
                        {[10, 20, 50].map(n => <option key={n} value={n}>{n} por página</option>)}
                      </select>
                      <div className="export-menu">
                        <span>Exportar:</span>
                        <button className="btn-action" onClick={() => exportJSON(displayResults.results)}>JSON</button>
                        <button className="btn-action" onClick={() => exportCSV(displayResults.results)}>CSV</button>
                        <button className="btn-action" onClick={() => exportBibTeX(displayResults.results)}>BibTeX</button>
                      </div>
                    </div>
                  </div>

                  {displayResults?.results?.length === 0
                    ? <div className="no-results">Nenhum resultado encontrado para <strong>"{query}"</strong></div>
                    : (
                      <>
                        <div className="results-list">
                          {displayResults.results.map((r, i) => (
                            <ResultCard
                              key={r.url || i}
                              result={r}
                              rank={(pageNum - 1) * pageSize + i + 1}
                              isSaved={isSaved(r.url)}
                              onSave={toggleSave}
                              onAuthorClick={handleAuthorClick}
                            />
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

        {/* ══ AUTHOR PAGE ══ */}
        {page === "author" && authorTarget && (
          <AuthorPage name={authorTarget} onBack={() => setPage("search")}
            onAuthorClick={handleAuthorClick} saved={saved} onSave={toggleSave} isSaved={isSaved} />
        )}

        {/* ══ STATS PAGE ══ */}
        {page === "stats" && (
          <div className="content-page">
            <h2>Estatísticas do Índice</h2>
            <StatsPanel stats={stats} />
          </div>
        )}

        {/* ══ EDUCATION PAGE ══ */}
        {page === "edu" && (
          <div className="content-page">
            <h2>Como funciona o Motor de Pesquisa</h2>
            <p className="page-intro">Conceitos fundamentais de Recuperação de Informação implementados neste sistema.</p>
            <EducationPanel />
          </div>
        )}

        {/* ══ SAVED PAGE ══ */}
        {page === "saved" && (
          <div className="content-page">
            <h2>Publicações Guardadas</h2>
            {saved.length === 0
              ? <div className="no-results">Ainda não guardou nenhuma publicação.</div>
              : (
                <div className="results-list">
                  {saved.map((r, i) => (
                    <ResultCard key={r.url || i} result={r} rank={i + 1}
                      isSaved={true} onSave={toggleSave} onAuthorClick={handleAuthorClick} />
                  ))}
                </div>
              )
            }
          </div>
        )}
      </main>

      <footer className="footer">
        <span>Universidade do Minho · Pesquisa e Recuperação de Informação · 2025/2026</span>
        {stats && <span>Índice: {stats.total_documents} docs · {stats.total_terms} termos</span>}
      </footer>
    </div>
  );
}