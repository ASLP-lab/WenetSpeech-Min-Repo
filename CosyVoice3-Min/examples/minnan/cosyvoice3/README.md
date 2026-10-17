# Minnan LLM training configuration

`conf/cosyvoice3_minnan.yaml` defines the JSONL input pipeline and LLM training
hyperparameters used by `cosyvoice/bin/train.py`.

Each line in `train.data.list` or `dev.data.list` points to a JSONL shard. The
records are expected to contain text, pre-extracted text/speech tokens, and the
metadata consumed by `cosyvoice.dataset.jsonl_processor`.

Run `cosyvoice/bin/train.py` through `torchrun`; the repository-level README
contains complete single-GPU and multi-GPU commands.
