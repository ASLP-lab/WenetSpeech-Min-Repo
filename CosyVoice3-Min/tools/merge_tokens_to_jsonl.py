#!/usr/bin/env python3
"""
Merge pre-extracted speech tokens back into a JSONL file.

Reads an input JSONL and a utt2speech_token.pt file, then writes
an enriched JSONL with the speech_token field added to each sample.

Input:
    --input_jsonl:  original JSONL with {utt, wav_path, text, ...}
    --token_pt:     utt2speech_token.pt (dict: {utt_id: [token_ids]})
    --output_jsonl: output JSONL with speech_token added
    --instruct:     default instruct text (optional)

Usage:
    python tools/merge_tokens_to_jsonl.py \
        --input_jsonl data/train.jsonl \
        --token_pt data/token/utt2speech_token.pt \
        --output_jsonl data/train_features.jsonl \
        --instruct "用闽南语说这句话<|endofprompt|>"
"""
import argparse
import json
import logging
import os

import torch

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description='Merge speech tokens into JSONL')
    parser.add_argument('--input_jsonl', type=str, required=True,
                        help='Input JSONL file')
    parser.add_argument('--token_pt', type=str, required=True,
                        help='utt2speech_token.pt from S3Tokenizer')
    parser.add_argument('--output_jsonl', type=str, required=True,
                        help='Output JSONL with speech_token')
    parser.add_argument('--instruct', type=str,
                        default='用闽南语说这句话<|endofprompt|>',
                        help='Default instruct text')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s')

    # Load token dict
    logger.info('Loading tokens from %s', args.token_pt)
    utt2token = torch.load(args.token_pt, map_location='cpu')
    logger.info('Loaded %d utterances with tokens', len(utt2token))

    # Load input JSONL
    logger.info('Loading JSONL from %s', args.input_jsonl)
    samples = []
    with open(args.input_jsonl, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    logger.info('Loaded %d samples', len(samples))

    # Merge
    merged = 0
    missing = 0
    os.makedirs(os.path.dirname(args.output_jsonl) or '.', exist_ok=True)
    with open(args.output_jsonl, 'w', encoding='utf-8') as f:
        for s in samples:
            utt = s['utt']
            token = utt2token.get(utt)
            if token is None:
                logger.warning('No token found for utt %s, skipping', utt)
                missing += 1
                continue
            # Convert tensor to list if needed
            if isinstance(token, torch.Tensor):
                token = token.tolist()
            s['speech_token'] = token
            if 'instruct' not in s:
                s['instruct'] = args.instruct
            f.write(json.dumps(s, ensure_ascii=False) + '\n')
            merged += 1

    logger.info('Done! %d samples written to %s, %d missing',
                merged, args.output_jsonl, missing)


if __name__ == '__main__':
    main()
