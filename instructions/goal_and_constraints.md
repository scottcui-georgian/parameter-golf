# Goal and Criteria

## Goal

Primary objective: minimize final validation `val_bpb` on the fixed FineWeb validation split.

Operationally, this means optimizing the score that would count for submission, while staying within the challenge artifact, training-time, and evaluation-time limits. In this checkout, freely modify **`workspace/train_gpt.py`** to improve architecture, optimization, inference, evaluation, compression, and serialization.

## Submission Hard Constraints

- Training must reproducibly finish within `10 minutes` on `8xH100` for the leaderboard track.
- Evaluation must finish within `10 minutes` on `8xH100`.
- Final artifact size must satisfy:
  `bytes(training_script) + bytes(compressed model weights) <= 16,000,000`
  (in-repo canonical script: `workspace/train_gpt.py`)
- The artifact must be self-contained for evaluation:
  no external downloads, no network calls, and no training-data access during evaluation unless those bits are included in the artifact budget.
- Counted code should live in the single training script (`workspace/train_gpt.py` here; record PRs include a `train_gpt.py` snapshot in the record folder).
- The `train_gpt.py` script should never exceeds 1500 lines of code.

## Additional Official Submission Criteria

- For a new record submission, the result must beat the existing SOTA by at least `0.005` nats, with enough logs to show `p < 0.01`, unless the gain is purely from systems optimization without changing the ML.
- If the tokenizer or dataset changes, we must prove the `val_bpb` computation is correct.
- A valid submission PR must include a record folder with:
  `README.md`, `submission.json`, `train.log`, and the runnable `train_gpt.py` snapshot plus any required dependencies.

## Project-Specific Constraints

- Do not train on validation data.
- Fix the tokenizer to the current SP-1024 tokenizer (`fineweb_1024_bpe.model`).
- Fix the training data to one pinned SP-1024 FineWeb training corpus for all experiments.
- Keep the published FineWeb validation split fixed for scoring.
- Treat `workspace/train_gpt.py` as the main optimization surface in this repo.

## Practical Success Criteria

Each serious run should report these metrics, at minimum:

- final roundtrip `val_bpb`
- training wallclock
- evaluation wallclock
- final artifact bytes

Preferred changes are the ones that lower `val_bpb` under the fixed tokenizer/data policy without violating submission rules.
