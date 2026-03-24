# autoresearch — parameter golf default task

Combine this file with `instructions/base_program.md`.

Assume you are already in the checkout or worktree you should use.

## Default loop

Loop indefinitely once setup is complete:

1. Check the current git state.
2. Query `autoresearch summary` and read relevant past `workspace/exp.md` files via `autoresearch read <commit>` to understand what has been tried. The first run from any fresh starting commit should normally be the unmodified baseline for that starting commit unless your instruction says otherwise or `autoresearch read <commit_hash>` is completed.
3. Think about one concrete idea. Update `workspace/exp.md` with the hypothesis and reasoning, and edit `workspace/train_gpt.py` to implement the idea. Think deeply and mathematically.
4. Follow the single-experiment contract in `instructions/base_program.md`: commit the exact runnable snapshot before each training attempt, and treat the last code snapshot actually executed as the `run_commit`.
5. Run: `python3 run.py train > run.log 2>&1` and wait until the training finished, crashed, or timed out.
6. Inspect `run.log`.
7. If the run failed because of an obvious mistake and the idea is still worth testing, fix it, commit the new runnable snapshot, and retry a small number of times. The commit from the final executed retry is the `run_commit` for the experiment you record.
8. If the idea is broken or the run crashed/timed out, append the failure results to `workspace/exp.md`, create the `result_commit`, and record the experiment with `--status crash` or `--status timeout`.
9. If the run succeeded, append **Results** to `workspace/exp.md`, including the decision, metrics, and your analysis. Create a `result_commit` that only updates `workspace/exp.md`, then record the experiment using `autoresearch` CLI.
10. Keep the result commit only if `val_bpb` improved. If equal, worse, or crashed, revert to the previous good result commit.

Modal runs use the timeouts in `.runner/modal_app.py`. If a run hangs far beyond that budget, treat it as a failure.

Once the loop starts, do not stop to ask the human whether to continue. Keep iterating until interrupted.
