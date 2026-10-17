#!/usr/bin/env python3
# Copyright (c) 2024 Alibaba Inc (authors: Xiang Lyu)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Extract speech tokens from a JSONL dataset for CosyVoice3 LLM fine-tuning.
Supports multi-GPU parallel extraction.

Input JSONL format (one JSON object per line):
    {"utt": "utt001", "wav_path": "/path/to/audio.wav", "text": "..."}

Output JSONL format:
    {"utt": "utt001", "wav_path": "/path/to/audio.wav", "text": "...",
     "speech_token": [123, 456, ...],
     "instruct": "用闽南语说这句话<|endofprompt|>"}

Usage (single GPU):
    python tools/extract_features_to_jsonl.py \
        --input data/train.jsonl \
        --output data/train_features.jsonl \
        --onnx_path pretrained_models/Fun-CosyVoice3-0.5B

Usage (multi GPU, 4 GPUs):
    python tools/extract_features_to_jsonl.py \
        --input data/train.jsonl \
        --output data/train_features.jsonl \
        --onnx_path pretrained_models/Fun-CosyVoice3-0.5B \
        --num_gpus 4
"""
import argparse
import json
import logging
import multiprocessing as mp
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import onnxruntime
import torch
import torchaudio
import whisper
from tqdm import tqdm

logger = logging.getLogger(__name__)


def load_jsonl(jsonl_path):
    """Load all samples from a JSONL file."""
    samples = []
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    return samples


def write_jsonl(samples, output_path):
    """Write samples to a JSONL file."""
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        for s in samples:
            f.write(json.dumps(s, ensure_ascii=False) + '\n')


def process_one_sample(sample, session, instruct):
    """Process a single sample: load audio, extract speech token.

    Args:
        sample: dict with keys utt, wav_path, text
        session: ONNX inference session (one per GPU worker)
        instruct: default instruct text

    Returns:
        dict or None (if failed)
    """
    utt = sample['utt']
    wav_path = sample.get('wav_path', sample.get('audio', ''))
    text = sample.get('text', '')

    try:
        audio, sample_rate = torchaudio.load(wav_path, backend='soundfile')
    except Exception as e:
        logger.warning('Failed to load audio for %s: %s', utt, e)
        return None

    # Resample to 16k if needed
    if sample_rate != 16000:
        audio = torchaudio.transforms.Resample(
            orig_freq=sample_rate, new_freq=16000)(audio)

    # Convert to mono
    if audio.shape[0] > 1:
        audio = audio.mean(dim=0, keepdim=True)

    # Skip audio longer than 30s (speech tokenizer limitation)
    if audio.shape[1] / 16000 > 30:
        logger.warning('Skipping %s: audio longer than 30s', utt)
        return None

    # Extract speech token
    try:
        feat = whisper.log_mel_spectrogram(audio, n_mels=128)
        speech_token = session.run(
            None,
            {
                session.get_inputs()[0].name:
                    feat.detach().cpu().numpy(),
                session.get_inputs()[1].name:
                    np.array([feat.shape[2]], dtype=np.int32),
            },
        )[0].flatten().tolist()
    except Exception as e:
        logger.warning('Failed speech token for %s: %s', utt, e)
        return None

    sample_instruct = sample.get('instruct', instruct)

    return {
        'utt': utt,
        'wav_path': wav_path,
        'text': text,
        'speech_token': speech_token,
        'instruct': sample_instruct,
    }


# ---------------------------------------------------------------------------
# Multi-GPU worker (runs in a separate process, one per GPU)
# ---------------------------------------------------------------------------

def _gpu_worker(gpu_id, onnx_path, samples, instruct, output_path):
    """Process a chunk of samples on a specific GPU.

    This function runs in a child process. It creates its own ONNX session,
    processes all assigned samples, and writes results to output_path.
    """
    # Each process gets its own logger
    logging.basicConfig(
        level=logging.INFO,
        format=f'%(asctime)s [GPU {gpu_id}] %(levelname)s %(message)s')

    logger.info('Worker starting on GPU %d, %d samples', gpu_id, len(samples))

    # Create ONNX session bound to this GPU
    option = onnxruntime.SessionOptions()
    option.graph_optimization_level = onnxruntime.GraphOptimizationLevel.ORT_ENABLE_ALL
    option.intra_op_num_threads = 1
    session = onnxruntime.InferenceSession(
        os.path.join(onnx_path, 'speech_tokenizer_v3.onnx'),
        sess_options=option,
        providers=[("CUDAExecutionProvider", {'device_id': gpu_id})],
    )

    results = []
    failed = 0
    for sample in tqdm(samples, desc=f'GPU {gpu_id}', position=gpu_id):
        result = process_one_sample(sample, session, instruct)
        if result is not None:
            results.append(result)
        else:
            failed += 1

    write_jsonl(results, output_path)
    logger.info('GPU %d done: %d success, %d failed -> %s',
                gpu_id, len(results), failed, output_path)

    # Return stats via the output file path convention (caller reads it)
    return len(results), failed


def _gpu_worker_wrapper(args):
    """Thin wrapper for multiprocessing pool compatibility."""
    gpu_id, onnx_path, chunk, instruct, output_path = args
    ok, fail = _gpu_worker(gpu_id, onnx_path, chunk, instruct, output_path)
    return ok, fail


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Extract speech tokens from JSONL (multi-GPU)')
    parser.add_argument('--input', type=str, required=True,
                        help='Input JSONL file path')
    parser.add_argument('--output', type=str, required=True,
                        help='Output JSONL file path')
    parser.add_argument('--onnx_path', type=str,
                        default='model_weights/Fun-CosyVoice3',
                        help='Directory containing speech_tokenizer_v3.onnx')
    parser.add_argument('--instruct', type=str,
                        default='用闽南语说这句话<|endofprompt|>',
                        help='Default instruct/prompt text for each sample.')
    parser.add_argument('--num_gpus', type=int, default=1,
                        help='Number of GPUs for parallel extraction. '
                             'Samples are split evenly across GPUs.')
    parser.add_argument('--num_threads_per_gpu', type=int, default=1,
                        help='Number of threads per GPU for I/O parallelism '
                             '(torchaudio loading can overlap with ONNX). '
                             'Set to 1 for pure single-threaded per GPU.')

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s')

    # Load input samples
    logger.info('Loading input JSONL: %s', args.input)
    samples = load_jsonl(args.input)
    logger.info('Loaded %d samples', len(samples))

    # Validate required fields
    required_fields = {'utt', 'text'}
    for i, sample in enumerate(samples):
        has_wav = 'wav_path' in sample or 'audio' in sample
        if not has_wav:
            raise ValueError(
                'Sample %d missing wav_path or audio field. '
                'Got keys: %s' % (i, list(sample.keys())))
        missing = required_fields - set(sample.keys())
        if missing:
            raise ValueError(
                'Sample %d missing required fields: %s. '
                'Got keys: %s' % (i, missing, list(sample.keys())))

    num_gpus = min(args.num_gpus, len(samples))

    if num_gpus <= 1:
        # --- Single GPU path (no multiprocessing overhead) ---
        logger.info('Single GPU mode on device 0, %d samples', len(samples))

        option = onnxruntime.SessionOptions()
        option.graph_optimization_level = \
            onnxruntime.GraphOptimizationLevel.ORT_ENABLE_ALL
        option.intra_op_num_threads = 1
        session = onnxruntime.InferenceSession(
            os.path.join(args.onnx_path, 'speech_tokenizer_v3.onnx'),
            sess_options=option,
            providers=[("CUDAExecutionProvider", {'device_id': 0})],
        )

        if args.num_threads_per_gpu <= 1:
            # Simplest: sequential
            results, failed = [], 0
            for s in tqdm(samples, desc='Extracting'):
                r = process_one_sample(s, session, args.instruct)
                if r is not None:
                    results.append(r)
                else:
                    failed += 1
        else:
            # Threaded I/O
            results, failed = [], 0
            with ThreadPoolExecutor(
                    max_workers=args.num_threads_per_gpu) as executor:
                futures = {
                    executor.submit(
                        process_one_sample, s, session, args.instruct
                    ): s for s in samples
                }
                for future in tqdm(as_completed(futures),
                                   total=len(futures),
                                   desc='Extracting'):
                    r = future.result()
                    if r is not None:
                        results.append(r)
                    else:
                        failed += 1

        write_jsonl(results, args.output)
        logger.info('Done! %d samples written to %s, %d failed',
                    len(results), args.output, failed)

    else:
        # --- Multi-GPU path ---
        logger.info('Multi-GPU mode: %d GPUs, %d total samples',
                    num_gpus, len(samples))

        # Split samples into chunks (one per GPU)
        chunk_size = (len(samples) + num_gpus - 1) // num_gpus
        chunks = []
        for gpu_id in range(num_gpus):
            start = gpu_id * chunk_size
            end = min(start + chunk_size, len(samples))
            chunks.append(samples[start:end])

        for i, chunk in enumerate(chunks):
            logger.info('  GPU %d: %d samples', i, len(chunk))

        # Create temp output files (one per GPU)
        temp_files = []
        for gpu_id in range(num_gpus):
            fd, path = tempfile.mkstemp(
                suffix='.jsonl',
                prefix=f'extract_gpu{gpu_id}_')
            os.close(fd)
            temp_files.append(path)

        # Spawn workers with 'spawn' context (required for CUDA)
        ctx = mp.get_context('spawn')
        worker_args = [
            (gpu_id, args.onnx_path, chunks[gpu_id],
             args.instruct, temp_files[gpu_id])
            for gpu_id in range(num_gpus)
        ]

        with ctx.Pool(processes=num_gpus) as pool:
            stats = pool.map(_gpu_worker_wrapper, worker_args)

        # Merge temp files into final output
        total_ok, total_fail = 0, 0
        with open(args.output, 'w', encoding='utf-8') as outf:
            for gpu_id, temp_path in enumerate(temp_files):
                ok, fail = stats[gpu_id]
                total_ok += ok
                total_fail += fail
                if os.path.exists(temp_path):
                    with open(temp_path, 'r', encoding='utf-8') as inf:
                        outf.write(inf.read())
                    os.unlink(temp_path)

        logger.info('Done! %d samples written to %s, %d failed (%d GPUs)',
                    total_ok, args.output, total_fail, num_gpus)


if __name__ == '__main__':
    main()
