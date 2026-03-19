# autoresearch — parameter golf base worker program

This file is the static worker contract.

Assume you have already been launched in the correct checkout or worktree. Do not create
new worktrees yourself. If an orchestrator assigned you a direct worker instruction, follow
that instruction in addition to this file.

## Read First

Read these files for context:

- `workspace/prepare.py` — workspace entrypoint for data download; delegates to
  `data/cached_challenge_fineweb.py`. Read-only.
- `data/cached_challenge_fineweb.py` — actual downloader and layout for datasets/tokenizers.
  Read-only.
- `workspace/train_gpt.py` — the only training code file you modify for CUDA/Modal experiments.
- `workspace/exp.md` — create or update for each experiment.
- `.runner/modal/pyproject.toml` from the repo root — remote runtime manifest. Read-only context.

Local Apple Silicon iteration uses `train_gpt_mlx.py` at the repo root; this Modal/autoresearch
loop uses **`python3 run.py train`**, which runs **`workspace/train_gpt.py`** on the remote GPU
image. Do not expect MLX in that path.

## Setup

1. Confirm you are working in the assigned checkout or worktree.
2. Read the in-scope files above.
3. Assume the Modal cache already exists. Cache preparation is not part of the worker role.
4. If a training run fails because the cache is missing or invalid, stop and report the issue.
5. Confirm the current `HEAD`, branch, and assigned `agent_id` before starting experiments.

## Execution Contract

Each experiment runs on Modal with the GPU and timeouts configured in `.runner/modal_app.py`
(typically a single CUDA GPU, e.g. `L40S`).

```bash
python3 run.py train > run.log 2>&1
```

This is the only experiment execution command for this autoresearch loop.

## Scratch Work

You may use local Python for quick calculations or small hypothesis checks:

```bash
python3 - <<'PY'
import math
print(math.sqrt(2))
PY
```

## Allowed Changes

- You can ONLY modify `workspace/train_gpt.py` for training experiments in this workflow.
- You may create or update `workspace/exp.md` for each experiment.
- Everything inside `workspace/train_gpt.py` is fair game: architecture, optimizer,
  hyperparameters, batch size, model shape, training loop, serialization—subject to challenge
  rules (artifact size, eval harness, etc.).

## Forbidden Changes

- Do not modify `workspace/prepare.py`, `data/cached_challenge_fineweb.py`, `run.py`, root
  `train_gpt_mlx.py`, or anything under `.runner/` unless the human explicitly asks.
- Do not run `python3 run.py prepare`.
- Do not install packages in the remote image from worker scripts (the image is fixed).
- Do not weaken or bypass the validation path that produces reported `val_bpb`.
- Do not create or manage worktrees unless the human explicitly asks. That is the orchestrator's job.

## Goal

The worker's goal is defined by the instruction it was launched with.

- In orchestrated mode, follow the orchestrator's stated objective, loop, and stopping condition.
- In single-agent mode, follow `instructions/default_task.md`.

For this task, **`val_bpb`** from the training script’s final roundtrip evaluation is the
primary metric unless the instruction says otherwise. Lower is better.

The first run from any fresh starting point should normally be the unmodified baseline for
that starting commit unless your instruction says otherwise.

Peak GPU memory is a useful secondary signal. Some increase is acceptable for a real gain;
avoid wasteful blowups.

Prefer simpler changes when the metric impact is similar. Deleting complexity for equal or
better results is a win.

## Output format (logs)

This task does not emit a NanoGPT-style `---` YAML footer. After a successful run, locate
metrics in `run.log` roughly as follows:

- **val_bpb**: lines containing `final_int8_zlib_roundtrip` (and `final_int8_zlib_roundtrip_exact`
  for high-precision). Prefer the roundtrip `val_bpb` that reflects the submission artifact path.
- **Peak VRAM**: a line like `peak memory allocated: … MiB`.

Example greps:

```bash
grep "final_int8_zlib_roundtrip" run.log
grep "peak memory allocated" run.log
```

Parse the numeric `val_bpb` from the last relevant roundtrip line for recording.

## exp.md

Write `workspace/exp.md` before the run commit. Include:

- **Hypothesis**: what you expect and why
- **Reasoning**: mathematical derivation, parameter calculations, or conceptual argument
- **References**: papers/sources and what you took from them, N/A if not applicable
- **Changes**: which file and what changed
- **Base**: parent commit hash and baseline val_bpb

After the run, append a **Results** section with val_bpb, peak VRAM (MiB), optional submission
size lines from the log, status (`keep`, `discard`, `crash`, or `timeout`), and brief analysis.
Then make a second commit with the completed results note.

## Experiment recording

Record each experiment once, after the results commit exists. Each DB row stores both the run
commit and the later results commit.

```bash
autoresearch record <run-commit> \
  --result-commit <result-commit> \
  --status success \
  --decision keep|discard \
  --description "one-line summary" \
  --agent-id <agent-id> \
  --metric val_bpb=<value> \
  --metric peak_vram_mb=<value>
```

Extract `val_bpb` and peak VRAM from `run.log` as described above. You may add more
`--metric` flags for other logged quantities if useful.

Browse experiments with:

```bash
autoresearch summary
autoresearch read <commit-hash>
```
