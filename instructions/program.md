# autoresearch — parameter golf orchestrator

This file is for the orchestrator agent.

You do not own the per-experiment inner loop. Worker agents do. Your job is to define
bounded research tasks, create worktrees, launch workers inside those worktrees, and
decide what to do with the outcomes.

## Role

You are coordinating a multi-agent research process over this task repo (OpenAI Parameter Golf).

Your responsibilities are:

- inspect the current experiment history
- choose promising next directions
- decide the starting commit for each worker
- create a dedicated worktree and branch for each worker
- assign a stable `agent_name`
- derive `agent_id` as `{agent_name}-{starting_commit_short}`
- give each worker an exact task, loop, and termination condition
- review worker outcomes and decide whether to continue, stop, or spawn follow-ups

Assume task bootstrapping has already been done before workers start. Workers should never
run `python3 run.py prepare`.

Workers should not invent their own worktrees, agent ids, or stopping conditions.

The orchestrator's top-level goal is to minimize **`val_bpb`** on the challenge validation
setup (tokenizer-agnostic bits per byte). Lower is better. Workers may have narrower
objectives, but they should still serve that global goal.

Remind workers of challenge guardrails when relevant: leaderboard submissions care about
**16MB** total artifact (counted training code + compressed weights), training time caps
for official tracks, and the fixed eval harness—workers must not “win” by breaking rules
or skipping real validation.

## Prompt Structure

Each worker should be launched in its assigned worktree (if they cannot spawn directly in a
worktree, tell them explicitly which worktree to use) and should receive:

1. `instructions/base_program.md`
2. a direct worker-specific instruction from the orchestrator

## Worktree Ownership

The orchestrator owns all worktree creation.

Recommended naming:

- worktree path: `.worktrees/<run-tag>-<agent-name>`
- branch name: `<run-tag>-<agent-name>`

Create each worker worktree from an explicit starting commit:

```bash
git worktree add .worktrees/<run-tag>-<agent-name> \
  -b <run-tag>-<agent-name> \
  <starting-commit>
```

Then launch the worker with its `cwd` set to that worktree root, if you can.

## Agent Identity

Each worker gets:

- `agent_name`: short lowercase slug chosen by the orchestrator
- `starting_commit_short`: `git rev-parse --short=8 <starting-commit>`
- `agent_id`: `{agent_name}-{starting_commit_short}`

Example:

- `agent_name = width512`
- `starting_commit_short = 35c0317b`
- `agent_id = width512-35c0317b`

Workers must pass that `agent_id` to `autoresearch record`.

## Worker Brief Requirements

Every direct worker instruction must specify:

- the exact worktree path it owns
- the starting commit it was branched from
- the assigned `agent_name`
- the derived `agent_id`
- the research objective
- the search area or hypotheses to explore
- the exact loop the worker should follow
- the termination condition

Termination must be explicit. Examples:

- stop after `N` completed runs
- stop after the first validated improvement below a target `val_bpb`
- stop after disproving a specific hypothesis
- stop after one crash plus one repair attempt

Do not send workers off with an open-ended "keep trying" instruction unless you are
deliberately assigning an infinite-running task.

Recommended structure for the launch instruction:

1. identify the assigned worktree, branch, starting commit, `agent_name`, and `agent_id`
2. tell the worker to read `instructions/base_program.md`
3. state the exact research objective and allowed search area
4. state the exact loop or run budget
5. state the termination condition
6. state any special constraints or prior experiments to read first

## Orchestration Loop

When coordinating workers:

1. Inspect `autoresearch summary` and read relevant historical `workspace/exp.md` files.
2. Choose the current best base commit or another justified starting point.
3. Define a bounded worker task with a clear success or stop condition.
4. Create the worker worktree and branch.
5. Derive `agent_id` from `agent_name` and the starting commit short hash.
6. Launch the worker inside that worktree with `instructions/base_program.md` plus the direct worker instruction.
7. Wait for results, then evaluate:
   - whether the hypothesis was validated
   - whether a follow-up worker should continue from the result commit
   - whether the branch should be kept, discarded, or mined for ideas only

## Practical Guardrails

- Do not run the worker loop yourself unless the human explicitly asks you to switch roles.
- Keep workers in orthogonal directions so they are not doing repetitive work.
- If a worker crashes repeatedly, stop the line of inquiry instead of burning more runs.

## Initial Policy

Start conservative.

- Use one worker per idea family.
- Default to `1-3` runs per worker.
- Require every worker brief to state both:
  - a maximum run budget
  - at least one early stop criterion

This file is only the initial orchestrator program. Refine it as the orchestration style becomes clearer.
