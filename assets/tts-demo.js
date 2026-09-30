(function () {
  const container = document.getElementById('tts-samples');
  const samples = window.WENETSPEECH_TTS_SAMPLES;
  if (!container || !samples) return;

  const mandarinTranslations = {
    easy_v10_008: '那样东西卖完了，明天才会有货。',
    easy_v10_062: '老师讲的那些重点，你有没有抄下来？',
    easy_v10_065: '第一次自己坐高铁去台北，心里有点紧张，不过我从小胆子就很大。',
    easy_v10_223: '很高兴，我顺路载你去学校。',
    easy_v10_228: '功课做完，明天我们再一起去兜风。',
    easy_v10_273: '下班后我会去进货，明天你如果来，就有货卖给你。',
    easy_v10_434: '收不到通知，计划就改了。',
    easy_v10_445: '你先找皮包，如果没有，再去找抽屉，不要急。',
    easy_v10_486: '时间快到了，你不如先叫辆车来家门前等着？',
    hard_v5_017: '你如果有空，就替我去看看他说的那间房子；价格如果合理，周围也很清清清清清清清静，我就会考虑把它买下来。现在房价一直在涨，要是再犹豫下去，怕连机会都没有了。',
    hard_v5_099: '某款电动车的自动驾驶功能有更新，现在会自己换车道了；我对人工智能技术还是半信半疑半信半疑半信半疑半信半疑半信半疑，行车安全不是可以随便试的。',
    hard_v5_228: '天上有云，地上有尘。天上的云遮住太阳，地上的尘迷住眼睛。天上有云，地上有尘。天上的云遮住太阳，地上的尘迷住眼睛。'
  };

  const models = Object.keys(samples.easy[0].outputs);
  const scroll = document.createElement('div');
  scroll.className = 'table-scroll sample-table-scroll';
  scroll.setAttribute('role', 'region');
  scroll.setAttribute('aria-label', 'TTS samples with prompt audio and model outputs');
  scroll.tabIndex = 0;

  const table = document.createElement('table');
  table.className = 'tts-sample-table';
  const thead = document.createElement('thead');
  const header = document.createElement('tr');
  ['Text', 'Reference', ...models].forEach((label) => {
    const th = document.createElement('th');
    th.scope = 'col';
    th.textContent = label;
    if (label === 'CosyVoice3-WSM') th.classList.add('wsm-column');
    header.appendChild(th);
  });
  thead.appendChild(header);
  table.appendChild(thead);

  const body = document.createElement('tbody');
  [['easy', 'Easy'], ['hard', 'Hard']].forEach(([key, title]) => {
    samples[key].forEach((sample) => {
      const row = document.createElement('tr');
      const textCell = document.createElement('td');
      const text = document.createElement('p');
      text.className = 'sample-cell-text';
      text.textContent = sample.text;
      const translation = document.createElement('p');
      translation.className = 'sample-translation';
      translation.textContent = `普通话：${mandarinTranslations[sample.utt] || ''}`;
      textCell.append(text, translation);
      row.appendChild(textCell);

      const promptCell = document.createElement('td');
      promptCell.className = 'sample-reference-cell';
      promptCell.appendChild(makeAudio(sample.promptAudio, `${title} ${sample.number} reference audio`));
      row.appendChild(promptCell);

      models.forEach((model) => {
        const cell = document.createElement('td');
        if (model === 'CosyVoice3-WSM') cell.classList.add('wsm-column');
        cell.appendChild(makeAudio(sample.outputs[model], `${title} ${sample.number}, ${model}`));
        row.appendChild(cell);
      });
      body.appendChild(row);
    });
  });

  table.appendChild(body);
  scroll.appendChild(table);
  container.appendChild(scroll);

  function makeAudio(src, label) {
    const audio = document.createElement('audio');
    audio.controls = true;
    audio.preload = 'none';
    audio.setAttribute('aria-label', label);
    const source = document.createElement('source');
    source.src = src;
    source.type = src.toLowerCase().endsWith('.mp3') ? 'audio/mpeg' : 'audio/wav';
    audio.appendChild(source);
    return audio;
  }
})();
