const el = {
  connection: document.querySelector('#connection'),
  refresh: document.querySelector('#refresh'),
  presentationSelect: document.querySelector('#presentationSelect'),
  previous: document.querySelector('#previous'),
  next: document.querySelector('#next'),
  slideNumber: document.querySelector('#slideNumber'),
  slideTitle: document.querySelector('#slideTitle'),
  notes: document.querySelector('#notes'),
  raw: document.querySelector('#raw')
};

let presentations = [];
let selected = null;
let pollTimer = null;

async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {})
    }
  });

  if (response.status === 204) return null;

  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || response.statusText);
  return data;
}

function idValue(id) {
  return id?.uuid || id?.name || String(id?.index ?? '');
}

function labelFor(item) {
  const lib = item.library?.name || item.library?.uuid || 'Library';
  const pres = item.presentation?.name || item.presentation?.uuid || `Presentation ${item.presentation?.index ?? ''}`;
  return `${lib} — ${pres}`;
}

function setConnection(ok, message) {
  el.connection.className = ok ? 'statusGood' : 'statusBad';
  el.connection.textContent = message;
}

async function checkHealth() {
  const config = await request('/api/config');
  try {
    await request('/api/health');
    setConnection(true, `Connected to ${config.baseUrl}`);
  } catch (err) {
    setConnection(false, `Cannot reach ${config.baseUrl}: ${err.message}`);
  }
}

async function loadPresentations() {
  presentations = await request('/api/presentations');
  el.presentationSelect.innerHTML = '';

  if (!presentations.length) {
    const option = document.createElement('option');
    option.value = '';
    option.textContent = 'No presentations found';
    el.presentationSelect.appendChild(option);
    return;
  }

  presentations.forEach((item, index) => {
    const option = document.createElement('option');
    option.value = String(index);
    option.textContent = labelFor(item);
    el.presentationSelect.appendChild(option);
  });

  selected = presentations[0];
  el.presentationSelect.value = '0';
}

async function updateSlideState() {
  const params = new URLSearchParams();
  if (selected) {
    params.set('libraryId', idValue(selected.library));
    params.set('presentationId', idValue(selected.presentation));
  }

  try {
    const state = await request(`/api/slide-state?${params.toString()}`);
    el.slideNumber.textContent = `Slide ${state.slideNumber ?? '—'}`;
    el.slideTitle.textContent = state.title || '';
    el.notes.textContent = state.notes || 'No slide notes found for this slide.';
    el.raw.textContent = JSON.stringify(state.raw, null, 2);
  } catch (err) {
    el.notes.textContent = `Unable to read slide notes: ${err.message}`;
  }
}

async function trigger(direction) {
  el.previous.disabled = true;
  el.next.disabled = true;
  try {
    await request(`/api/trigger/${direction}`, { method: 'POST' });
    await new Promise((resolve) => setTimeout(resolve, 250));
    await updateSlideState();
  } finally {
    el.previous.disabled = false;
    el.next.disabled = false;
  }
}

function startPolling() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(updateSlideState, 1000);
}

el.refresh.addEventListener('click', async () => {
  await checkHealth();
  await loadPresentations();
  await updateSlideState();
});

el.presentationSelect.addEventListener('change', async () => {
  selected = presentations[Number(el.presentationSelect.value)] || null;
  if (selected) {
    await request('/api/trigger/slide', {
      method: 'POST',
      body: JSON.stringify({
        libraryId: idValue(selected.library),
        presentationId: idValue(selected.presentation),
        index: 0
      })
    });
  }
  await updateSlideState();
});

el.previous.addEventListener('click', () => trigger('previous'));
el.next.addEventListener('click', () => trigger('next'));

document.addEventListener('keydown', (event) => {
  if (event.key === 'ArrowRight' || event.key === 'PageDown') trigger('next');
  if (event.key === 'ArrowLeft' || event.key === 'PageUp') trigger('previous');
});

await checkHealth();
await loadPresentations();
await updateSlideState();
// startPolling();
