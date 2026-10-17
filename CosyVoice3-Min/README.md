# CosyVoice3 Minnan Minimal Training

A minimal CosyVoice3 LLM training loop for Minnan speech synthesis, based on
[CosyVoice](https://github.com/FunAudioLLM/CosyVoice).

## Contents

- `cosyvoice/bin/train.py`: the only training entry point
- `cosyvoice/utils/executor.py`: epoch, optimization, and validation loop
- `cosyvoice/utils/train_utils.py`: data loader, optimizer, logging, and checkpoint helpers
- `cosyvoice/dataset/`: JSONL loading and batching
- `cosyvoice/llm/`: model and forward loss
- `examples/minnan/cosyvoice3/conf/cosyvoice3_minnan.yaml`: training configuration
- `tools/`: feature, token, embedding, and JSONL/Parquet preparation helpers
- `third_party/Matcha-TTS/`: audio feature dependency used by the data pipeline

## Required local assets

Datasets, model weights, checkpoints, logs, and generated outputs are not
included. The commands below assume this layout:

```text
CosyVoice3-Min/
├── data/minnan/
│   ├── train.data.list
│   ├── dev.data.list
│   ├── train_test.data.list       # optional smoke-test subset
│   └── dev_test.data.list         # optional smoke-test subset
└── model_weights/Fun-CosyVoice3/
    ├── CosyVoice-BlankEN/
    ├── llm.pt
    ├── campplus.onnx
    ├── speech_tokenizer_v3.onnx
    └── speech_tokenizer_v3.batch.onnx
```

Each line in a `.data.list` file points to a JSONL shard. See
`examples/minnan/cosyvoice3/README.md` for the expected records.

## Training

Run all commands from the `CosyVoice3-Min` directory:

```bash
export PYTHONPATH="$PWD:$PWD/third_party/Matcha-TTS:${PYTHONPATH}"
```


Eight-GPU training:

```bash
CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7 torchrun \
  --standalone \
  --nnodes=1 \
  --nproc_per_node=8 \
  cosyvoice/bin/train.py \
  --train_engine torch_ddp \
  --config examples/minnan/cosyvoice3/conf/cosyvoice3_minnan.yaml \
  --train_data data/minnan/train.data.list \
  --cv_data data/minnan/dev.data.list \
  --qwen_pretrain_path model_weights/Fun-CosyVoice3/CosyVoice-BlankEN \
  --onnx_path model_weights/Fun-CosyVoice3 \
  --model llm \
  --checkpoint model_weights/Fun-CosyVoice3/llm.pt \
  --model_dir exp/cosyvoice3_minnan/llm \
  --tensorboard_dir tensorboard/cosyvoice3_minnan/llm \
  --ddp.dist_backend nccl \
  --num_workers 1 \
  --prefetch 4 \
  --use_amp
```

Important options:

- `--config`: model, data-pipeline, optimizer, scheduler, and epoch settings
- `--train_data`, `--cv_data`: files listing the JSONL training shards
- `--checkpoint`: initial or resume checkpoint
- `--model_dir`: checkpoint output directory
- `--tensorboard_dir`: TensorBoard event directory
- `--num_workers`, `--prefetch`: data-loading concurrency
- `--use_amp`: enable mixed-precision training
- `--ddp.dist_backend`: use `nccl` for GPUs or `gloo` where required

## License

This project is derived from CosyVoice and retains its Apache License 2.0.
See `LICENSE` and `NOTICE`. Model weights and datasets may have separate terms.
