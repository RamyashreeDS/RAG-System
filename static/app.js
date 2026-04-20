'use strict';

// ── State ─────────────────────────────────────────────────────────────────────
const state = {
  conversations: JSON.parse(localStorage.getItem('medigide_convs') || '[]'),
  currentId: null,
  isGenerating: false,
  darkMode: localStorage.getItem('medigide_dark') === 'true',
  mode: localStorage.getItem('medigide_mode') || 'discharge',
  samples: [],
  lastNote: '',   // stored discharge note for follow-up context
  lastQATopic: '', // stored last health Q&A topic
};

// ── DOM refs ──────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const welcomeDischarge = $('welcome-discharge');
const welcomeHealthqa  = $('welcome-healthqa');
const messages         = $('messages');
const noteInput        = $('note-input');
const sendBtn          = $('send-btn');
const fileInput        = $('file-input');
const historyList      = $('history-list');
const themeBtn         = $('theme-btn');
const themeIcon        = $('theme-icon');
const themeLabel       = $('theme-label');
const toastEl          = $('toast');
const chatArea         = $('chat-area');
const sampleGrid       = $('sample-grid');
const qaSampleGrid     = $('qa-sample-grid');
const sidebar          = $('sidebar');

// ── Init ──────────────────────────────────────────────────────────────────────
async function init() {
  applyTheme();
  applyMode(state.mode, false);
  renderHistory();
  await loadSamples();
  updateInputSuggestions();
  autoResizeTextarea();
  bindEvents();
}

// ── Theme ─────────────────────────────────────────────────────────────────────
function applyTheme() {
  document.body.classList.toggle('dark', state.darkMode);
  themeIcon.textContent  = state.darkMode ? '☀️' : '🌙';
  themeLabel.textContent = state.darkMode ? 'Light Mode' : 'Dark Mode';
}

function toggleTheme() {
  state.darkMode = !state.darkMode;
  localStorage.setItem('medigide_dark', state.darkMode);
  applyTheme();
}

// ── Mode (Discharge / Health Q&A) ─────────────────────────────────────────────
function applyMode(newMode, startNewChat = true) {
  state.mode = newMode;
  localStorage.setItem('medigide_mode', newMode);

  document.querySelectorAll('.mode-tab').forEach(t => {
    t.classList.toggle('active', t.dataset.mode === newMode);
  });

  const isDischarge = newMode === 'discharge';
  noteInput.placeholder = isDischarge
    ? 'Paste your discharge note here… or click a sample above'
    : 'Ask a health question… e.g. "What should I do for a sore throat?"';

  const uploadLbl = $('upload-btn-label');
  if (uploadLbl) uploadLbl.style.display = isDischarge ? '' : 'none';

  updateInputSuggestions();
  if (startNewChat) newChat();
}

// ── Toast ─────────────────────────────────────────────────────────────────────
let toastTimer;
function showToast(msg, duration = 2200) {
  clearTimeout(toastTimer);
  toastEl.textContent = msg;
  toastEl.classList.add('show');
  toastTimer = setTimeout(() => toastEl.classList.remove('show'), duration);
}

// ── Samples ───────────────────────────────────────────────────────────────────
const QA_SAMPLES = [
  { icon: '🤧', title: 'Cold & Flu', subtitle: 'Sore throat, runny nose', text: 'I have a sore throat, stuffy nose, and mild fever. What can I do at home to feel better, and when should I see a doctor?' },
  { icon: '🤕', title: 'Headache', subtitle: 'Head pain & causes', text: 'I have had a persistent headache for two days. What could be causing it and what can I do to relieve it at home?' },
  { icon: '🤢', title: 'Upset Stomach', subtitle: 'Nausea & digestion', text: 'I have an upset stomach with nausea and loose stools. What home remedies can help, and when is it serious?' },
  { icon: '💪', title: 'Back Pain', subtitle: 'Muscle & joint aches', text: 'My lower back hurts after lifting heavy things yesterday. What can I do to relieve the pain at home?' },
];

async function loadSamples() {
  try {
    const res = await fetch('/api/samples');
    state.samples = await res.json();
  } catch {
    state.samples = [];
  }
  renderSamples();
  renderQASamples();
}

function renderSamples() {
  if (!state.samples.length) {
    sampleGrid.innerHTML = '<div class="history-empty">No sample notes found.</div>';
    return;
  }
  sampleGrid.innerHTML = state.samples.map((s, i) => `
    <div class="sample-card" data-idx="${i}">
      <div class="sample-card-icon">${s.icon}</div>
      <div class="sample-card-title">${escHtml(s.title)}</div>
      <div class="sample-card-sub">${escHtml(s.subtitle)}</div>
    </div>
  `).join('');
  sampleGrid.querySelectorAll('.sample-card').forEach(card => {
    card.addEventListener('click', () => {
      const s = state.samples[+card.dataset.idx];
      if (s) { noteInput.value = s.text; autoResizeTextarea(); noteInput.focus(); }
    });
  });
}

function renderQASamples() {
  qaSampleGrid.innerHTML = QA_SAMPLES.map((s, i) => `
    <div class="sample-card" data-qa-idx="${i}">
      <div class="sample-card-icon">${s.icon}</div>
      <div class="sample-card-title">${escHtml(s.title)}</div>
      <div class="sample-card-sub">${escHtml(s.subtitle)}</div>
    </div>
  `).join('');
  qaSampleGrid.querySelectorAll('.sample-card').forEach(card => {
    card.addEventListener('click', () => {
      const s = QA_SAMPLES[+card.dataset.qaIdx];
      if (s) { noteInput.value = s.text; autoResizeTextarea(); noteInput.focus(); }
    });
  });
}

// ── SSE parser ────────────────────────────────────────────────────────────────
function parseSSE(buffer) {
  const events = [];
  let remaining = buffer;
  while (remaining.includes('\n\n')) {
    const end = remaining.indexOf('\n\n');
    const block = remaining.slice(0, end).trim();
    remaining = remaining.slice(end + 2);
    if (!block) continue;
    let event = 'message', dataStr = '';
    for (const line of block.split('\n')) {
      if (line.startsWith('event: '))     event = line.slice(7).trim();
      else if (line.startsWith('data: ')) dataStr = line.slice(6);
    }
    if (dataStr) {
      try { events.push({ event, data: JSON.parse(dataStr) }); } catch {}
    }
  }
  return { events, remaining };
}

// ── Section definitions ───────────────────────────────────────────────────────
const DISCHARGE_SECTIONS = [
  { key: 'diag', icon: '🔍', label: 'Diagnosis Explained', cls: 'section-card-diag', delay: 0 },
  { key: 'med',  icon: '💊', label: 'Your Medications',    cls: 'section-card-med',  delay: 1 },
  { key: 'fol',  icon: '📅', label: 'Follow-up Actions',   cls: 'section-card-fol',  delay: 2 },
  { key: 'warn', icon: '⚠️', label: 'Warning Signs',       cls: 'section-card-warn', delay: 3 },
];

const HEALTHQA_SECTIONS = [
  { key: 'what', icon: '🤔', label: 'What This Could Be',   cls: 'section-card-diag', delay: 0 },
  { key: 'home', icon: '🏠', label: 'Home Care Tips',        cls: 'section-card-med',  delay: 1 },
  { key: 'doc',  icon: '🩺', label: 'When to See a Doctor',  cls: 'section-card-fol',  delay: 2 },
  { key: 'er',   icon: '🚨', label: 'Go to the ER If',       cls: 'section-card-warn', delay: 3 },
];

function parseSections(text, sectionDefs) {
  const defs = sectionDefs || (state.mode === 'healthqa' ? HEALTHQA_SECTIONS : DISCHARGE_SECTIONS);
  const lines = text.split('\n');
  const result = [];
  let currentSection = null;
  const contentBuf = [];

  for (const line of lines) {
    if (line.startsWith('## ') || line.startsWith('# ')) {
      if (currentSection) {
        const content = contentBuf.join('\n').trim();
        if (content) result.push({ ...currentSection, content });
        contentBuf.length = 0;
      }
      currentSection = defs.find(s => line.includes(s.label)) || null;
    } else if (currentSection) {
      contentBuf.push(line);
    }
  }
  if (currentSection) {
    const content = contentBuf.join('\n').trim();
    if (content) result.push({ ...currentSection, content });
  }
  return result.length >= 2 ? result : null;
}

function formatContent(text) {
  const lines = text.split('\n').map(l => l.trim()).filter(Boolean);
  let html = '';
  let inList = false;
  for (const line of lines) {
    const isBullet = /^[•\-\*]\s/.test(line);
    const isNum    = /^\d+\.\s/.test(line);
    if (isBullet || isNum) {
      if (!inList) { html += '<ul>'; inList = true; }
      const content = line.replace(/^[•\-\*\d\.]+\s+/, '');
      html += `<li>${md(content)}</li>`;
    } else {
      if (inList) { html += '</ul>'; inList = false; }
      html += `<p>${md(line)}</p>`;
    }
  }
  if (inList) html += '</ul>';
  return html;
}

function md(text) {
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>');
}

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ── Render helpers ────────────────────────────────────────────────────────────
function renderSectionCard(sec, idx) {
  return `
    <div class="section-card ${sec.cls}" style="animation-delay:${idx * 60}ms">
      <div class="section-header">
        <div class="section-header-left">
          <span class="section-header-icon">${sec.icon}</span>
          <span>${sec.label}</span>
        </div>
        <span class="section-chevron">▼</span>
      </div>
      <div class="section-body">${formatContent(sec.content)}</div>
    </div>
  `;
}

function renderSourceBadge(source) {
  const cls = 'source-badge-' + source.replace(/ /g, '_');
  const short = {
    medlineplus: 'MedlinePlus', openfda: 'FDA', pubmed: 'PubMed',
    plaba: 'PLABA', mimic_notes: 'MIMIC', mimic_iv_demo: 'MIMIC Demo',
  }[source] || source;
  return `<span class="source-badge ${cls}">${escHtml(short)}</span>`;
}

function renderSources(retrieved) {
  if (!retrieved) return { html: '', count: 0 };
  const sectionNames = {
    diagnosis: '🔍 Diagnosis', medications: '💊 Medications',
    follow_up: '📅 Follow-up', warning_signs: '⚠️ Warning Signs',
  };
  let totalCount = 0;
  let html = `<div class="sources-panel-header">📚 Evidence Retrieved from Medical Databases</div>`;
  for (const [sec, items] of Object.entries(retrieved)) {
    if (!items || !items.length) continue;
    const label = sectionNames[sec] || sec.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    html += `<div class="sources-section"><div class="sources-section-title">${label}</div>`;
    for (const item of items) {
      totalCount++;
      html += `
        <div class="source-item">
          <div class="source-item-top">
            ${renderSourceBadge(item.source)}
            <span class="source-title">${escHtml(item.title || 'No title')}</span>
          </div>
          <div class="source-text">${escHtml(item.text)}</div>
          <div class="source-scores">
            <span class="score-chip">BM25: ${item.bm25}</span>
            <span class="score-chip">Dense: ${item.dense}</span>
            <span class="score-chip">Fused: ${item.fused}</span>
          </div>
        </div>`;
    }
    html += '</div>';
  }
  return { html, count: totalCount };
}

// ── Message creation ──────────────────────────────────────────────────────────
function addUserMessage(text) {
  hideWelcome();
  const tpl   = document.getElementById('msg-user-tpl');
  const clone = tpl.content.cloneNode(true);
  const preview = clone.querySelector('.msg-note-preview');
  const display = text.length > 600 ? text.slice(0, 600) + '\n\n[… continues …]' : text;
  preview.textContent = display;
  messages.appendChild(clone);
  scrollBottom();
}

function createAiMessage() {
  const tpl   = document.getElementById('msg-ai-tpl');
  const clone = tpl.content.cloneNode(true);
  const el    = clone.querySelector('.message-ai');
  messages.appendChild(clone);
  scrollBottom();
  return el;
}

function getStatusBar(el)    { return el.querySelector('.msg-status-bar'); }
function getStepsEl(el)      { return el.querySelector('.status-steps'); }
function getStreamEl(el)     { return el.querySelector('.msg-stream'); }
function getSectionsEl(el)   { return el.querySelector('.msg-sections'); }
function getFooterEl(el)     { return el.querySelector('.msg-footer'); }
function getSourcesPanel(el) { return el.querySelector('.sources-panel'); }

const DISCHARGE_STEPS = [
  '📋 Reading your discharge note…',
  '🔍 Searching medical knowledge base…',
  '✍️  Preparing your explanation…',
];
const HEALTHQA_STEPS = [
  '🔍 Searching medical knowledge base…',
  '✍️  Preparing your answer…',
];

function updateStatus(el, text, step) {
  const stepsEl = getStepsEl(el);
  const labels  = state.mode === 'healthqa' ? HEALTHQA_STEPS : DISCHARGE_STEPS;
  while (stepsEl.children.length < labels.length) {
    const idx = stepsEl.children.length;
    const div = document.createElement('div');
    div.className = 'status-step';
    div.innerHTML = `<div class="step-dot"></div><span>${labels[idx] || ''}</span>`;
    stepsEl.appendChild(div);
  }
  const stepEls = stepsEl.querySelectorAll('.status-step');
  stepEls.forEach((s, i) => {
    s.classList.remove('done', 'active');
    if (i < step - 1)       { s.classList.add('done');   s.querySelector('.step-dot').textContent = '✓'; }
    else if (i === step - 1) { s.classList.add('active'); s.querySelector('.step-dot').textContent = ''; }
  });
  scrollBottom();
}

function startStream(el) {
  getStatusBar(el).classList.add('hidden');
  const streamEl = getStreamEl(el);
  streamEl.classList.add('visible');
  streamEl.innerHTML = '<span class="typing-cursor"></span>';
  scrollBottom();
}

function appendToken(el, text) {
  const streamEl = getStreamEl(el);
  const cursor = streamEl.querySelector('.typing-cursor');
  if (cursor) cursor.insertAdjacentText('beforebegin', text);
  else        streamEl.insertAdjacentText('beforeend', text);
  scrollBottom();
}

function finalizeMessage(el, fullText, retrieved, doneData, sectionDefs) {
  getStreamEl(el).style.display = 'none';

  const sectionsEl = getSectionsEl(el);
  const sections   = parseSections(fullText, sectionDefs);

  if (sections && sections.length) {
    sectionsEl.innerHTML = sections.map((s, i) => renderSectionCard(s, i)).join('');
    sectionsEl.style.display = 'flex';
    sectionsEl.querySelectorAll('.section-header').forEach(hdr => {
      hdr.addEventListener('click', () => hdr.closest('.section-card').classList.toggle('collapsed'));
    });
  } else {
    sectionsEl.innerHTML = `<div class="msg-stream visible markdown-body" style="display:block; padding: 16px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.08); background: var(--bg-alt);">${formatContent(fullText)}</div>`;
    sectionsEl.style.display = 'block';
  }

  const sourcesPanelEl = getSourcesPanel(el);
  if (retrieved) {
    const { html, count } = renderSources(retrieved);
    sourcesPanelEl.innerHTML = html;

    const footerEl = getFooterEl(el);
    footerEl.style.display = 'flex';

    footerEl.querySelector('.copy-btn').addEventListener('click', () => {
      navigator.clipboard.writeText(fullText).then(() => showToast('✓ Copied to clipboard'));
      footerEl.querySelector('.copy-btn').classList.add('copied');
      setTimeout(() => footerEl.querySelector('.copy-btn').classList.remove('copied'), 1800);
    });

    const srcBtn = footerEl.querySelector('.sources-toggle');
    srcBtn.querySelector('.sources-count').textContent = count;
    srcBtn.addEventListener('click', () => {
      const visible = sourcesPanelEl.style.display !== 'none';
      sourcesPanelEl.style.display = visible ? 'none' : 'block';
      srcBtn.classList.toggle('copied', !visible);
    });

    const diags = (doneData.diagnoses || []).slice(0, 3);
    if (diags.length) {
      footerEl.querySelector('.msg-meta').textContent = `Conditions: ${diags.join(', ')}`;
    }
  }
  scrollBottom();
}

function showError(el, msg) {
  getStatusBar(el).classList.add('hidden');
  getStreamEl(el).style.display = 'none';
  const sectionsEl = getSectionsEl(el);
  sectionsEl.innerHTML = `<div class="msg-error">⚠️ ${escHtml(msg || 'Something went wrong. Please try again.')}</div>`;
  sectionsEl.style.display = 'block';
  scrollBottom();
}

// ── Recommendations — Discharge mode ─────────────────────────────────────────
// Stays in Discharge mode. Follow-ups about the patient's own note.
const DISCHARGE_RECS = {
  'heart failure': [
    'Why do I need to weigh myself every day with heart failure?',
    'What foods and drinks should I limit with heart failure?',
    'What are signs that my heart failure is getting worse?',
  ],
  'hypertension': [
    'Can I stop my blood pressure medicine once my numbers are normal?',
    'What lifestyle changes can lower my blood pressure naturally?',
    'What blood pressure numbers should I aim for?',
  ],
  'diabetes': [
    'What foods are best for controlling my blood sugar?',
    'What are the early signs of low blood sugar I should watch for?',
    'How often should I check my blood sugar at home?',
  ],
  'coronary artery disease': [
    'What activities are safe for me after a heart procedure?',
    'What are the warning signs of a heart attack I should never ignore?',
    'How can I lower my cholesterol through diet?',
  ],
  'atrial fibrillation': [
    'What does an irregular heartbeat feel like and is it dangerous?',
    'What foods should I avoid while taking blood thinners?',
    'Is it safe to exercise with atrial fibrillation?',
  ],
  'pneumonia': [
    'How long will it take me to fully recover from pneumonia?',
    'What foods and fluids help my lungs heal?',
    'What breathing symptoms should send me back to the ER?',
  ],
  'chronic kidney disease': [
    'What foods are hardest on my kidneys?',
    'How much water should I drink daily with kidney disease?',
    'What symptoms mean my kidney function is getting worse?',
  ],
  'copd': [
    'What breathing exercises can help me manage COPD at home?',
    'What triggers a COPD flare-up that I should avoid?',
    'How do I know when a COPD episode needs emergency care?',
  ],
};

function generateDischargeRecs(diagnoses) {
  const recs = [];
  const seen = new Set();
  for (const diag of (diagnoses || [])) {
    for (const [cond, questions] of Object.entries(DISCHARGE_RECS)) {
      if (diag.toLowerCase().includes(cond)) {
        for (const q of questions.slice(0, 2)) {
          if (!seen.has(q)) { seen.add(q); recs.push(q); }
        }
      }
    }
    if (recs.length >= 4) break;
  }
  if (!recs.length) {
    recs.push(
      'What should I do in the first 24 hours after leaving the hospital?',
      'Are there activities I should avoid at home during recovery?',
      'What should I bring to my follow-up appointment?'
    );
  }
  return recs.slice(0, 4);
}

// ── Recommendations — Health Q&A mode ────────────────────────────────────────
// Stays in Health Q&A mode. Follow-up health questions on the same topic.
const HEALTHQA_RECS = {
  'sore throat': [
    'How long does a sore throat normally last before I should worry?',
    'What home remedies are most effective for soothing a sore throat?',
    'How do I know if my sore throat needs antibiotics?',
  ],
  'headache': [
    'What is the difference between a tension headache and a migraine?',
    'What is the best over-the-counter medicine for a bad headache?',
    'When should a headache make me go to the ER immediately?',
  ],
  'fever': [
    'What is a dangerously high fever temperature for an adult?',
    'Should I try to bring a fever down or let it run its course?',
    'What home remedies bring down a fever safely?',
  ],
  'stomach': [
    'What foods are safe to eat with an upset stomach?',
    'How long should diarrhea or vomiting last before I see a doctor?',
    'What signs mean a stomach ache is something more serious?',
  ],
  'back pain': [
    'What is the fastest way to relieve lower back pain at home?',
    'Should I rest in bed or stay active when my back hurts?',
    'What signs suggest my back pain might be something serious?',
  ],
  'cough': [
    'When does a cough mean I should see a doctor right away?',
    'What home remedies help stop a persistent cough?',
    'What is the difference between a dry cough and a wet cough?',
  ],
  'cold': [
    'What is the quickest way to recover from a cold?',
    'Which over-the-counter cold medicines actually work?',
    'How do I stop spreading my cold to the people around me?',
  ],
  'flu': [
    'How do I tell the difference between the flu and a cold?',
    'When should I see a doctor for the flu instead of treating it at home?',
    'What can I do to recover from the flu faster?',
  ],
  'blood pressure': [
    'What is a normal blood pressure reading for my age?',
    'Can stress and anxiety cause a temporary spike in blood pressure?',
    'What happens if blood pressure stays too high for too long?',
  ],
  'blood sugar': [
    'What is a normal blood sugar level for someone without diabetes?',
    'What should I eat to keep my blood sugar stable throughout the day?',
    'What are the warning signs of dangerously low blood sugar?',
  ],
  'chest pain': [
    'How do I tell if chest pain is coming from my heart?',
    'Can anxiety and stress cause chest pain?',
    'What should I do if I feel sudden chest tightness or pressure?',
  ],
  'dizziness': [
    'What are the most common causes of sudden dizziness?',
    'What helps when you feel dizzy or lightheaded?',
    'When is dizziness a sign of something serious?',
  ],
  'rash': [
    'How do I tell if a skin rash needs a doctor?',
    'What home treatments help with an itchy rash?',
    'What rashes are contagious and what precautions should I take?',
  ],
  'sleep': [
    'What are the best tips for improving sleep quality?',
    'How many hours of sleep do adults actually need?',
    'When does difficulty sleeping become a medical problem?',
  ],
};

function generateHealthQARecs(question) {
  const q = question.toLowerCase();
  const recs = [];
  const seen = new Set();
  for (const [keyword, questions] of Object.entries(HEALTHQA_RECS)) {
    if (q.includes(keyword)) {
      for (const r of questions.slice(0, 2)) {
        if (!seen.has(r)) { seen.add(r); recs.push(r); }
      }
    }
    if (recs.length >= 4) break;
  }
  if (!recs.length) {
    recs.push(
      'How do I know when my symptoms are serious enough to see a doctor?',
      'What home care steps help with most common illnesses?',
      'When should I call my doctor versus going straight to the ER?'
    );
  }
  return recs.slice(0, 4);
}

// ── Shared recommendation renderer ─────────────────────────────────────────────
// Never switches mode — recommendations stay in the current mode's context.
function renderRecBar(recs, label) {
  if (!recs.length) return;
  const bar = document.createElement('div');
  bar.className = 'recommendations-bar';
  bar.innerHTML = `
    <div class="recs-label">${label}</div>
    <div class="recs-chips">
      ${recs.map(r => `<button class="rec-chip">${escHtml(r)}</button>`).join('')}
    </div>
  `;
  messages.appendChild(bar);

  bar.querySelectorAll('.rec-chip').forEach((btn, i) => {
    btn.addEventListener('click', () => {
      // Fill textarea only — never switches mode
      noteInput.value = recs[i];
      autoResizeTextarea();
      hideSpellBar();
      // Update contextual suggestions in input area
      updateInputSuggestionsFromText(recs[i]);
      noteInput.focus();
      noteInput.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    });
  });
  scrollBottom();
}

function addDischargeRecs(diagnoses) {
  const recs = generateDischargeRecs(diagnoses);
  renderRecBar(recs, '💡 Follow-up questions about your discharge note:');
}

function addHealthQARecs(question) {
  const recs = generateHealthQARecs(question);
  renderRecBar(recs, '💡 Related questions you might want to ask:');
}

// ── Input suggestion chips ────────────────────────────────────────────────────
// Contextual question starters shown above the input box.
const MODE_SUGGESTIONS = {
  discharge: [
    { label: '📋 Explain my diagnosis',     value: 'Can you explain my diagnosis in simple terms?' },
    { label: '💊 About my medications',     value: 'What do my discharge medications do and how should I take them?' },
    { label: '📅 My next steps',            value: 'What are the most important steps after leaving the hospital?' },
    { label: '⚠️ Warning symptoms',         value: 'What symptoms should make me call my doctor right away?' },
  ],
  healthqa: [
    { label: '🤧 Cold & flu tips',          value: 'I have cold and flu symptoms — what can I do at home to feel better?' },
    { label: '🤕 Headache relief',          value: 'I have a persistent headache — what could be causing it and how can I treat it?' },
    { label: '🤢 Stomach problems',         value: 'I have an upset stomach with nausea — what home remedies can help?' },
    { label: '🩺 When to see a doctor',     value: 'How do I know when my symptoms are serious enough to see a doctor?' },
  ],
};

function updateInputSuggestions(customChips) {
  const el = $('input-suggestions');
  if (!el) return;

  const chips = customChips || MODE_SUGGESTIONS[state.mode] || [];
  if (!chips.length) { el.innerHTML = ''; return; }

  el.innerHTML = chips.map(c =>
    `<button class="suggest-chip" title="${escHtml(c.value)}">${escHtml(c.label)}</button>`
  ).join('');

  el.querySelectorAll('.suggest-chip').forEach((chip, i) => {
    chip.addEventListener('click', () => {
      noteInput.value = chips[i].value;
      autoResizeTextarea();
      hideSpellBar();
      noteInput.focus();
    });
  });
}

// Update suggestions while typing — matches keyword topics
function updateInputSuggestionsFromText(text) {
  if (!text || text.length < 3) { updateInputSuggestions(); return; }
  const q = text.toLowerCase();

  if (state.mode === 'healthqa') {
    for (const [keyword, questions] of Object.entries(HEALTHQA_RECS)) {
      if (q.includes(keyword)) {
        const chips = questions.slice(0, 4).map(v => ({ label: v, value: v }));
        updateInputSuggestions(chips);
        return;
      }
    }
  } else {
    for (const [keyword, questions] of Object.entries(DISCHARGE_RECS)) {
      if (q.includes(keyword)) {
        const chips = questions.slice(0, 4).map(v => ({ label: v, value: v }));
        updateInputSuggestions(chips);
        return;
      }
    }
  }
  updateInputSuggestions();
}

// ── Spell correction ──────────────────────────────────────────────────────────
const MEDICAL_CORRECTIONS = {
  'diabeties':      'diabetes',
  'diaetes':        'diabetes',
  'diabtes':        'diabetes',
  'diabetis':       'diabetes',
  'hypertenshion':  'hypertension',
  'hipertension':   'hypertension',
  'hypertenison':   'hypertension',
  'colestrol':      'cholesterol',
  'cholesteral':    'cholesterol',
  'kolesterol':     'cholesterol',
  'asthama':        'asthma',
  'astma':          'asthma',
  'pnemonia':       'pneumonia',
  'neumonia':       'pneumonia',
  'pnuemonia':      'pneumonia',
  'symtoms':        'symptoms',
  'symptons':       'symptoms',
  'symtpoms':       'symptoms',
  'inflamation':    'inflammation',
  'infammation':    'inflammation',
  'presure':        'pressure',
  'medicin':        'medicine',
  'medecine':       'medicine',
  'medicene':       'medicine',
  'prescripton':    'prescription',
  'prescripion':    'prescription',
  'diarrea':        'diarrhea',
  'diarrhoea':      'diarrhea',
  'nausous':        'nauseous',
  'nausaeous':      'nauseous',
  'deprresion':     'depression',
  'depresion':      'depression',
  'anxeity':        'anxiety',
  'anxiaty':        'anxiety',
  'antibiotecs':    'antibiotics',
  'antibotics':     'antibiotics',
  'alergic':        'allergic',
  'alergy':         'allergy',
  'allergie':       'allergy',
  'headach':        'headache',
  'stomache':       'stomach',
  'kidnee':         'kidney',
  'kidny':          'kidney',
  'feavor':         'fever',
  'feaver':         'fever',
  'hart':           'heart',
  'vomitting':      'vomiting',
  'brething':       'breathing',
  'breathng':       'breathing',
  'sweling':        'swelling',
  'swelling':       'swelling',
  'tiredness':      'tiredness',
  'fatiqued':       'fatigued',
  'fatigue':        'fatigue',
  'diziness':       'dizziness',
  'dizzines':       'dizziness',
  'blured':         'blurred',
};

let spellTimer = null;
let _spellWrong = '';
let _spellCorrect = '';

function checkSpelling() {
  clearTimeout(spellTimer);
  spellTimer = setTimeout(() => {
    const text = noteInput.value;
    const words = text.toLowerCase().split(/[\s\n,.!?;:'"()\-]+/);
    for (const raw of words) {
      const word = raw.replace(/[^a-z]/g, '');
      if (word.length < 4) continue;
      if (MEDICAL_CORRECTIONS[word]) {
        showSpellBar(word, MEDICAL_CORRECTIONS[word]);
        return;
      }
    }
    hideSpellBar();
  }, 900);
}

function showSpellBar(wrong, correct) {
  const bar = $('spell-bar');
  if (!bar) return;
  _spellWrong = wrong;
  _spellCorrect = correct;
  bar.innerHTML = `
    <span class="spell-msg">🔤 Did you mean <strong>${escHtml(correct)}</strong>?</span>
    <button class="spell-fix-btn">Fix it</button>
    <button class="spell-dismiss-btn" title="Dismiss">×</button>
  `;
  bar.style.display = 'flex';

  bar.querySelector('.spell-fix-btn').addEventListener('click', () => {
    const regex = new RegExp(`\\b${_spellWrong}\\b`, 'gi');
    noteInput.value = noteInput.value.replace(regex, _spellCorrect);
    hideSpellBar();
    noteInput.focus();
  });
  bar.querySelector('.spell-dismiss-btn').addEventListener('click', hideSpellBar);
}

function hideSpellBar() {
  const bar = $('spell-bar');
  if (bar) bar.style.display = 'none';
}

// ── Load a saved conversation ─────────────────────────────────────────────────
function loadConversation(conv) {
  if (state.isGenerating) return;
  messages.innerHTML = '';
  hideWelcome();
  state.currentId = conv.id;

  const convMode = conv.mode || 'discharge';
  state.mode = convMode;
  localStorage.setItem('medigide_mode', convMode);
  document.querySelectorAll('.mode-tab').forEach(t => {
    t.classList.toggle('active', t.dataset.mode === convMode);
  });
  noteInput.placeholder = convMode === 'discharge'
    ? 'Paste your discharge note here… or click a sample above'
    : 'Ask a health question… e.g. "What should I do for a sore throat?"';
  const uploadLbl = $('upload-btn-label');
  if (uploadLbl) uploadLbl.style.display = convMode === 'discharge' ? '' : 'none';

  // Restore last note for context
  if (convMode === 'discharge' && conv.note) state.lastNote = conv.note;
  if (convMode === 'healthqa' && conv.question) state.lastQATopic = conv.question;

  const inputText = conv.note || conv.question || '';
  addUserMessage(inputText);
  const aiEl = createAiMessage();
  getStatusBar(aiEl).classList.add('hidden');

  if (conv.response) {
    const sectionDefs = convMode === 'healthqa' ? HEALTHQA_SECTIONS : DISCHARGE_SECTIONS;
    finalizeMessage(aiEl, conv.response, conv.retrieved || null, conv.doneData || {}, sectionDefs);
    if (convMode === 'discharge' && conv.doneData?.diagnoses?.length) {
      addDischargeRecs(conv.doneData.diagnoses);
    } else if (convMode === 'healthqa') {
      addHealthQARecs(conv.question || conv.title || '');
    }
  } else {
    showError(aiEl, 'Response not saved. Please send the note again to regenerate.');
  }

  updateInputSuggestions();
  renderHistory();
  closeSidebar();
}

// ── Main send action ──────────────────────────────────────────────────────────
async function sendNote() {
  const text = noteInput.value.trim();
  if (!text || state.isGenerating) return;

  state.isGenerating = true;
  setInputDisabled(true);
  hideSpellBar();
  noteInput.value = '';
  autoResizeTextarea();

  const convId   = Date.now().toString();
  const isDischarge = state.mode === 'discharge';
  state.currentId = convId;

  // For discharge: if the input is a short follow-up (< 300 chars) and we have a previous note,
  // inject the note as context so the RAG retrieval is relevant.
  const isFollowUp = isDischarge && text.length < 300 && state.lastNote.length > 50;
  const apiText = isFollowUp
    ? `${state.lastNote.slice(0, 2000)}\n\n--- Follow-up question: ${text}`
    : text;

  // Update stored context
  if (isDischarge && !isFollowUp) state.lastNote = text.slice(0, 5000);
  if (!isDischarge) state.lastQATopic = text;

  const conv = {
    id:       convId,
    mode:     state.mode,
    title:    text.slice(0, 80),
    ts:       Date.now(),
    note:     isDischarge ? (isFollowUp ? state.lastNote : text).slice(0, 5000) : '',
    question: isDischarge ? '' : text,
    response: null,
    retrieved: null,
    doneData:  null,
  };
  state.conversations.unshift(conv);
  if (state.conversations.length > 40) state.conversations.pop();
  saveConversations();
  renderHistory();

  addUserMessage(text);
  const aiEl = createAiMessage();
  updateStatus(aiEl, '', 1);

  let fullText = '';
  let retrieved = null;
  let streamStarted = false;
  const sectionDefs = isDischarge ? DISCHARGE_SECTIONS : HEALTHQA_SECTIONS;
  const endpoint = isDischarge ? '/api/explain' : '/api/healthqa';
  const body = isDischarge
    ? JSON.stringify({ note_text: apiText, use_ollama: true })
    : JSON.stringify({ question: text, use_ollama: true });

  try {
    const resp = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
    });

    if (!resp.ok) throw new Error(`Server error: ${resp.status}`);

    const reader  = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const { events, remaining } = parseSSE(buffer);
      buffer = remaining;

      for (const { event, data } of events) {
        switch (event) {
          case 'status':
            if (!streamStarted) updateStatus(aiEl, data.text, data.step || 1);
            break;
          case 'sources':
            retrieved = data;
            break;
          case 'token':
            if (!streamStarted) { startStream(aiEl); streamStarted = true; }
            fullText += data.text;
            appendToken(aiEl, data.text);
            break;
          case 'done': {
            finalizeMessage(aiEl, fullText, retrieved, data, sectionDefs);
            // Persist full response
            const c = state.conversations.find(x => x.id === convId);
            if (c) { c.response = fullText; c.retrieved = retrieved; c.doneData = data; saveConversations(); }
            // Mode-specific recommendations — each stays in its own mode
            if (isDischarge && data.diagnoses?.length) {
              addDischargeRecs(data.diagnoses);
            } else if (!isDischarge) {
              addHealthQARecs(text);
            }
            // Reset suggestions to mode defaults after response
            updateInputSuggestions();
            break;
          }
          case 'error':
            showError(aiEl, data.text);
            break;
        }
      }
    }

    if (streamStarted && fullText && getSectionsEl(aiEl).style.display === 'none') {
      finalizeMessage(aiEl, fullText, retrieved, {}, sectionDefs);
    }
  } catch (err) {
    showError(aiEl, err.message);
  } finally {
    state.isGenerating = false;
    setInputDisabled(false);
    noteInput.focus();
  }
}

// ── Conversation history ──────────────────────────────────────────────────────
function saveConversations() {
  localStorage.setItem('medigide_convs', JSON.stringify(state.conversations));
}

function renderHistory() {
  if (!state.conversations.length) {
    historyList.innerHTML = '<div class="history-empty">Your conversations will appear here</div>';
    return;
  }

  const now = Date.now();
  const DAY = 86400000;
  const groups = { Today: [], Yesterday: [], 'Last 7 days': [], Older: [] };

  for (const conv of state.conversations) {
    const age = now - conv.ts;
    if      (age < DAY)   groups.Today.push(conv);
    else if (age < 2*DAY) groups.Yesterday.push(conv);
    else if (age < 7*DAY) groups['Last 7 days'].push(conv);
    else                  groups.Older.push(conv);
  }

  const modeIcon = { discharge: '📋', healthqa: '🩺' };
  let html = '';
  for (const [label, items] of Object.entries(groups)) {
    if (!items.length) continue;
    html += `<div class="history-group-label">${label}</div>`;
    for (const conv of items) {
      const active = conv.id === state.currentId ? ' active' : '';
      const icon = modeIcon[conv.mode || 'discharge'] || '💬';
      html += `
        <div class="history-item${active}" data-id="${conv.id}">
          <span class="history-item-icon">${icon}</span>
          <span class="history-item-text">${escHtml(conv.title)}</span>
          <span class="history-item-time">${formatTime(conv.ts)}</span>
        </div>`;
    }
  }
  historyList.innerHTML = html;

  historyList.querySelectorAll('.history-item').forEach(item => {
    item.addEventListener('click', () => {
      const conv = state.conversations.find(c => c.id === item.dataset.id);
      if (conv) loadConversation(conv);
    });
  });
}

function formatTime(ts) {
  const d = new Date(ts);
  const now = new Date();
  if (d.toDateString() === now.toDateString()) {
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

// ── New chat ──────────────────────────────────────────────────────────────────
function newChat() {
  if (state.isGenerating) return;
  state.currentId = null;
  messages.innerHTML = '';
  hideWelcome();
  showWelcome();
  noteInput.value = '';
  autoResizeTextarea();
  hideSpellBar();
  updateInputSuggestions();
  noteInput.focus();
  closeSidebar();
  renderHistory();
}

function hideWelcome() {
  welcomeDischarge.style.display = 'none';
  welcomeHealthqa.style.display  = 'none';
}

function showWelcome() {
  if (state.mode === 'healthqa') {
    welcomeHealthqa.style.display  = '';
    welcomeDischarge.style.display = 'none';
  } else {
    welcomeDischarge.style.display = '';
    welcomeHealthqa.style.display  = 'none';
  }
}

// ── Textarea auto-resize ──────────────────────────────────────────────────────
function autoResizeTextarea() {
  noteInput.style.height = 'auto';
  noteInput.style.height = Math.min(noteInput.scrollHeight, 280) + 'px';
}

// ── Input state ───────────────────────────────────────────────────────────────
function setInputDisabled(disabled) {
  sendBtn.disabled   = disabled;
  noteInput.disabled = disabled;
  const inputBox = $('input-box');
  inputBox.classList.toggle('disabled', disabled);
  if (disabled) {
    sendBtn.innerHTML = '<span class="typing-cursor" style="background:#fff;animation:blink .7s step-end infinite"></span> Thinking…';
  } else {
    sendBtn.innerHTML = 'Send <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>';
  }
}

// ── Scroll ────────────────────────────────────────────────────────────────────
function scrollBottom() {
  requestAnimationFrame(() => { chatArea.scrollTop = chatArea.scrollHeight; });
}

// ── Mobile sidebar ────────────────────────────────────────────────────────────
function openSidebar()  { sidebar.classList.add('open');    overlay.classList.add('show'); }
function closeSidebar() { sidebar.classList.remove('open'); overlay.classList.remove('show'); }

const overlay = document.createElement('div');
overlay.className = 'sidebar-overlay';
overlay.addEventListener('click', closeSidebar);
document.body.appendChild(overlay);

// ── File upload ───────────────────────────────────────────────────────────────
const ACCEPTED_EXTS = new Set(['.txt','.pdf','.docx','.png','.jpg','.jpeg','.bmp','.tiff','.tif','.webp','.gif']);

function fileExt(name) { return name.slice(name.lastIndexOf('.')).toLowerCase(); }

async function handleFileUpload(file) {
  if (!file) return;

  const ext = fileExt(file.name);
  if (!ACCEPTED_EXTS.has(ext)) {
    showToast(`⚠️ Unsupported file type "${ext}". Use PDF, DOCX, TXT, or an image.`, 4000);
    return;
  }

  const uploadBtn = document.querySelector('.upload-btn');
  const origHTML  = uploadBtn.innerHTML;
  uploadBtn.innerHTML = '<span class="typing-cursor" style="background:var(--blue)"></span> Reading…';
  uploadBtn.style.pointerEvents = 'none';

  const form = new FormData();
  form.append('file', file);

  try {
    const res  = await fetch('/api/upload', { method: 'POST', body: form });
    const data = await res.json();
    if (!res.ok) { showToast(`⚠️ ${data.detail || 'Could not read file.'}`, 5000); return; }
    noteInput.value = data.text;
    autoResizeTextarea();
    const kb = (file.size / 1024).toFixed(1);
    showToast(`✓ Loaded ${data.filename} (${kb} KB, ${data.chars?.toLocaleString()} characters)`);
    noteInput.focus();
  } catch (err) {
    showToast(`⚠️ Upload failed: ${err.message}`, 4000);
  } finally {
    uploadBtn.innerHTML = origHTML;
    uploadBtn.style.pointerEvents = '';
    fileInput.value = '';
  }
}

// ── Event binding ─────────────────────────────────────────────────────────────
function bindEvents() {
  sendBtn.addEventListener('click', sendNote);

  noteInput.addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); sendNote(); }
  });

  noteInput.addEventListener('input', () => {
    autoResizeTextarea();
    checkSpelling();
    updateInputSuggestionsFromText(noteInput.value);
  });

  fileInput.addEventListener('change', e => handleFileUpload(e.target.files[0]));

  const inputBox = $('input-box');
  ['dragenter','dragover'].forEach(ev => inputBox.addEventListener(ev, e => {
    e.preventDefault(); inputBox.style.borderColor = 'var(--blue)';
  }));
  ['dragleave','dragend'].forEach(ev => inputBox.addEventListener(ev, () => {
    inputBox.style.borderColor = '';
  }));
  inputBox.addEventListener('drop', e => {
    e.preventDefault();
    inputBox.style.borderColor = '';
    const file = e.dataTransfer.files[0];
    if (file) handleFileUpload(file);
  });

  themeBtn.addEventListener('click', toggleTheme);

  $('new-chat-btn').addEventListener('click', newChat);
  $('mobile-new') && $('mobile-new').addEventListener('click', newChat);
  $('hamburger')  && $('hamburger').addEventListener('click', openSidebar);

  document.querySelectorAll('.mode-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      if (tab.dataset.mode !== state.mode) applyMode(tab.dataset.mode, true);
    });
  });

  noteInput.addEventListener('focus', () => {
    $('input-hint') && ($('input-hint').textContent = 'Ctrl+Enter to send');
  });
}

// ── Run ───────────────────────────────────────────────────────────────────────
init().catch(console.error);
