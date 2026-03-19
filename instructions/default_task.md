# autoresearch — parameter golf default task

Use this file only when no orchestrator-specific worker brief was provided.

Combine this file with `instructions/base_program.md`.

Assume you are already in the checkout or worktree you should use.

## Default loop

Loop indefinitely once setup is complete:

1. Query `autoresearch summary` and read past `workspace/exp.md` files via `autoresearch read <commit>` to understand what has been tried.
2. Check the current git state.
3. Edit `workspace/train_gpt.py` with one concrete idea. Write `workspace/exp.md` with hypothesis and reasoning. Think deeply and mathematically.
4. Commit the runnable snapshot. Save the hash as the run commit.
5. Run: `python3 run.py train > run.log 2>&1`.
6. Check logs: ensure `run.log` contains `final_int8_zlib_roundtrip` with a `val_bpb:` field, and `peak memory allocated` for VRAM. Example:

   ```bash
   grep "final_int8_zlib_roundtrip" run.log
   grep "peak memory allocated" run.log
   ```

7. If those lines are missing or clearly wrong, inspect `tail -n 80 run.log`. Fix obvious mistakes and retry a small number of times. If the idea is broken, write the failure into `workspace/exp.md`, commit the results note, and record with `--status crash` or `--status timeout`.
8. Append **Results** to `workspace/exp.md`, including the keep/discard decision and parsed metrics. Commit that update. Save the hash as the result commit.
9. Record once:

   ```bash
   autoresearch record <run-commit> --result-commit <result-commit> \
     --status success --decision keep|discard --description "..." \
     --metric val_bpb=<...> --metric peak_vram_mb=<...>
   ```

   Use the `val_bpb` from the final `final_int8_zlib_roundtrip` line and parse `peak memory allocated: N MiB` as `peak_vram_mb=N`.

10. Keep the result commit only if `val_bpb` improved. If equal, worse, or crashed, revert to the previous good result commit.

Modal runs use the timeouts in `.runner/modal_app.py`. If a run hangs far beyond that budget, treat it as a failure.

Once the loop starts, do not stop to ask the human whether to continue. Keep iterating until interrupted.
