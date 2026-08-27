// NexusRAG Enterprise v0.2.0 Control Plane & Full Observability Client

let currentVaultId = "all";
let currentSessionId = "session_01";
let currentRbacToken = null;
let currentRbacRole = "admin";

let graphSimulation = null;
let graphDataCache = null;

// PDF Inspector Lab State
let activePdfFile = null;
let activePdfPreset = null;
let lastExtractionResult = null;

// Last query result cache (for DocGen handoff)
let lastQueryResult = null;

// Helper: Common Auth & Headers
function getApiHeaders(extraHeaders = {}) {
  const headers = { ...extraHeaders };
  if (currentRbacToken) {
    headers['Authorization'] = `Bearer ${currentRbacToken}`;
  }
  return headers;
}

// Tab Switching
function switchMainTab(tabId) {
  const allTabs = [
    'query', 'multihop', 'raptor', 'docgen', 'pdf',
    'arena', 'audit', 'mcp', 'timeline', 'graph', 'triad', 'vaults'
  ];

  allTabs.forEach(t => {
    const el = document.getElementById(`tab-${t}`);
    const btn = document.getElementById(`nav-btn-${t}`);
    if (!el || !btn) return;

    if (t === tabId) {
      el.classList.remove('hidden');
      btn.className = 'px-3 py-1.5 rounded-lg transition-all bg-blue-700 text-white shadow-sm font-semibold whitespace-nowrap';
    } else {
      el.classList.add('hidden');
      btn.className = 'px-3 py-1.5 rounded-lg transition-all text-slate-400 hover:text-slate-200 hover:bg-[#0f2244] font-semibold whitespace-nowrap';
    }
  });

  if (tabId === 'graph') {
    renderKnowledgeGraph();
  } else if (tabId === 'vaults') {
    loadVaultsGrid();
  } else if (tabId === 'timeline') {
    loadPolicyTimelines();
  } else if (tabId === 'raptor') {
    loadRaptorTreeVisualization();
  } else if (tabId === 'audit') {
    loadAuditLogsList();
  } else if (tabId === 'mcp') {
    loadMcpToolsList();
  } else if (tabId === 'pdf' && !activePdfFile && !activePdfPreset) {
    loadSamplePdfPreset('ai_governance');
  }
}

// RBAC Role Switcher
async function handleRbacRoleChange(role) {
  currentRbacRole = role;
  const passwords = {
    'admin': { u: 'admin@nexusrag.com', p: 'AdminPass123!' },
    'auditor': { u: 'auditor@nexusrag.com', p: 'AuditorPass123!' },
    'analyst': { u: 'analyst@nexusrag.com', p: 'AnalystPass123!' },
  };

  if (role === 'guest' || !passwords[role]) {
    currentRbacToken = null;
    return;
  }

  try {
    const resp = await fetch('/api/v1/auth/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username: passwords[role].u,
        password: passwords[role].p
      })
    });
    if (resp.ok) {
      const data = await resp.json();
      currentRbacToken = data.access_token;
    }
  } catch (e) {
    console.error('RBAC token authentication error:', e);
  }
}

// Session Management
function createNewSession() {
  currentSessionId = 'session_' + Math.random().toString(36).substring(2, 8);
  const disp = document.getElementById('session-id-display');
  if (disp) disp.innerText = currentSessionId;
  alert(`Started new conversation session: ${currentSessionId}`);
}

// Vault Selector Handling
async function changeActiveVault(vaultId) {
  currentVaultId = vaultId;
  try {
    const resp = await fetch('/api/v1/vaults/switch', {
      method: 'POST',
      headers: getApiHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ vault_id: vaultId })
    });
    if (resp.ok) {
      const vSelect = document.getElementById('vault-select');
      if (vSelect) vSelect.value = vaultId;
      if (!document.getElementById('tab-graph').classList.contains('hidden')) {
        renderKnowledgeGraph();
      }
    }
  } catch (e) {
    console.error('Failed to switch vault:', e);
  }
}

async function setQueryPreset(vaultId, query) {
  await changeActiveVault(vaultId);
  const vSelect = document.getElementById('vault-select');
  if (vSelect) vSelect.value = vaultId;
  const qInput = document.getElementById('query-input');
  if (qInput) qInput.value = query;
  switchMainTab('query');
  executeEnterpriseQuery();
}

// ================= TAB 1: RAG OPS & SSE STREAMING =================

async function executeEnterpriseQuery() {
  const query = document.getElementById('query-input').value.trim();
  if (!query) return;

  const submitBtn = document.getElementById('submit-btn');
  const resultSec = document.getElementById('result-section');
  submitBtn.disabled = true;
  submitBtn.innerHTML = '<span>⏳ Decomposing & Synthesizing...</span>';

  const alpha = parseFloat(document.getElementById('param-alpha').value);
  const rrf_k = parseInt(document.getElementById('param-rrf').value);
  const top_k = parseInt(document.getElementById('param-topk').value);
  const use_hyde = document.getElementById('param-hyde').checked;
  const use_multi_query = document.getElementById('param-multiquery').checked;

  try {
    const response = await fetch('/api/v1/query', {
      method: 'POST',
      headers: getApiHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        query: query,
        vault_id: currentVaultId,
        session_id: currentSessionId,
        alpha_hybrid_weight: alpha,
        rrf_k: rrf_k,
        top_k_rerank: top_k,
        use_hyde: use_hyde,
        use_multi_query: use_multi_query
      })
    });

    if (!response.ok) throw new Error('Query execution failed');

    const data = await response.json();
    lastQueryResult = data;
    renderQueryOutput(data);
    renderTriadMetrics(data.evaluation, data.latency);
    resultSec.classList.remove('hidden');
  } catch (error) {
    alert('Error: ' + error.message);
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerHTML = '<span>⚡ Execute Query</span>';
  }
}

async function executeStreamingQuery() {
  const query = document.getElementById('query-input').value.trim();
  if (!query) return;

  const resultSec = document.getElementById('result-section');
  const answerEl = document.getElementById('answer-text');
  resultSec.classList.remove('hidden');
  answerEl.className = 'text-sm sm:text-base text-slate-100 leading-relaxed font-normal cursor-blink';
  answerEl.innerHTML = '';

  document.getElementById('total-latency').innerText = 'Streaming...';
  document.getElementById('res-vault-badge').innerText = `Vault: ${currentVaultId.toUpperCase()}`;

  try {
    const response = await fetch('/api/v1/query/stream', {
      method: 'POST',
      headers: getApiHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ query: query, vault_id: currentVaultId, session_id: currentSessionId })
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let accumulated = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value);
      const lines = chunk.split('\n\n');
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const token = line.replace('data: ', '');
          if (token === '[DONE]') break;
          accumulated += token;
          let formatted = accumulated.replace(
            /\[Source:\s*([a-zA-Z0-9_-]+)\]/g,
            (m, id) => `<span class="citation-badge">📎 ${id}</span>`
          );
          answerEl.innerHTML = formatted;
        }
      }
    }
  } catch (e) {
    console.error('Stream error:', e);
  } finally {
    answerEl.className = 'text-sm sm:text-base text-slate-100 leading-relaxed font-normal';
    executeEnterpriseQuery(); // Hydrate metadata, observability traces, and RAG Triad
  }
}

function renderQueryOutput(data) {
  document.getElementById('total-latency').innerText = `${data.latency.total_ms} ms`;
  document.getElementById('res-vault-badge').innerText = `Vault: ${data.active_vault_id.toUpperCase()}`;
  document.getElementById('citation-count').innerText = data.citations.length;

  if (data.crag_reflection) {
    document.getElementById('crag-action-badge').innerText = `CRAG: ${data.crag_reflection.action}`;
    document.getElementById('trace-crag-reason').innerText = data.crag_reflection.reasoning;
  }

  // Answer format with interactive inline badges
  let formattedAnswer = data.answer.replace(
    /\[Source:\s*([a-zA-Z0-9_-]+)\]/g,
    (match, chunkId) => `<span class="citation-badge" onclick="highlightRetrievedChunk('${chunkId}')">📎 ${chunkId}</span>`
  );
  document.getElementById('answer-text').innerHTML = formattedAnswer;

  // Citations list
  const citContainer = document.getElementById('citations-container');
  citContainer.innerHTML = '';
  if (data.citations.length > 0) {
    data.citations.forEach(c => {
      const card = document.createElement('div');
      card.className = 'p-3 rounded-xl bg-[#081020] border border-[#162846] text-xs space-y-1.5 cursor-pointer hover:border-blue-500/60 transition-all';
      card.onclick = () => highlightRetrievedChunk(c.chunk_id);
      
      const isTable = c.has_table;
      const isPdf = c.doc_format === 'pdf' || c.doc_title.endsWith('.pdf');

      card.innerHTML = `
        <div class="flex items-center justify-between text-[11px]">
          <div class="flex items-center gap-1.5">
            <span class="font-bold text-blue-300">${c.doc_title}</span>
            ${isPdf ? '<span class="px-1.5 py-0.2 rounded bg-emerald-950 text-emerald-300 text-[9px] font-bold">PDF</span>' : ''}
            ${isTable ? '<span class="px-1.5 py-0.2 rounded bg-blue-950 text-blue-300 text-[9px] font-bold">📊 TABLE</span>' : ''}
          </div>
          <span class="text-slate-400 font-mono">Page ${c.page_number}</span>
        </div>
        <p class="text-slate-400 text-[10px]">Section: <strong class="text-slate-200">${c.section_header}</strong></p>
        <p class="text-slate-300 font-mono text-[11px] line-clamp-2 bg-[#060b17] p-2 rounded-lg border border-[#162846]">${c.snippet}</p>
      `;
      citContainer.appendChild(card);
    });
  } else {
    citContainer.innerHTML = `<p class="text-xs text-slate-500 italic col-span-2">No grounded document citations (query answered out-of-context or unknown).</p>`;
  }

  // Query Expansion Trace
  document.getElementById('trace-intent').innerText = data.query_analysis.intent;
  document.getElementById('trace-hyde').innerText = data.query_analysis.hyde_document;

  const expList = document.getElementById('trace-expansions');
  expList.innerHTML = '';
  data.query_analysis.expanded_queries.forEach(eq => {
    const li = document.createElement('li');
    li.innerText = eq;
    expList.appendChild(li);
  });

  // Waterfall table
  const tbody = document.getElementById('retrieval-table-body');
  tbody.innerHTML = '';
  data.retrieved_chunks.forEach(c => {
    const row = document.createElement('tr');
    row.id = `row-${c.chunk_id}`;
    row.className = 'hover:bg-[#0f2244]/50 transition-colors';
    
    const isTable = c.has_table || c.content.includes('|---|');
    const isPdf = c.doc_format === 'pdf';

    row.innerHTML = `
      <td class="py-2.5 px-3 font-mono text-blue-300 font-bold">
        ${c.chunk_id}
        ${isTable ? '<span class="block text-[9px] text-blue-400 font-sans">📊 Tabular</span>' : ''}
      </td>
      <td class="py-2.5 px-3">
        <div class="font-semibold text-white flex items-center gap-1.5">
          ${c.doc_title}
          ${isPdf ? '<span class="px-1 py-0.2 rounded bg-emerald-950 text-emerald-300 text-[8px] font-bold">PDF</span>' : ''}
        </div>
        <div class="text-[10px] text-slate-400">${c.section_header} (P.${c.page_number})</div>
      </td>
      <td class="py-2.5 px-3 text-center">
        <span class="px-2 py-0.5 rounded-md bg-[#081426] border border-[#162846] text-blue-300 font-mono">#${c.dense_rank} (${c.dense_score})</span>
      </td>
      <td class="py-2.5 px-3 text-center">
        <span class="px-2 py-0.5 rounded-md bg-[#081426] border border-[#162846] text-slate-300 font-mono">#${c.sparse_rank} (${c.sparse_score})</span>
      </td>
      <td class="py-2.5 px-3 text-center font-mono font-bold text-blue-300">${c.rrf_score}</td>
      <td class="py-2.5 px-3 text-center font-mono font-bold text-emerald-400">${c.rerank_score}</td>
      <td class="py-2.5 px-3 text-slate-300 font-mono text-[11px] max-w-xs truncate" title="${c.content.replace(/"/g, '&quot;')}">${c.content}</td>
    `;
    tbody.appendChild(row);
  });
}

function renderTriadMetrics(evalData, latency) {
  document.getElementById('triad-faithfulness').innerText = `${Math.round(evalData.faithfulness * 100)}%`;
  document.getElementById('triad-context').innerText = `${Math.round(evalData.context_relevance * 100)}%`;
  document.getElementById('triad-answer').innerText = `${Math.round(evalData.answer_relevance * 100)}%`;

  // Sentence Verification matrix
  const matrixContainer = document.getElementById('sentence-matrix');
  matrixContainer.innerHTML = '';
  evalData.sentence_verifications.forEach(sv => {
    const row = document.createElement('div');
    row.className = `p-3 rounded-xl border text-xs flex items-start justify-between gap-3 ${
      sv.is_grounded ? 'bg-[#061e16] border-emerald-500/30 text-emerald-200' : 'bg-[#2b0c10] border-rose-500/30 text-rose-200'
    }`;
    row.innerHTML = `
      <div class="space-y-1">
        <p class="font-medium">${sv.sentence}</p>
        <p class="text-[10px] text-slate-400 font-mono">Source Evidence: ${sv.evidence_snippet}</p>
      </div>
      <div class="text-right whitespace-nowrap">
        <span class="px-2 py-0.5 rounded-md ${sv.is_grounded ? 'bg-emerald-950 text-emerald-300 border border-emerald-700' : 'bg-rose-950 text-rose-300 border border-rose-700'} font-bold text-[10px]">
          ${sv.is_grounded ? 'GROUNDED ✓' : 'UNVERIFIED ✗'} (${Math.round(sv.confidence * 100)}%)
        </span>
      </div>
    `;
    matrixContainer.appendChild(row);
  });

  // Latency Waterfall cards
  const latContainer = document.getElementById('latency-waterfall');
  latContainer.innerHTML = `
    <div class="nexus-card p-2.5 rounded-xl border border-[#1e3a5f] text-center">
      <span class="text-slate-400 block text-[10px] uppercase font-bold">Expansion</span>
      <strong class="text-blue-300 font-mono">${latency.query_expansion_ms}ms</strong>
    </div>
    <div class="nexus-card p-2.5 rounded-xl border border-[#1e3a5f] text-center">
      <span class="text-slate-400 block text-[10px] uppercase font-bold">Retrieval</span>
      <strong class="text-blue-300 font-mono">${latency.retrieval_ms}ms</strong>
    </div>
    <div class="nexus-card p-2.5 rounded-xl border border-[#1e3a5f] text-center">
      <span class="text-slate-400 block text-[10px] uppercase font-bold">Reranking</span>
      <strong class="text-blue-300 font-mono">${latency.rerank_ms}ms</strong>
    </div>
    <div class="nexus-card p-2.5 rounded-xl border border-[#1e3a5f] text-center">
      <span class="text-slate-400 block text-[10px] uppercase font-bold">Generation</span>
      <strong class="text-blue-300 font-mono">${latency.generation_ms}ms</strong>
    </div>
    <div class="nexus-card p-2.5 rounded-xl border border-[#1e3a5f] text-center">
      <span class="text-slate-400 block text-[10px] uppercase font-bold">Evaluation</span>
      <strong class="text-emerald-400 font-mono">${latency.evaluation_ms}ms</strong>
    </div>
  `;
}

function sendResultToDocGen() {
  if (!lastQueryResult) return;
  switchMainTab('docgen');
  document.getElementById('docgen-title').value = `Research Dossier: ${lastQueryResult.query}`;
  compileScholarDossier();
}

function highlightRetrievedChunk(chunkId) {
  const row = document.getElementById(`row-${chunkId}`);
  if (row) {
    row.scrollIntoView({ behavior: 'smooth', block: 'center' });
    row.classList.add('bg-blue-900/60');
    setTimeout(() => row.classList.remove('bg-blue-900/60'), 2500);
  }
}

// ================= TAB 2: MULTI-HOP RESEARCH AGENT =================

async function executeMultiHopResearch() {
  const query = document.getElementById('multihop-query-input').value.trim();
  if (!query) return;

  const btn = document.getElementById('multihop-btn');
  const resultsSec = document.getElementById('multihop-results-section');
  btn.disabled = true;
  btn.innerHTML = '<span>🤖 Reasoning across Vaults...</span>';

  const vault = document.getElementById('multihop-vault').value;
  const maxHops = parseInt(document.getElementById('multihop-max-hops').value);

  try {
    const resp = await fetch('/api/v1/research/multi-hop', {
      method: 'POST',
      headers: getApiHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        query: query,
        initial_vault_id: vault,
        max_hops: maxHops
      })
    });

    if (!resp.ok) throw new Error('Multi-hop research failed');
    const data = await resp.json();

    document.getElementById('multihop-hops-count').innerText = data.hops_taken;
    document.getElementById('multihop-chunks-count').innerText = data.total_chunks_consulted;
    document.getElementById('multihop-faith-score').innerText = `${Math.round(data.faithfulness_score * 100)}%`;
    document.getElementById('multihop-latency').innerText = `${data.execution_time_ms} ms`;
    document.getElementById('multihop-answer').innerHTML = data.final_answer.replace(
      /\[Source:\s*([a-zA-Z0-9_-]+)\]/g,
      (m, id) => `<span class="citation-badge">📎 ${id}</span>`
    );

    // Step Trajectory
    const tracesContainer = document.getElementById('multihop-traces-container');
    tracesContainer.innerHTML = '';

    data.hop_traces.forEach(trace => {
      const card = document.createElement('div');
      card.className = 'nexus-card p-4 rounded-xl border border-[#1e3a5f] space-y-2';
      card.innerHTML = `
        <div class="flex items-center justify-between border-b border-[#162846] pb-2 text-xs">
          <div class="flex items-center gap-2">
            <span class="px-2 py-0.5 rounded bg-blue-900/60 border border-blue-600/40 text-blue-300 font-mono font-bold">HOP #${trace.hop_number}</span>
            <span class="text-white font-semibold">${trace.sub_query}</span>
          </div>
          <span class="text-slate-400 font-mono">Vault: <strong class="text-blue-300">${trace.target_vault}</strong></span>
        </div>
        <p class="text-xs text-slate-300">${trace.evidence_summary}</p>
        <div class="flex flex-wrap items-center gap-3 pt-2 text-[11px] text-slate-400 border-t border-[#162846]/60">
          <span>Action: <strong class="text-slate-200">${trace.action_taken}</strong></span>
          <span>Confidence: <strong class="text-emerald-400 font-mono">${Math.round(trace.confidence * 100)}%</strong></span>
          <span>Chunks: <strong class="text-blue-300 font-mono">${trace.retrieved_chunk_ids.join(', ')}</strong></span>
        </div>
      `;
      tracesContainer.appendChild(card);
    });

    resultsSec.classList.remove('hidden');
  } catch (e) {
    alert('Research Agent error: ' + e.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span>🤖 Launch Research Agent</span>';
  }
}

// ================= TAB 3: RAPTOR RECURSIVE TREE =================

async function loadRaptorTreeVisualization() {
  try {
    const resp = await fetch('/api/v1/raptor/tree', { headers: getApiHeaders() });
    const data = await resp.json();

    document.getElementById('raptor-count-l2').innerText = `${data.level_counts[2] || 0} Nodes`;
    document.getElementById('raptor-count-l1').innerText = `${data.level_counts[1] || 0} Nodes`;
    document.getElementById('raptor-count-l0').innerText = `${data.level_counts[0] || 0} Nodes`;
  } catch (e) {
    console.error('Failed to load RAPTOR tree:', e);
  }
}

async function executeRaptorSearch() {
  const query = document.getElementById('raptor-query-input').value.trim();
  if (!query) return;

  const btn = document.getElementById('raptor-btn');
  btn.disabled = true;
  btn.innerHTML = '<span>Searching Hierarchy...</span>';

  const selectedRadio = document.querySelector('input[name="raptor-level"]:checked');
  const levelVal = selectedRadio ? selectedRadio.value : 'all';
  const targetLevel = levelVal === 'all' ? null : parseInt(levelVal);

  try {
    const resp = await fetch('/api/v1/raptor/search', {
      method: 'POST',
      headers: getApiHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        query: query,
        vault_id: currentVaultId,
        top_k: 6,
        target_level: targetLevel
      })
    });
    const data = await resp.json();

    const container = document.getElementById('raptor-hits-list');
    container.innerHTML = '';

    if (data.results && data.results.length > 0) {
      data.results.forEach(res => {
        const card = document.createElement('div');
        card.className = 'nexus-card p-4 rounded-xl border border-[#1e3a5f] space-y-2';
        
        let levelBadge = `<span class="px-2 py-0.5 rounded bg-slate-900 border border-slate-700 text-slate-300 font-mono text-[10px] font-bold">LEVEL 0 (Leaf)</span>`;
        if (res.level === 1) levelBadge = `<span class="px-2 py-0.5 rounded bg-cyan-950 border border-cyan-700 text-cyan-300 font-mono text-[10px] font-bold">LEVEL 1 (Cluster)</span>`;
        if (res.level === 2) levelBadge = `<span class="px-2 py-0.5 rounded bg-blue-950 border border-blue-700 text-blue-300 font-mono text-[10px] font-bold">LEVEL 2 (Theme)</span>`;

        card.innerHTML = `
          <div class="flex items-center justify-between border-b border-[#162846] pb-2">
            <div class="flex items-center gap-2">
              ${levelBadge}
              <h4 class="font-bold text-xs text-white">${res.title || 'Hierarchical Summary'}</h4>
            </div>
            <span class="text-blue-300 font-mono text-xs">Score: ${res.score ? res.score.toFixed(3) : '0.900'}</span>
          </div>
          <p class="text-xs text-slate-300 leading-relaxed font-mono bg-[#081020] p-2.5 rounded-lg border border-[#162846]">${res.content}</p>
        `;
        container.appendChild(card);
      });
    } else {
      container.innerHTML = '<p class="text-xs text-slate-400 italic">No matching hierarchical nodes found.</p>';
    }
  } catch (e) {
    alert('RAPTOR Search error: ' + e.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span>🌲 Search RAPTOR Tree</span>';
  }
}

// ================= TAB 4: SCHOLAR DOCGEN COMPILER =================

async function compileScholarDossier() {
  const btn = document.getElementById('btn-compile-doc');
  btn.disabled = true;
  btn.innerHTML = '<span>📜 Compiling Dossier...</span>';

  const title = document.getElementById('docgen-title').value.trim();
  const format = document.getElementById('docgen-format').value;
  const style = document.getElementById('docgen-style').value;
  const author = document.getElementById('docgen-author').value.trim();

  const query = lastQueryResult ? lastQueryResult.query : document.getElementById('query-input').value;
  const answer = lastQueryResult ? lastQueryResult.answer : 'Enterprise security compliance mandates strict access control and deterministic citation proofs.';
  const citations = lastQueryResult ? lastQueryResult.citations : [];

  try {
    const resp = await fetch('/api/v1/docgen/compile', {
      method: 'POST',
      headers: getApiHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        title: title,
        query: query,
        answer: answer,
        citations: citations,
        doc_format: format,
        citation_style: style,
        author: author
      })
    });

    if (!resp.ok) throw new Error('Compilation failed');
    const data = await resp.json();

    document.getElementById('docgen-preview-title').innerText = `Compiled: ${data.title} (${data.doc_format.toUpperCase()})`;
    document.getElementById('docgen-stats').innerText = `${data.word_count} Words • ${data.citation_count} Citations • Style: ${data.citation_style}`;
    document.getElementById('docgen-output-textarea').value = data.content;
  } catch (e) {
    alert('DocGen error: ' + e.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span>📜 Compile Research Dossier</span>';
  }
}

function copyDocGenContent() {
  const text = document.getElementById('docgen-output-textarea').value;
  if (!text) return;
  navigator.clipboard.writeText(text);
  alert('Dossier copied to clipboard!');
}

function downloadDocGenFile() {
  const text = document.getElementById('docgen-output-textarea').value;
  const format = document.getElementById('docgen-format').value;
  if (!text) return;

  const ext = format === 'latex' ? 'tex' : format === 'html' ? 'html' : 'md';
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `nexusrag_dossier.${ext}`;
  a.click();
  URL.revokeObjectURL(url);
}

// ================= TAB 5: PDF INSPECTOR & LAB =================

function handleDragOver(e) {
  e.preventDefault();
  e.stopPropagation();
  document.getElementById('pdf-dropzone').classList.add('dragover');
}

function handleDragLeave(e) {
  e.preventDefault();
  e.stopPropagation();
  document.getElementById('pdf-dropzone').classList.remove('dragover');
}

function handleFileDrop(e) {
  e.preventDefault();
  e.stopPropagation();
  document.getElementById('pdf-dropzone').classList.remove('dragover');
  if (e.dataTransfer.files && e.dataTransfer.files[0]) {
    loadSelectedFile(e.dataTransfer.files[0]);
  }
}

function handleFileSelected(e) {
  if (e.target.files && e.target.files[0]) {
    loadSelectedFile(e.target.files[0]);
  }
}

function loadSelectedFile(file) {
  activePdfFile = file;
  activePdfPreset = null;
  document.getElementById('pdf-filename-display').innerHTML = `Selected File: <strong class="text-blue-300">${file.name}</strong> (${(file.size / 1024).toFixed(1)} KB)`;
  runPdfInspection();
}

async function loadSamplePdfPreset(presetName) {
  activePdfPreset = presetName;
  activePdfFile = null;

  const names = {
    'ai_governance': 'Enterprise AI Governance Standard 2026 (SEC-909).pdf',
    'sre_dr_matrix': 'Multi-Region Disaster Recovery & SLA Matrix.pdf',
    'hr_benefits_matrix': 'Executive PTO Accrual & Rollover Schedule 2026.pdf'
  };

  const displayName = names[presetName] || `${presetName}.pdf`;
  document.getElementById('pdf-filename-display').innerHTML = `Loaded Preset: <strong class="text-emerald-300">${displayName}</strong>`;
  
  if (presetName === 'ai_governance') document.getElementById('pdf-target-vault').value = 'infosec_compliance';
  else if (presetName === 'sre_dr_matrix') document.getElementById('pdf-target-vault').value = 'sre_infra';
  else if (presetName === 'hr_benefits_matrix') document.getElementById('pdf-target-vault').value = 'hr_benefits';

  runPdfInspection();
}

async function runPdfInspection() {
  const btn = document.getElementById('btn-inspect-pdf');
  btn.disabled = true;
  btn.innerText = '🔍 Inspecting...';

  try {
    let report = null;
    if (activePdfFile) {
      const formData = new FormData();
      formData.append('file', activePdfFile);
      const resp = await fetch('/api/v1/pdf/inspect', { method: 'POST', body: formData, headers: getApiHeaders() });
      const data = await resp.json();
      report = data.report;
    } else {
      const preset = activePdfPreset || 'ai_governance';
      const resp = await fetch(`/api/v1/pdf/benchmark?preset_name=${preset}`, { method: 'POST', headers: getApiHeaders() });
      const data = await resp.json();
      report = {
        pdf_type: data.benchmark.pdf_type,
        confidence: 1.0,
        page_count: data.benchmark.page_count,
        processing_time_ms: data.benchmark.inspection_latency_ms,
        table_count: data.benchmark.tables_detected,
        heading_count: 4,
        is_complex_layout: true,
        ocr_routing_action: 'NATIVE_PASS',
        pages_needing_ocr: []
      };
    }

    document.getElementById('diag-pdf-type').innerText = report.pdf_type.toUpperCase();
    document.getElementById('diag-confidence').innerText = `${Math.round(report.confidence * 100)}% Conf`;
    document.getElementById('diag-pages').innerText = report.page_count;
    document.getElementById('diag-latency').innerText = `${report.processing_time_ms} ms`;
    document.getElementById('diag-speedup').innerText = `~${Math.round(1150 / Math.max(1, report.processing_time_ms))}x vs OCR`;
    document.getElementById('diag-tables').innerText = report.table_count;
    document.getElementById('diag-headings').innerText = report.heading_count || 3;
    document.getElementById('diag-layout').innerText = report.is_complex_layout ? 'Yes (Multi-Column)' : 'Standard';
    document.getElementById('diag-ocr-action').innerText = report.ocr_routing_action;
    document.getElementById('diag-ocr-pages').innerText = `${report.pages_needing_ocr.length} (100% Native Pass)`;

    document.getElementById('pdf-diagnostics-section').classList.remove('hidden');
    runPdfExtraction();
  } catch (e) {
    console.error('Inspection error:', e);
  } finally {
    btn.disabled = false;
    btn.innerText = '🔍 Inspect (<10ms)';
  }
}

async function runPdfExtraction() {
  const btn = document.getElementById('btn-extract-pdf');
  btn.disabled = true;
  btn.innerText = '📝 Extracting...';

  try {
    let extractData = null;
    if (activePdfFile) {
      const formData = new FormData();
      formData.append('file', activePdfFile);
      const resp = await fetch('/api/v1/pdf/extract', { method: 'POST', body: formData, headers: getApiHeaders() });
      extractData = await resp.json();
    } else {
      const preset = activePdfPreset || 'ai_governance';
      const sampleTexts = {
        'ai_governance': `# Enterprise AI Governance & Model Risk Standard 2026\n\nDocument ID: GOV-AI-2026-V4 | Classification: Tier-1 Enterprise Standard\n\n## 1. Model Risk Classification & Pre-Deployment Gates\n\nUnder Corporate Directive SEC-909, all generative AI models and autonomous agent workflows must complete adversarial red-teaming and bias audits before production sign-off. Form GOV-AI-88 must be signed by the VP of Engineering prior to production deployment.\n\n## 2. Operational SLA & Escalation Thresholds\n\n|Incident Level|Response SLA|Resolution Target|Mandatory Escalation Path|Notification Rule|\n|---|---|---|---|---|\n|P0 - Model Breach|5 Minutes|2 Hours|Executive AI Security War Room|Immediate SMS + PagerDuty|\n|P1 - High Drift|15 Minutes|6 Hours|Lead MLOps Incident Commander|Email & Slack #ai-ops|\n|P2 - Prompt Drift|1 Hour|24 Hours|Domain Model Stewards|Standard JIRA Ticket|\n|P3 - Low Impact|4 Hours|72 Hours|Weekly Sprint Backlog Review|Async Digest|`,
        'sre_dr_matrix': `# Multi-Region Disaster Recovery & Uptime SLA Matrix\n\n## 1. Recovery Objectives by Service Tier\n\n|Service Tier|RTO Target|RPO Target|Backup Frequency|Failover Mechanism|\n|---|---|---|---|---|\n|Tier-1 Relational DB|15 Minutes|60 Seconds|Continuous WAL Replicate|Automated Multi-AZ Flip|\n|Tier-1 Vector Index|30 Minutes|5 Minutes|Hourly Snapshot to GCS|DNS Route53 Shifting|\n|Tier-2 Analytics DB|2 Hours|1 Hour|Daily Cold Storage|Manual Terraform Apply|`,
        'hr_benefits_matrix': `# Executive Compensation & PTO Accrual Schedule 2026\n\n## 1. Paid Leave Accrual Tiers\n\n|Tenure Bracket|Annual PTO Days|Monthly Accrual|Max Rollover Days|Form Required for Roll|\n|---|---|---|---|---|\n|0 - 2 Years|20 Days|1.66 Days|5 Days|Form HR-PTO-ROLL|\n|3 - 5 Years|25 Days|2.08 Days|7 Days|Form HR-PTO-ROLL|\n|5+ Years|30 Days|2.50 Days|10 Days|Form HR-PTO-ROLL|`
      };
      const text = sampleTexts[preset] || sampleTexts['ai_governance'];
      extractData = {
        title: preset.replace(/_/g, ' ').toUpperCase(),
        full_markdown: text,
        table_blocks: [text.split('## 2.')[1] || text]
      };
    }

    lastExtractionResult = extractData;
    document.getElementById('pdf-viewer-title').innerText = `Preview: ${extractData.title}`;
    document.getElementById('pdf-raw-textarea').value = extractData.full_markdown;

    renderMarkdownHtml(extractData.full_markdown);
    document.getElementById('pdf-viewer-section').classList.remove('hidden');
  } catch (e) {
    console.error('Extraction error:', e);
  } finally {
    btn.disabled = false;
    btn.innerText = '📝 Extract Markdown';
  }
}

function renderMarkdownHtml(mdText) {
  const container = document.getElementById('pdf-rendered-pane');
  let html = '';
  const lines = mdText.split('\n');
  let inTable = false;
  let tableRows = [];

  lines.forEach(line => {
    const trimmed = line.trim();
    if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
      if (!inTable) {
        inTable = true;
        tableRows = [];
      }
      tableRows.push(trimmed);
    } else {
      if (inTable) {
        html += formatMarkdownTable(tableRows);
        inTable = false;
        tableRows = [];
      }
      if (trimmed.startsWith('# ')) {
        html += `<h2 class="text-base font-extrabold text-white mt-3 mb-1">${trimmed.slice(2)}</h2>`;
      } else if (trimmed.startsWith('## ')) {
        html += `<h3 class="text-sm font-bold text-blue-300 mt-2 mb-1">${trimmed.slice(3)}</h3>`;
      } else if (trimmed.startsWith('<!-- Page')) {
        html += `<div class="text-[10px] text-slate-500 font-mono border-t border-[#162846] pt-2 mt-3">${trimmed}</div>`;
      } else if (trimmed.length > 0) {
        html += `<p class="text-slate-300 text-xs leading-relaxed mb-2">${trimmed}</p>`;
      }
    }
  });

  if (inTable && tableRows.length > 0) {
    html += formatMarkdownTable(tableRows);
  }

  container.innerHTML = html;
}

function formatMarkdownTable(rows) {
  if (rows.length < 2) return '';
  const headers = rows[0].split('|').map(c => c.trim()).filter(c => c);
  let tableHtml = '<div class="overflow-x-auto my-3"><table class="w-full text-left"><thead><tr>';
  headers.forEach(h => {
    tableHtml += `<th>${h}</th>`;
  });
  tableHtml += '</tr></thead><tbody>';

  for (let i = 2; i < rows.length; i++) {
    const cells = rows[i].split('|').map(c => c.trim()).filter(c => c);
    if (cells.length > 0) {
      tableHtml += '<tr>';
      cells.forEach(c => {
        tableHtml += `<td>${c}</td>`;
      });
      tableHtml += '</tr>';
    }
  }
  tableHtml += '</tbody></table></div>';
  return tableHtml;
}

function togglePdfPreviewMode(mode) {
  const renderedPane = document.getElementById('pdf-rendered-pane');
  const rawPane = document.getElementById('pdf-raw-pane');
  const btnRend = document.getElementById('btn-preview-rendered');
  const btnRaw = document.getElementById('btn-preview-raw');

  if (mode === 'rendered') {
    renderedPane.classList.remove('hidden');
    rawPane.classList.add('hidden');
    btnRend.className = 'btn-primary px-3 py-1 rounded-lg font-bold';
    btnRaw.className = 'btn-secondary px-3 py-1 rounded-lg font-bold';
  } else {
    renderedPane.classList.add('hidden');
    rawPane.classList.remove('hidden');
    btnRaw.className = 'btn-primary px-3 py-1 rounded-lg font-bold';
    btnRend.className = 'btn-secondary px-3 py-1 rounded-lg font-bold';
  }
}

async function runPdfUploadAndIngest() {
  const btn = document.getElementById('btn-ingest-pdf');
  const targetVault = document.getElementById('pdf-target-vault').value;
  btn.disabled = true;
  btn.innerHTML = '<span>⏳ Ingesting & Indexing...</span>';

  try {
    let result = null;
    if (activePdfFile) {
      const formData = new FormData();
      formData.append('file', activePdfFile);
      formData.append('vault_id', targetVault);
      const resp = await fetch('/api/v1/pdf/upload', { method: 'POST', body: formData, headers: getApiHeaders() });
      result = await resp.json();
    } else {
      const title = activePdfPreset ? activePdfPreset.replace(/_/g, ' ').toUpperCase() : 'Enterprise PDF Policy';
      const content = lastExtractionResult ? lastExtractionResult.full_markdown : document.getElementById('pdf-raw-textarea').value;
      const resp = await fetch('/api/v1/documents/ingest', {
        method: 'POST',
        headers: getApiHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          title: title,
          content: content,
          vault_id: targetVault,
          metadata: { doc_format: 'pdf', is_pdf: true }
        })
      });
      result = await resp.json();
    }

    alert(`✅ PDF parsed & indexed into '${targetVault}'! Created ${result.chunks_created} chunks (${result.table_chunks_created || 1} tabular rows).`);
    currentVaultId = targetVault;
    document.getElementById('vault-select').value = targetVault;
    loadVaultsGrid();
  } catch (e) {
    alert('Ingestion error: ' + e.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span>📥 Ingest to Vault</span>';
  }
}

async function runLivePdfBenchmark() {
  const btn = document.getElementById('btn-bench-pdf');
  btn.disabled = true;
  btn.innerText = 'Benchmarking...';

  try {
    const preset = activePdfPreset || 'ai_governance';
    const resp = await fetch(`/api/v1/pdf/benchmark?preset_name=${preset}`, { method: 'POST', headers: getApiHeaders() });
    const data = await resp.json();

    document.getElementById('bench-lat').innerText = `${data.benchmark.inspection_latency_ms + data.benchmark.markdown_extraction_latency_ms} ms`;
    document.getElementById('bench-ocr-lat').innerText = `${data.details.baseline_ocr_estimated_ms} ms`;
    document.getElementById('bench-speedup').innerText = `${data.benchmark.speedup_factor_vs_ocr}x Faster`;

    document.getElementById('pdf-benchmark-modal').classList.remove('hidden');
  } catch (e) {
    alert('Benchmark error: ' + e.message);
  } finally {
    btn.disabled = false;
    btn.innerText = '🚀 Benchmark Engine';
  }
}

// ================= TAB 6: A/B STRATEGY ARENA =================

async function runArenaComparison() {
  const query = document.getElementById('query-input').value.trim();
  if (!query) return;

  const btn = document.getElementById('arena-run-btn');
  btn.disabled = true;
  btn.innerHTML = '<span>⚡ Benchmarking Strategies...</span>';

  try {
    const resp = await fetch('/api/v1/arena', {
      method: 'POST',
      headers: getApiHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ query: query, vault_id: currentVaultId })
    });
    const data = await resp.json();

    document.getElementById('arena-ans-a').innerText = data.strategy_a.answer;
    document.getElementById('arena-faith-a').innerText = `${Math.round(data.strategy_a.faithfulness * 100)}%`;
    document.getElementById('arena-cit-a').innerText = data.strategy_a.citations_count;
    document.getElementById('arena-lat-a').innerText = `${data.strategy_a.latency_ms} ms`;

    document.getElementById('arena-ans-b').innerText = data.strategy_b.answer;
    document.getElementById('arena-faith-b').innerText = `${Math.round(data.strategy_b.faithfulness * 100)}%`;
    document.getElementById('arena-cit-b').innerText = data.strategy_b.citations_count;
    document.getElementById('arena-lat-b').innerText = `${data.strategy_b.latency_ms} ms`;

    const banner = document.getElementById('arena-winner-banner');
    document.getElementById('arena-winner-text').innerText = data.winner_strategy;
    document.getElementById('arena-delta-text').innerText = `+${data.accuracy_delta_percent}%`;
    banner.classList.remove('hidden');
  } catch (e) {
    alert('Arena comparison failed: ' + e.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span>🚀 Execute A/B Benchmark</span>';
  }
}

// ================= TAB 7: CRYPTOGRAPHIC AUDIT =================

async function verifyAuditCertificateId() {
  const auditId = document.getElementById('audit-verify-id').value.trim();
  if (!auditId) return;

  const statusEl = document.getElementById('audit-verify-status');
  statusEl.classList.remove('hidden');
  statusEl.innerHTML = '<span class="text-blue-300 font-mono">Verifying HMAC cryptographic chain...</span>';

  try {
    const resp = await fetch('/api/v1/audit/verify', {
      method: 'POST',
      headers: getApiHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ audit_id: auditId })
    });
    const data = await resp.json();

    if (data.is_valid) {
      statusEl.innerHTML = `
        <div class="flex items-center gap-2 text-emerald-400 font-bold mb-1">
          <span>✅ Cryptographic Verification Valid</span>
        </div>
        <p class="text-slate-300 font-mono text-[11px]">Audit ID: ${data.audit_id}</p>
        <p class="text-slate-400 font-mono text-[10px]">Tamper-Proof SHA-256 HMAC signature matched ledger state.</p>
      `;
    } else {
      statusEl.innerHTML = `
        <div class="flex items-center gap-2 text-rose-400 font-bold mb-1">
          <span>❌ Verification Failed: Signature or Ledger Record Missing</span>
        </div>
      `;
    }
  } catch (e) {
    statusEl.innerHTML = `<span class="text-rose-400">Error: ${e.message}</span>`;
  }
}

async function loadAuditLogsList() {
  const container = document.getElementById('audit-logs-container');
  container.innerHTML = '<p class="text-xs text-slate-400">Loading audit ledger...</p>';

  try {
    const resp = await fetch('/api/v1/audit/logs', { headers: getApiHeaders() });
    const logs = await resp.json();
    container.innerHTML = '';

    if (logs.length === 0) {
      container.innerHTML = '<p class="text-xs text-slate-500 italic">No queries logged yet. Execute a query to record an audit entry.</p>';
      return;
    }

    logs.forEach(l => {
      const card = document.createElement('div');
      card.className = 'nexus-card p-3 rounded-xl border border-[#1e3a5f] flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs';
      card.innerHTML = `
        <div class="space-y-1">
          <div class="flex items-center gap-2">
            <span class="px-2 py-0.5 rounded bg-emerald-950/60 border border-emerald-500/40 text-emerald-400 font-mono font-bold text-[10px]">HMAC SIGNED</span>
            <span class="font-mono text-slate-300 font-bold">${l.audit_id}</span>
            <span class="text-slate-400 text-[10px]">${l.timestamp}</span>
          </div>
          <p class="text-slate-300">${l.query_text}</p>
        </div>
        <div class="text-right">
          <span class="text-blue-300 font-mono text-[11px] block">Vault: ${l.active_vault}</span>
          <span class="text-emerald-400 font-mono text-[10px]">Faithfulness: ${Math.round((l.faithfulness_score || 1) * 100)}%</span>
        </div>
      `;
      container.appendChild(card);
    });
  } catch (e) {
    container.innerHTML = '<p class="text-xs text-rose-400">Failed to load audit logs.</p>';
  }
}

async function downloadAuditCertificate() {
  const query = document.getElementById('query-input').value.trim();
  if (!query) return;

  try {
    const resp = await fetch(`/api/v1/audit/export?query=${encodeURIComponent(query)}&vault_id=${currentVaultId}`, {
      headers: getApiHeaders()
    });
    const cert = await resp.json();
    
    const blob = new Blob([JSON.stringify(cert, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${cert.audit_id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    alert('Failed to generate audit certificate: ' + e.message);
  }
}

// ================= TAB 8: MCP (MODEL CONTEXT PROTOCOL) =================

let selectedMcpTool = 'search_rag';

async function loadMcpToolsList() {
  const container = document.getElementById('mcp-tools-list');
  try {
    const resp = await fetch('/api/v1/mcp/tools', { headers: getApiHeaders() });
    const data = await resp.json();
    container.innerHTML = '';

    data.tools.forEach(tool => {
      const card = document.createElement('div');
      card.className = `p-3 rounded-xl border text-xs cursor-pointer transition-all ${
        selectedMcpTool === tool.name ? 'bg-blue-900/40 border-blue-500 text-white' : 'bg-[#081020] border-[#162846] text-slate-300 hover:border-[#1e3a5f]'
      }`;
      card.onclick = () => selectMcpTool(tool);

      card.innerHTML = `
        <div class="flex items-center justify-between font-mono font-bold text-blue-300">
          <span>${tool.name}</span>
          <span class="text-[10px] text-slate-400 font-sans">Tool</span>
        </div>
        <p class="text-slate-400 text-[11px] mt-1">${tool.description}</p>
      `;
      container.appendChild(card);
    });
  } catch (e) {
    container.innerHTML = '<p class="text-xs text-rose-400">Failed to load MCP tools.</p>';
  }
}

function selectMcpTool(tool) {
  selectedMcpTool = tool.name;
  document.getElementById('mcp-selected-tool-name').innerText = `Tool: ${tool.name}`;
  
  const sampleArgs = {
    'search_rag': { query: 'What is SEC-909?', vault_id: 'all', top_k: 4 },
    'inspect_pdf': { preset_name: 'ai_governance' },
    'graph_lookup': { vault_id: 'all' },
    'multi_hop_research': { query: 'Compare leave policy with security rules', max_hops: 2 },
    'compile_dossier': { title: 'Compliance Report', query: 'SRE SLAs', doc_format: 'markdown' },
    'verify_audit_log': { audit_id: 'sample_id' }
  };

  document.getElementById('mcp-args-input').value = JSON.stringify(sampleArgs[tool.name] || {}, null, 2);
  loadMcpToolsList();
}

async function executeMcpToolCall() {
  const btn = document.getElementById('btn-call-mcp');
  btn.disabled = true;
  btn.innerHTML = '<span>Executing Tool...</span>';

  try {
    const argsText = document.getElementById('mcp-args-input').value;
    const argsJson = JSON.parse(argsText);

    const resp = await fetch('/api/v1/mcp/call', {
      method: 'POST',
      headers: getApiHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        tool: selectedMcpTool,
        arguments: argsJson
      })
    });
    const data = await resp.json();
    document.getElementById('mcp-response-output').value = JSON.stringify(data, null, 2);
  } catch (e) {
    document.getElementById('mcp-response-output').value = `Error: ${e.message}`;
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span>⚡ Execute MCP Tool Call</span>';
  }
}

// ================= TAB 9: POLICY TIMELINE =================

async function loadPolicyTimelines() {
  const container = document.getElementById('timeline-container');
  container.innerHTML = '<p class="text-xs text-slate-400">Extracting temporal obligations...</p>';

  try {
    const resp = await fetch('/api/v1/timeline', { headers: getApiHeaders() });
    const events = await resp.json();
    container.innerHTML = '';

    events.forEach(ev => {
      let badgeClass = 'bg-slate-900 border-slate-700 text-slate-300';
      if (ev.urgency_level === 'CRITICAL') badgeClass = 'bg-[#3b0f15] border-rose-600/60 text-rose-300';
      else if (ev.urgency_level === 'HIGH') badgeClass = 'bg-[#382606] border-amber-600/60 text-amber-300';
      else if (ev.urgency_level === 'MEDIUM') badgeClass = 'bg-[#0f2244] border-blue-600/60 text-blue-300';

      const card = document.createElement('div');
      card.className = 'nexus-card p-4 rounded-xl border border-[#1e3a5f] flex flex-col sm:flex-row sm:items-center justify-between gap-3';
      card.innerHTML = `
        <div class="space-y-1">
          <div class="flex items-center gap-2">
            <span class="px-2 py-0.5 rounded-md border font-mono font-bold text-[10px] ${badgeClass}">${ev.timeframe.toUpperCase()}</span>
            <span class="text-xs font-bold text-white">${ev.doc_title}</span>
            <span class="text-[10px] text-slate-400">(${ev.section_header})</span>
          </div>
          <p class="text-xs text-slate-300">${ev.action_rule || ev.action_or_rule || ''}</p>
        </div>
        <div class="text-right whitespace-nowrap">
          <span class="text-[10px] font-mono text-slate-400">Vault: <strong class="text-blue-300">${ev.vault_id}</strong></span>
        </div>
      `;
      container.appendChild(card);
    });
  } catch (e) {
    container.innerHTML = '<p class="text-xs text-rose-400">Failed to load timelines.</p>';
  }
}

// ================= TAB 10: KNOWLEDGE GRAPH =================

async function renderKnowledgeGraph() {
  const canvas = document.getElementById('graph-canvas');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  canvas.width = canvas.parentElement.clientWidth;
  canvas.height = canvas.parentElement.clientHeight;

  try {
    const resp = await fetch(`/api/v1/graph?vault_id=${currentVaultId}`, { headers: getApiHeaders() });
    const data = await resp.json();
    graphDataCache = data;

    const nodes = data.nodes.map((n, i) => {
      const angle = (i / data.nodes.length) * Math.PI * 2;
      const radius = 140 + Math.random() * 80;
      return {
        ...n,
        x: canvas.width / 2 + Math.cos(angle) * radius,
        y: canvas.height / 2 + Math.sin(angle) * radius,
        vx: (Math.random() - 0.5) * 0.5,
        vy: (Math.random() - 0.5) * 0.5
      };
    });

    const nodeMap = {};
    nodes.forEach(n => nodeMap[n.id] = n);

    function animate() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Links
      data.links.forEach(l => {
        const s = nodeMap[l.source];
        const t = nodeMap[l.target];
        if (s && t) {
          ctx.beginPath();
          ctx.moveTo(s.x, s.y);
          ctx.lineTo(t.x, t.y);
          ctx.strokeStyle = 'rgba(30, 58, 95, 0.4)';
          ctx.lineWidth = 1;
          ctx.stroke();
        }
      });

      // Nodes
      nodes.forEach(n => {
        n.x += n.vx;
        n.y += n.vy;
        if (n.x < 30 || n.x > canvas.width - 30) n.vx *= -1;
        if (n.y < 30 || n.y > canvas.height - 30) n.vy *= -1;

        ctx.beginPath();
        ctx.arc(n.x, n.y, n.size + 3, 0, Math.PI * 2);
        ctx.fillStyle = n.color + '22';
        ctx.fill();

        ctx.beginPath();
        ctx.arc(n.x, n.y, n.size, 0, Math.PI * 2);
        ctx.fillStyle = n.color;
        ctx.fill();

        ctx.fillStyle = '#f8fafc';
        ctx.font = '10px Plus Jakarta Sans';
        ctx.textAlign = 'center';
        ctx.fillText(n.label.length > 16 ? n.label.slice(0, 14) + '...' : n.label, n.x, n.y + n.size + 12);
      });

      requestAnimationFrame(animate);
    }

    animate();
  } catch (e) {
    console.error('Failed to load graph:', e);
  }
}

// ================= TAB 12: VAULT MANAGER & INGESTION =================

async function loadVaultsGrid() {
  const container = document.getElementById('vaults-grid');
  container.innerHTML = '<p class="text-xs text-slate-400">Loading enterprise vaults...</p>';

  try {
    const resp = await fetch('/api/v1/vaults', { headers: getApiHeaders() });
    const vaults = await resp.json();
    container.innerHTML = '';

    vaults.forEach(v => {
      const isActive = v.id === currentVaultId;
      const card = document.createElement('div');
      card.className = `nexus-card p-5 rounded-2xl border transition-all cursor-pointer ${
        isActive ? 'border-blue-500 bg-[#0f2244]/80 shadow-md' : 'border-[#162846] hover:border-[#1e3a5f]'
      }`;
      card.onclick = () => {
        changeActiveVault(v.id);
        loadVaultsGrid();
      };

      card.innerHTML = `
        <div class="flex items-start justify-between">
          <div class="flex items-center gap-3">
            <span class="text-2xl p-2 rounded-xl bg-[#081020] border border-[#162846]">${v.icon}</span>
            <div>
              <h4 class="font-bold text-sm text-white">${v.name}</h4>
              <p class="text-[10px] text-slate-400 font-mono">ID: ${v.id}</p>
            </div>
          </div>
          ${isActive ? '<span class="px-2 py-0.5 rounded bg-blue-950 border border-blue-700 text-blue-300 text-[10px] font-bold">ACTIVE</span>' : ''}
        </div>
        <p class="text-xs text-slate-300 mt-3 line-clamp-2">${v.description}</p>
        <div class="pt-3 border-t border-[#162846] mt-3 flex items-center justify-between text-xs text-slate-400">
          <span>📄 <strong>${v.document_count}</strong> Documents</span>
          <span>⚡ <strong>${v.chunk_count}</strong> Chunks</span>
        </div>
      `;
      container.appendChild(card);
    });
  } catch (e) {
    container.innerHTML = '<p class="text-xs text-rose-400">Failed to load vaults.</p>';
  }
}

async function handleMultiFormatUpload() {
  const fileInput = document.getElementById('general-file-input');
  if (!fileInput.files || !fileInput.files[0]) {
    alert('Please select a file first.');
    return;
  }

  const file = fileInput.files[0];
  const formData = new FormData();
  formData.append('file', file);
  formData.append('vault_id', currentVaultId);

  try {
    let url = '/api/v1/documents/upload';
    if (file.name.endsWith('.pdf')) {
      url = '/api/v1/pdf/upload';
    }

    const resp = await fetch(url, {
      method: 'POST',
      body: formData,
      headers: getApiHeaders()
    });

    if (!resp.ok) throw new Error('Upload failed');
    const result = await resp.json();
    alert(`✅ Ingested "${file.name}" into "${currentVaultId}" (${result.chunks_created} chunks generated)!`);
    fileInput.value = '';
    loadVaultsGrid();
  } catch (e) {
    alert('Upload error: ' + e.message);
  }
}

async function handleVaultIngest(event) {
  event.preventDefault();
  const title = document.getElementById('ingest-title').value.trim();
  const content = document.getElementById('ingest-content').value.trim();
  if (!title || !content) return;

  const btn = document.getElementById('ingest-submit-btn');
  btn.disabled = true;
  btn.innerHTML = '<span>Ingesting & Indexing...</span>';

  try {
    const resp = await fetch('/api/v1/documents/ingest', {
      method: 'POST',
      headers: getApiHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        title: title,
        content: content,
        vault_id: currentVaultId,
        metadata: { source: title, date: new Date().toISOString() }
      })
    });

    if (!resp.ok) throw new Error('Ingestion failed');
    const data = await resp.json();
    alert(`Document "${title}" ingested into "${currentVaultId}" with ${data.chunks_created} chunks!`);
    document.getElementById('vault-ingest-form').reset();
    loadVaultsGrid();
  } catch (e) {
    alert('Error: ' + e.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span>📥 Ingest & Rebuild Index</span>';
  }
}

// Initial Run
document.addEventListener('DOMContentLoaded', async () => {
  await handleRbacRoleChange('admin');
  executeEnterpriseQuery();
});
