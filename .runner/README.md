# Parameter Golf on Modal

This folder contains a **task-owned** Modal app: cloud **CPU** for downloading challenge data and **GPU** for `workspace/train_gpt.py`. It mirrors the pattern used in the `task-nanogpt` autoresearch checkout.

## What runs where

| Where | Script | Stack |
|--------|--------|--------|
| **Modal GPU** | `workspace/train_gpt.py` | PyTorch + CUDA (Linux) |
| **Modal CPU** | `workspace/prepare.py` → `data/cached_challenge_fineweb.py` | Hugging Face Hub downloads |
| **Your Mac (local)** | `train_gpt_mlx.py` | MLX / Apple Silicon — **not** used by this runner |

Do not expect MLX on Modal; use `workspace/train_gpt.py` for cloud training here.

## Prerequisites

1. A [Modal](https://modal.com) account and workspace.
2. The Modal CLI on your PATH: [install](https://modal.com/docs/guide), then log in (e.g. `modal setup` or `modal token set`).
3. This repository cloned; commands below assume your **current working directory is the Parameter Golf task root** (the directory that contains `run.py`, `workspace/`, and `.runner/`).

### Optional: `.env` in the task root

`modal_runner.py` loads **`./.env`** from the task root (if the file exists) before invoking `modal run`. Entries are applied only for keys **not** already set in the process environment, so the shell still wins. Use this for `HF_TOKEN` / `HUGGING_FACE_HUB_TOKEN` and other vars that appear in `_FORWARD_ENV_KEYS` in `modal_app.py`. `.env` is listed in `.gitignore`; do not commit secrets.

## Typical flow

### 1. Download data on Modal (CPU)

Arguments after `prepare` are forwarded through `workspace/prepare.py`, which runs `data/cached_challenge_fineweb.py` (same idea as NanoGPT’s `modal_runner` + `argparse.REMAINDER`).

```bash
python run.py prepare --train-shards 1 --variant sp1024
```

For more training shards (longer download, larger cache), increase `--train-shards`. Full default in the upstream README is `80`.

### 2. Train on Modal (GPU)

Environment variables from your shell **or** from `.env` (see above) are forwarded into the container for a fixed allowlist (see `_FORWARD_ENV_KEYS` in `modal_app.py`). Examples:

**Short smoke:**

```bash
RUN_ID=modal_smoke \
ITERATIONS=200 \
TRAIN_BATCH_TOKENS=8192 \
VAL_LOSS_EVERY=0 \
VAL_BATCH_SIZE=81920 \
python run.py train
```

**Closer to defaults (still override as needed):**

```bash
RUN_ID=modal_run \
python run.py train
```

On Modal, downloads and tokenizer artifacts are stored under **`/cache-home/parameter-golf-data/`** (same layout as the repo’s `data/` directory: `datasets/`, `tokenizers/`). The runner sets `PARAMETER_GOLF_MODAL_DATA_ROOT` and, unless you override them, `DATA_PATH` / `TOKENIZER_PATH` for **`sp1024`**. If you run `prepare` with another `--variant`, set `DATA_PATH` and `TOKENIZER_PATH` when training to match that variant’s paths.

### Verbosity

- By default, Modal progress is quieter for `prepare` and noisier for `train` (same behavior as the NanoGPT runner).
- Override with `--quiet` / `--no-quiet` on `modal_runner.py` if you invoke it directly; `run.py` forwards all args to `modal_runner`.

## Cache and volume

The app name is `autoresearch-parameter-golf`. Modal keeps a volume named **`autoresearch-parameter-golf-cache`** mounted at **`/cache-home`**, and the container sets **`HOME=/cache-home`**. Hugging Face cache and downloaded `data/` shards persist across runs so you usually only need `prepare` again when you change shard counts or variants.

Training writes logs and model artifacts under **`/cache-home/parameter-golf-runs/<RUN_ID>/`** (`train.log`, `final_model.pt`, `final_model.int8.ptz`). The runner sets `PARAMETER_GOLF_OUTPUT_ROOT` for remote jobs; omit it locally and logs still go under **`./logs/<RUN_ID>.txt`** so the task root stays clean. The extra `logs/` folder is only for that local layout.

## Troubleshooting

| Issue | What to try |
|--------|----------------|
| `` `modal` is not on PATH `` | Install the CLI and open a new shell. |
| Prepare times out | Lower `--train-shards` or raise `timeout` on `cpu_remote` in `modal_app.py`. |
| Train times out | Shorten `ITERATIONS` / wallclock, or raise `timeout` on `gpu_remote` in `modal_app.py`. |
| CUDA OOM | Reduce `TRAIN_BATCH_TOKENS` or model size env vars (`MODEL_DIM`, `NUM_LAYERS`, …). |
| HF auth errors | Set `HF_TOKEN` (or `HUGGING_FACE_HUB_TOKEN`) in the environment before `python run.py …`; it is forwarded if set. |

## Files in this directory

| File | Purpose |
|------|---------|
| `modal_app.py` | Modal `App`, image (`uv_sync` from `modal/`), volume, `cpu_remote` / `gpu_remote`, local entrypoint. |
| `modal_runner.py` | Local wrapper: `modal run … --action prepare|train`. |
| `modal/pyproject.toml` | CUDA PyTorch + deps for the remote image (with `uv.lock`). |

Root-level `run.py` delegates to `modal_runner.py` so you can run everything from the task root.
