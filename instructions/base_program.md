# Base Instruction

Assume you have already been launched in the correct checkout or worktree. Do not create new worktrees yourself.

## Goal

Overall goal and constraints: `instructions/goal_and_constraints.md`. Your specific goal is defined by the instruction you're launched with.

## Context

Read-only:

- `data/cached_challenge_fineweb.py` - actual downloader and layout for datasets/tokenizers.
- `.runner/modal/pyproject.toml` - remote runtime manifest.
- `.runner/modal_app.py` - Modal warpper.

Your workspace (editable):
- `workspace/train_gpt.py` - the only training code file you will modify.
- `workspace/exp.md` - create or update for each experiment.

You can ONLY modify the 2 editable files above. Any changes outside the scope will incur a loss.

## Execution Contract

Each experiment runs on Modal with the GPU and timeouts configured in `.runner/modal_app.py`.
Current autoresearch training runs use a single-A10 proxy setup to rank ideas before the final
8xH100 submission runs. Treat proxy results as directional rather than exact; hyperparameters that
win on the proxy may still need retuning or rejection on the real 8xH100 budget.

```bash
python3 run.py train > run.log 2>&1
```

This is the only experiment execution command for you.

## Scratch Work

You may use local Python for quick calculations or small hypothesis checks:

```bash
python3 - <<'PY'
import math
print(math.sqrt(2))
PY
```

## Single-Experiment Contract

One recorded experiment must correspond to one exact executed code snapshot.

Definitions:

- `run_commit`: the exact git commit whose code was actually executed for the run you are recording
- `result_commit`: a later commit that records the final outcome of that same run in `workspace/exp.md`
- `base_commit`: the starting point the experiment started, usually the parent of `run_commit` if the first attempt to train is successful.

Rules:

- Before every training attempt, commit the current changes.
- If you change `workspace/train_gpt.py` or change the pre-run contents of `workspace/exp.md`, commit again before rerunning.
- If you fix a bug after a failed attempt and rerun, the new commit becomes the `run_commit` for the experiment you eventually record.
- Do not record an older commit if later code was the one that actually produced the final result.
- `result_commit` must be a descendant of `run_commit`.
- The only allowed change between `run_commit` and `result_commit` is updating `workspace/exp.md` with the run outcome. Do not change executable code in between.

## exp.md

`workspace/exp.md` is for one experiment only. Do not accumulate multiple experiments in the same file.

For each new experiment:

- start from a fresh `workspace/exp.md` for that experiment
- replace the previous contents instead of appending a new experiment below an old one
- use `autoresearch read <commit>` to inspect prior experiment writeups

Write `workspace/exp.md` before the run commit. Include:

- **Hypothesis**: what you expect and why
- **Reasoning**: mathematical derivation, parameter calculations, or conceptual argument
- **References**: papers/sources and what you took from them, N/A if not applicable

After the run, append a **Results** section with val_bpb, peak VRAM (MiB), optional submission
size lines from the log, status (`keep`, `discard`, `crash`, or `timeout`), and brief analysis.
Within a single experiment, appending the **Results** section is correct. Across experiments, replace
the file with a new experiment note.
That results update is the only change allowed in `result_commit`.

## Experiment tracking

After a successful run, locate metrics in `run.log`. Note that you may log other metrics by modifying `workspace/train_gpt.py`.

Record each experiment once, after the `result_commit` exists. Each DB row stores both the executed `run_commit` and the later `result_commit`.

```bash
autoresearch record <run-commit> \
  --result-commit <result-commit> \
  --status success \
  --decision keep|discard \
  --description "one-line summary" \
  --agent-id <agent-id> \
  --metric val_bpb=<value> \
  --metric peak_vram_mb=<value> \
  ... (other notable metrics)
```

Use the `val_bpb` from the eval of the final submission artifact (post-quantized/processed).

For crashes or timeouts, omit `--decision`:

```bash
autoresearch record <run-commit> \
  --result-commit <result-commit> \
  --status crash \
  --description "one-line summary" \
  --agent-id <agent-id>
```

Browse experiments with:

```bash
autoresearch summary
autoresearch read <commit-hash>
```
