(function () {
  const container = document.getElementById('dataset-audio-samples');
  const samples = window.WENETSPEECH_DATA_SAMPLES;
  if (!container || !samples) return;

  const grid = document.createElement('div');
  grid.className = 'dataset-sample-grid';
  grid.setAttribute('aria-label', 'Minnan speech samples');
  const removedSamples = new Set([3, 6, 8, 10, 13, 14, 15, 18, 19, 20, 24, 25, 26, 29, 31, 32, 35, 36, 37, 41, 42, 44, 45, 48]);

  samples.forEach((sample, index) => {
    const sampleNumber = index + 1;
    if (removedSamples.has(sampleNumber) || !sample.gender || sample.age == null) return;

    const card = document.createElement('article');
    card.className = 'dataset-sample-card';

    const heading = document.createElement('h4');
    heading.textContent = `Sample ${String(sampleNumber).padStart(2, '0')}`;

    const audio = document.createElement('audio');
    audio.controls = true;
    audio.preload = 'none';
    audio.setAttribute('aria-label', `Minnan speech sample ${sampleNumber}`);
    const source = document.createElement('source');
    source.src = sample.audio;
    source.type = 'audio/wav';
    audio.appendChild(source);

    const minnan = makeTranscript('Minnan', sample.minnan);
    const mandarin = makeTranscript('Mandarin', sample.mandarin);

    const stats = document.createElement('dl');
    stats.className = 'dataset-sample-stats';
    [
      ['MOS', formatScore(sample.mos)],
      ['SNR', formatScore(sample.snr, ' dB')],
      ['Gender', sample.gender || '—'],
      ['Age', sample.age == null ? '—' : `${Number(sample.age).toFixed(1)}`]
    ].forEach(([label, value]) => {
      const item = document.createElement('div');
      const term = document.createElement('dt');
      term.textContent = label;
      const description = document.createElement('dd');
      description.textContent = value;
      item.append(term, description);
      stats.appendChild(item);
    });

    card.append(heading, audio, minnan, mandarin, stats);
    grid.appendChild(card);
  });

  container.appendChild(grid);

  function makeTranscript(label, content) {
    const section = document.createElement('div');
    section.className = 'dataset-sample-transcript';
    const title = document.createElement('span');
    title.className = 'dataset-sample-label';
    title.textContent = label;
    const text = document.createElement('p');
    text.textContent = content || '—';
    section.append(title, text);
    return section;
  }

  function formatScore(value, suffix = '') {
    return value == null ? '—' : `${Number(value).toFixed(2)}${suffix}`;
  }
})();
