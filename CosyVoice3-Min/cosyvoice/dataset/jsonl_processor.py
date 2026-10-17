# Copyright (c) 2024 Alibaba Inc (authors: Xiang Lyu)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
JSONL dataset opener for CosyVoice3 training.

Provides jsonl_opener as a drop-in replacement for parquet_opener.
Reads JSONL files that contain pre-extracted speech tokens and text.
When wav_path is not available on this filesystem, silent audio is
substituted so the pipeline can proceed (LLM training only needs
speech_token, not actual audio).
"""
import io
import json
import logging
import os
import wave


def _make_silent_wav(sample_rate=24000, duration=1.5):
    """Generate silent WAV bytes so the pipeline doesn't crash when
    the actual wav file is not available on this filesystem.
    Duration must be >= 1s to pass min_length filter (100 frames).
    """
    buf = io.BytesIO()
    n_samples = int(sample_rate * duration)
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b'\x00\x00' * n_samples)
    return buf.getvalue()


def jsonl_opener(data, mode='train'):
    """Open JSONL files as a drop-in replacement for parquet_opener.

    Each JSONL line should be a JSON object with at least:
        - utt: utterance id
        - wav_path: path to the audio file
        - text: transcription text
        - speech_token: list of pre-extracted speech token ids
        - instruct: instruction/prompt text

    Audio is loaded from wav_path into audio_data (raw bytes) so that
    the downstream filter/resample/compute_fbank processors work
    without modification.

    A dummy speaker embedding is injected so that parse_embedding
    does not crash. CosyVoice3 LLM does not consume this embedding.

    Args:
        data: Iterable[{src, ...}] from DataList
        mode: 'train' or 'dev'

    Yields:
        dict with fields matching parquet_opener output schema
    """
    DUMMY_EMBEDDING_DIM = 192
    # Unit vector [1, 0, 0, ...] — survives F.normalize cleanly
    DUMMY_EMBEDDING = [0.0] * DUMMY_EMBEDDING_DIM
    DUMMY_EMBEDDING[0] = 1.0

    for sample in data:
        assert 'src' in sample
        jsonl_path = sample['src']
        try:
            with open(jsonl_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    item = json.loads(line)

                    # Load audio bytes from wav_path (required by filter)
                    wav_path = item.get('wav_path', '')
                    if wav_path and os.path.exists(wav_path):
                        with open(wav_path, 'rb') as af:
                            item['audio_data'] = af.read()
                    else:
                        item['audio_data'] = _make_silent_wav()

                    # Inject dummy speaker embedding so parse_embedding
                    # does not crash. CosyVoice3 LLM ignores this field.
                    item['utt_embedding'] = DUMMY_EMBEDDING
                    item['spk_embedding'] = DUMMY_EMBEDDING

                    # Merge sampler info (rank, world_size, etc.) into sample
                    yield {**sample, **item}
        except Exception as ex:
            logging.warning('Failed to open %s, ex info %s', jsonl_path, ex)
