// NexusRAG Enterprise 4.0 Control Plane Client

let currentVaultId = "all";
let graphSimulation = null;
let graphDataCache = null;

// Tab Switching
function switchMainTab(tabId) {
  ['query', 'arena', 'timeline', 'graph', 'triad', 'vaults'].forEach(t => {
    const el = document.getElementById(`tab-${t}`);
    const btn = document.getElementById(`nav-btn-${t}`);
    if (t === tabId) {
      el.classList.remove('hidden');
      btn.className = 'px-3 py-1.5 rounded-xl transition-all bg-indigo-600 text-white shadow-md font-semibold';
    } else {
      el.classList.add('hidden');
      btn.className = 'px-3 py-1.5 rounded-xl transition-all text-slate-400 hover:text-white font-semibold';
    }
  });

  if (tabId === 'graph') {
    renderKnowledgeGraph();
  } else if (tabId === 'vaults') {
    loadVaultsGrid();
  } else if (tabId === 'timeline') {
    loadPolicyTimelines();
  }
}

// Vault Selector Handling
async function changeActiveVault(vaultId) {
  currentVaultId = vaultId;
  try {
    const resp = await fetch('/api/v1/vaults/switch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ vault_id: vaultId })
    });
    if (resp.ok) {
      document.getElementById('vault-select').value = vaultId;
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
  document.getElementById('vault-select').value = vaultId;
  document.getElementById('query-input').value = query;
  executeEnterpriseQuery();
}

// Execute Enterprise RAG Query
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
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: query,
        vault_id: currentVaultId,
        alpha_hybrid_weight: alpha,
        rrf_k: rrf_k,
        top_k_rerank: top_k,
        use_hyde: use_hyde,
        use_multi_query: use_multi_query
      })
    });

    if (!response.ok) throw new Error('Query execution failed');

    const data = await response.json();
    renderQueryOutput(data);
    renderTriadMetrics(data.evaluation, data.latency);
    resultSec.classList.remove('hidden');
  } catch (error) {
    alert('Error: ' + error.message);
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerHTML = '<span>⚡ Execute RAG</span>';
  }
}

// Real-Time Server-Sent Events (SSE) Token Streaming
async function executeStreamingQuery() {
  const query = document.getElementById('query-input').value.trim();
  if (!query) return;

  const resultSec = document.getElementById('result-section');
  const answerEl = document.getElementById('answer-text');
  resultSec.classList.remove('hidden');
  answerEl.className = 'text-sm sm:text-base text-slate-100 leading-relaxed font-medium cursor-blink';
  answerEl.innerHTML = '';

  document.getElementById('total-latency').innerText = 'Streaming...';
  document.getElementById('res-vault-badge').innerText = `Vault: ${currentVaultId.toUpperCase()}`;

  try {
    const response = await fetch('/api/v1/query/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: query, vault_id: currentVaultId })
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
    answerEl.className = 'text-sm sm:text-base text-slate-100 leading-relaxed font-medium';
    executeEnterpriseQuery(); // Hydrate metadata and RAG Triad scores
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
      card.className = 'p-3 rounded-2xl bg-white/5 border border-white/10 text-xs space-y-1.5 cursor-pointer hover:border-indigo-500/50 transition-all';
      card.onclick = () => highlightRetrievedChunk(c.chunk_id);
      card.innerHTML = `
        <div class="flex items-center justify-between text-[11px]">
          <span class="font-bold text-indigo-300">${c.doc_title}</span>
          <span class="text-slate-400">Page ${c.page_number}</span>
        </div>
        <p class="text-slate-400 text-[10px]">Section: <strong class="text-slate-200">${c.section_header}</strong></p>
        <p class="text-slate-300 font-mono text-[11px] line-clamp-2 bg-black/40 p-2 rounded-lg border border-white/5">${c.snippet}</p>
      `;
      citContainer.appendChild(card);
    });
  } else {
    citContainer.innerHTML = `<p class="text-xs text-slate-500 italic col-span-2">No grounded document citations (query was answered as unknown or out-of-context).</p>`;
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
    row.className = 'hover:bg-white/5 transition-colors';
    row.innerHTML = `
      <td class="py-3 px-3 font-mono text-indigo-300 font-bold">${c.chunk_id}</td>
      <td class="py-3 px-3">
        <div class="font-semibold text-white">${c.doc_title}</div>
        <div class="text-[10px] text-slate-400">${c.section_header} (P.${c.page_number})</div>
      </td>
      <td class="py-3 px-3 text-center">
        <span class="px-2 py-0.5 rounded-md bg-blue-500/10 text-blue-300 font-mono">#${c.dense_rank} (${c.dense_score})</span>
      </td>
      <td class="py-3 px-3 text-center">
        <span class="px-2 py-0.5 rounded-md bg-amber-500/10 text-amber-300 font-mono">#${c.sparse_rank} (${c.sparse_score})</span>
      </td>
      <td class="py-3 px-3 text-center font-mono font-bold text-purple-300">${c.rrf_score}</td>
      <td class="py-3 px-3 text-center font-mono font-bold text-emerald-400">${c.rerank_score}</td>
      <td class="py-3 px-3 text-slate-300 font-mono text-[11px] max-w-xs truncate" title="${c.content.replace(/"/g, '&quot;')}">${c.content}</td>
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
      sv.is_grounded ? 'bg-emerald-950/20 border-emerald-500/30 text-emerald-200' : 'bg-rose-950/20 border-rose-500/30 text-rose-200'
    }`;
    row.innerHTML = `
      <div class="space-y-1">
        <p class="font-medium">${sv.sentence}</p>
        <p class="text-[10px] text-slate-400 font-mono">Source Evidence: ${sv.evidence_snippet}</p>
      </div>
      <div class="text-right whitespace-nowrap">
        <span class="px-2 py-0.5 rounded-md ${sv.is_grounded ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'} font-bold text-[10px]">
          ${sv.is_grounded ? 'GROUNDED ✓' : 'UNVERIFIED ✗'} (${Math.round(sv.confidence * 100)}%)
        </span>
      </div>
    `;
    matrixContainer.appendChild(row);
  });

  // Latency Waterfall cards
  const latContainer = document.getElementById('latency-waterfall');
  latContainer.innerHTML = `
    <div class="glass-card p-2.5 rounded-xl border border-white/5 text-center">
      <span class="text-slate-400 block text-[10px]">Expansion</span>
      <strong class="text-indigo-300">${latency.query_expansion_ms}ms</strong>
    </div>
    <div class="glass-card p-2.5 rounded-xl border border-white/5 text-center">
      <span class="text-slate-400 block text-[10px]">Retrieval</span>
      <strong class="text-blue-300">${latency.retrieval_ms}ms</strong>
    </div>
    <div class="glass-card p-2.5 rounded-xl border border-white/5 text-center">
      <span class="text-slate-400 block text-[10px]">Reranking</span>
      <strong class="text-purple-300">${latency.rerank_ms}ms</strong>
    </div>
    <div class="glass-card p-2.5 rounded-xl border border-white/5 text-center">
      <span class="text-slate-400 block text-[10px]">Generation</span>
      <strong class="text-pink-300">${latency.generation_ms}ms</strong>
    </div>
    <div class="glass-card p-2.5 rounded-xl border border-white/5 text-center">
      <span class="text-slate-400 block text-[10px]">Evaluation</span>
      <strong class="text-emerald-300">${latency.evaluation_ms}ms</strong>
    </div>
  `;
}

// ---------------- A/B STRATEGY ARENA CLIENT ----------------

async function runArenaComparison() {
  const query = document.getElementById('query-input').value.trim();
  if (!query) return;

  const btn = document.getElementById('arena-run-btn');
  btn.disabled = true;
  btn.innerHTML = '<span>⚡ Running A/B Benchmark...</span>';

  try {
    const resp = await fetch('/api/v1/arena', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: query, vault_id: currentVaultId })
    });
    const data = await resp.json();

    // Render Strategy A
    document.getElementById('arena-ans-a').innerText = data.strategy_a.answer;
    document.getElementById('arena-faith-a').innerText = `${Math.round(data.strategy_a.faithfulness * 100)}%`;
    document.getElementById('arena-cit-a').innerText = data.strategy_a.citations_count;
    document.getElementById('arena-lat-a').innerText = `${data.strategy_a.latency_ms} ms`;

    // Render Strategy B
    document.getElementById('arena-ans-b').innerText = data.strategy_b.answer;
    document.getElementById('arena-faith-b').innerText = `${Math.round(data.strategy_b.faithfulness * 100)}%`;
    document.getElementById('arena-cit-b').innerText = data.strategy_b.citations_count;
    document.getElementById('arena-lat-b').innerText = `${data.strategy_b.latency_ms} ms`;

    // Render Winner
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

// ---------------- POLICY TIMELINE CLIENT ----------------

async function loadPolicyTimelines() {
  const container = document.getElementById('timeline-container');
  container.innerHTML = '<p class="text-xs text-slate-400">Extracting temporal obligations...</p>';

  try {
    const resp = await fetch('/api/v1/timeline');
    const events = await resp.json();
    container.innerHTML = '';

    events.forEach(ev => {
      let badgeClass = 'bg-slate-500/20 text-slate-300 border-slate-500/30';
      if (ev.urgency_level === 'CRITICAL') badgeClass = 'bg-rose-500/20 text-rose-300 border-rose-500/40';
      else if (ev.urgency_level === 'HIGH') badgeClass = 'bg-amber-500/20 text-amber-300 border-amber-500/40';
      else if (ev.urgency_level === 'MEDIUM') badgeClass = 'bg-indigo-500/20 text-indigo-300 border-indigo-500/40';

      const card = document.createElement('div');
      card.className = 'glass-card p-4 rounded-2xl border border-white/10 flex flex-col sm:flex-row sm:items-center justify-between gap-3';
      card.innerHTML = `
        <div class="space-y-1">
          <div class="flex items-center gap-2">
            <span class="px-2 py-0.5 rounded-md border font-mono font-bold text-[10px] ${badgeClass}">${ev.timeframe.toUpperCase()}</span>
            <span class="text-xs font-bold text-white">${ev.doc_title}</span>
            <span class="text-[10px] text-slate-400">(${ev.section_header})</span>
          </div>
          <p class="text-xs text-slate-300">${ev.action_or_rule}</p>
        </div>
        <div class="text-right whitespace-nowrap">
          <span class="text-[10px] font-mono text-slate-400">Vault: <strong class="text-indigo-300">${ev.vault_id}</strong></span>
        </div>
      `;
      container.appendChild(card);
    });
  } catch (e) {
    container.innerHTML = '<p class="text-xs text-rose-400">Failed to load timelines.</p>';
  }
}

// ---------------- CRYPTOGRAPHIC AUDIT CERTIFICATE ----------------

async function downloadAuditCertificate() {
  const query = document.getElementById('query-input').value.trim();
  if (!query) return;

  try {
    const resp = await fetch(`/api/v1/audit/export?query=${encodeURIComponent(query)}&vault_id=${currentVaultId}`);
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

// ---------------- KNOWLEDGE GRAPH ----------------

async function renderKnowledgeGraph() {
  const canvas = document.getElementById('graph-canvas');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  canvas.width = canvas.parentElement.clientWidth;
  canvas.height = canvas.parentElement.clientHeight;

  try {
    const resp = await fetch(`/api/v1/graph?vault_id=${currentVaultId}`);
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
          ctx.strokeStyle = 'rgba(255, 255, 255, 0.12)';
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
        ctx.arc(n.x, n.y, n.size + 4, 0, Math.PI * 2);
        ctx.fillStyle = n.color + '33';
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

// ---------------- VAULT MANAGER CLIENT ----------------

async function loadVaultsGrid() {
  const container = document.getElementById('vaults-grid');
  container.innerHTML = '<p class="text-xs text-slate-400">Loading enterprise vaults...</p>';

  try {
    const resp = await fetch('/api/v1/vaults');
    const vaults = await resp.json();
    container.innerHTML = '';

    vaults.forEach(v => {
      const isActive = v.id === currentVaultId;
      const card = document.createElement('div');
      card.className = `glass-card p-5 rounded-2xl border transition-all cursor-pointer ${
        isActive ? 'border-indigo-500 bg-indigo-950/30 shadow-lg shadow-indigo-500/20' : 'border-white/10 hover:border-white/20'
      }`;
      card.onclick = () => {
        changeActiveVault(v.id);
        loadVaultsGrid();
      };

      card.innerHTML = `
        <div class="flex items-start justify-between">
          <div class="flex items-center gap-3">
            <span class="text-2xl p-2 rounded-xl bg-white/5 border border-white/10">${v.icon}</span>
            <div>
              <h4 class="font-bold text-sm text-white">${v.name}</h4>
              <p class="text-[10px] text-slate-400 font-mono">ID: ${v.id}</p>
            </div>
          </div>
          ${isActive ? '<span class="px-2 py-0.5 rounded-full bg-indigo-500/20 border border-indigo-500/50 text-indigo-300 text-[10px] font-bold">ACTIVE</span>' : ''}
        </div>
        <p class="text-xs text-slate-300 mt-3 line-clamp-2">${v.description}</p>
        <div class="pt-3 border-t border-white/10 mt-3 flex items-center justify-between text-xs text-slate-400">
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

async function handleVaultIngest(event) {
  event.preventDefault();
  const title = document.getElementById('ingest-title').value.trim();
  const content = document.getElementById('ingest-content').value.trim();
  if (!title || !content) return;

  const btn = document.getElementById('ingest-submit-btn');
  btn.disabled = true;
  btn.innerHTML = '<span>Ingesting & Updating Graph...</span>';

  try {
    const resp = await fetch('/api/v1/documents/ingest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
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

function highlightRetrievedChunk(chunkId) {
  const row = document.getElementById(`row-${chunkId}`);
  if (row) {
    row.scrollIntoView({ behavior: 'smooth', block: 'center' });
    row.classList.add('bg-indigo-950/90');
    setTimeout(() => row.classList.remove('bg-indigo-950/90'), 2500);
  }
}

// Initial Run
document.addEventListener('DOMContentLoaded', () => {
  executeEnterpriseQuery();
});
