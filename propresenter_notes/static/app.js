const el = {
  connection: document.querySelector('#connection'),
  refresh: document.querySelector('#refresh'),
  presentationSelect: document.querySelector('#presentationSelect'),
  previous: document.querySelector('#previous'),
  next: document.querySelector('#next'),
  cacheStatus: document.querySelector('#cacheStatus'),
  thumbnailStrip: document.querySelector('#thumbnailStrip'),
  slideNumber: document.querySelector('#slideNumber'),
  slideTitle: document.querySelector('#slideTitle'),
  notes: document.querySelector('#notes'),
  raw: document.querySelector('#raw')
};

let presentations = [];
let selected = null;
let selectedSlideIndex = 0;
let selectedCache = null;
let changeTimer = null;

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

function selectedPresentationId() {
  return selected ? idValue(selected.presentation) : '';
}

function selectedLibraryId() {
  return selected ? idValue(selected.library) : '';
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

function setRefreshDirty(isDirty) {
  el.refresh.classList.toggle('needsRefresh', isDirty);
  el.refresh.setAttribute(
    'aria-label',
    isDirty ? 'Presentation changed in ProPresenter. Refresh to reload.' : 'Refresh presentation'
  );
}

function setCacheStatus(message, isWarning = false) {
  el.cacheStatus.textContent = message;
  el.cacheStatus.className = isWarning ? 'statusWarn' : '';
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

async function loadPresentations(keepCurrent = false) {
  const previousId = keepCurrent ? selectedPresentationId() : '';
  presentations = await request('/api/presentations');
  el.presentationSelect.innerHTML = '';

  if (!presentations.length) {
    const option = document.createElement('option');
    option.value = '';
    option.textContent = 'No presentations found';
    el.presentationSelect.appendChild(option);
    selected = null;
    return;
  }

  presentations.forEach((item, index) => {
    const option = document.createElement('option');
    option.value = String(index);
    option.textContent = labelFor(item);
    el.presentationSelect.appendChild(option);
  });

  const previousIndex = presentations.findIndex((item) => idValue(item.presentation) === previousId);
  const nextIndex = previousIndex >= 0 ? previousIndex : 0;
  selected = presentations[nextIndex];
  el.presentationSelect.value = String(nextIndex);
}

function slideNotes(slide) {
  return slide?.notes || 'No slide notes found for this slide.';
}

function showSlide(index) {
  if (!selectedCache?.slides?.length) {
    selectedSlideIndex = 0;
    el.slideNumber.textContent = 'Slide —';
    el.slideTitle.textContent = '';
    el.notes.textContent = 'No notes loaded yet.';
    return;
  }

  const clampedIndex = Math.max(0, Math.min(index, selectedCache.slides.length - 1));
  selectedSlideIndex = clampedIndex;
  const slide = selectedCache.slides[clampedIndex];
  el.slideNumber.textContent = `Slide ${slide.number ?? clampedIndex + 1}`;
  el.slideTitle.textContent = slide.title || '';
  el.notes.textContent = slideNotes(slide);
  el.raw.textContent = JSON.stringify(slide, null, 2);

  [...el.thumbnailStrip.querySelectorAll('.thumbnailCard')].forEach((button) => {
    button.classList.toggle('active', Number(button.dataset.index) === clampedIndex);
  });
}

function renderSlides() {
  el.thumbnailStrip.innerHTML = '';
  const slides = selectedCache?.slides || [];
  if (!slides.length) {
    const empty = document.createElement('p');
    empty.className = 'emptySlides';
    empty.textContent = 'No slides were found in this presentation.';
    el.thumbnailStrip.appendChild(empty);
    return;
  }

  slides.forEach((slide) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'thumbnailCard';
    button.dataset.index = String(slide.index);
    button.setAttribute('aria-label', `Show notes for slide ${slide.number}`);

    if (slide.thumbnail) {
      const img = document.createElement('img');
      img.src = slide.thumbnail;
      img.alt = slide.title || `Slide ${slide.number}`;
      button.appendChild(img);
    } else {
      const placeholder = document.createElement('div');
      placeholder.className = 'thumbnailPlaceholder';
      placeholder.textContent = `Slide ${slide.number}`;
      button.appendChild(placeholder);
    }

    const caption = document.createElement('span');
    caption.textContent = `${slide.number}. ${slide.title || 'Untitled'}`;
    button.appendChild(caption);

    button.addEventListener('click', () => showSlide(slide.index));
    el.thumbnailStrip.appendChild(button);
  });
}

async function loadSelectedPresentationCache() {
  const presentationId = selectedPresentationId();
  if (!presentationId) {
    selectedCache = null;
    renderSlides();
    showSlide(0);
    setCacheStatus('Select a presentation to load slide thumbnails.');
    return;
  }

  el.refresh.disabled = true;
  setRefreshDirty(false);
  setCacheStatus('Loading presentation thumbnails and notes...');
  try {
    selectedCache = await request(`/api/presentation-cache/${encodeURIComponent(presentationId)}`);
    selectedSlideIndex = 0;
    renderSlides();
    showSlide(0);
    setCacheStatus(`Cached ${selectedCache.slides.length} slides. Notes will stay unchanged until you refresh.`);
    startChangeWatcher();
  } catch (err) {
    selectedCache = null;
    renderSlides();
    showSlide(0);
    setCacheStatus(`Unable to cache presentation: ${err.message}`, true);
  } finally {
    el.refresh.disabled = false;
  }
}

async function checkForPresentationChanges() {
  if (!selectedCache?.fingerprint || !selectedPresentationId()) return;

  try {
    const latest = await request(`/api/presentation-fingerprint/${encodeURIComponent(selectedPresentationId())}`);
    if (latest.fingerprint && latest.fingerprint !== selectedCache.fingerprint) {
      setRefreshDirty(true);
      setCacheStatus('Presentation changed in ProPresenter. Click Refresh to update this page.', true);
    }
  } catch (err) {
    setCacheStatus(`Unable to check for changes: ${err.message}`, true);
  }
}

function startChangeWatcher() {
  if (changeTimer) clearInterval(changeTimer);
  changeTimer = setInterval(checkForPresentationChanges, 5000);
}

async function triggerSlide(index) {
  if (!selected) return;
  await request('/api/trigger/slide', {
    method: 'POST',
    body: JSON.stringify({
      libraryId: selectedLibraryId(),
      presentationId: selectedPresentationId(),
      index
    })
  });
}

async function trigger(direction) {
  if (!selectedCache?.slides?.length) return;

  el.previous.disabled = true;
  el.next.disabled = true;
  try {
    const delta = direction === 'next' ? 1 : -1;
    const nextIndex = Math.max(0, Math.min(selectedSlideIndex + delta, selectedCache.slides.length - 1));
    await triggerSlide(nextIndex);
    showSlide(nextIndex);
  } finally {
    el.previous.disabled = false;
    el.next.disabled = false;
  }
}

el.refresh.addEventListener('click', async () => {
  await checkHealth();
  await loadPresentations(true);
  await loadSelectedPresentationCache();
});

el.presentationSelect.addEventListener('change', async () => {
  selected = presentations[Number(el.presentationSelect.value)] || null;
  if (selected) {
    await triggerSlide(0);
  }
  await loadSelectedPresentationCache();
});

el.previous.addEventListener('click', () => trigger('previous'));
el.next.addEventListener('click', () => trigger('next'));

document.addEventListener('keydown', (event) => {
  if (event.key === 'ArrowRight' || event.key === 'PageDown') trigger('next');
  if (event.key === 'ArrowLeft' || event.key === 'PageUp') trigger('previous');
});

await checkHealth();
await loadPresentations();
if (selected) {
  await triggerSlide(0);
}
await loadSelectedPresentationCache();
