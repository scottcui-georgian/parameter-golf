"""
Modal backend for the Parameter Golf task.

This file is task-owned. The shared `autoresearch` package does not know anything
about Modal or this task's runtime layout.
"""

from __future__ import annotations

import codecs
import json
import os
import selectors
import subprocess
import sys
from pathlib import Path
from typing import Any

import modal

TASK_ROOT = Path(__file__).resolve().parent.parent
REMOTE_TASK_DIR = "/root/task"
VOLUME_ROOT = "/cache-home"
# Training logs and checkpoints (train_gpt reads PARAMETER_GOLF_OUTPUT_ROOT); persisted on the Modal volume.
VOLUME_RUNS_ROOT = f"{VOLUME_ROOT}/parameter-golf-runs"

APP_NAME = "autoresearch-parameter-golf"
# Modal GPU type for the train image and `gpu_remote` (single GPU). Change when switching hardware.
GPU_TYPE = "A10"
# Host CPU/memory for `cpu_remote` and `gpu_remote` (physical cores; memory in MiB per Modal API).
REMOTE_CPU = 4
REMOTE_MEMORY_MIB = 10 * 1024  # 10 GiB
RUNTIME_PROJECT_DIR = TASK_ROOT / ".runner" / "modal"
RUNNER_FILES = [
    "workspace/train_gpt.py",
    "workspace/prepare.py",
    "data/cached_challenge_fineweb.py",
]
ENTRYPOINTS = {
    "train": {"file": "workspace/train_gpt.py", "gpu": GPU_TYPE, "timeout": 1800},
    "prepare": {"file": "workspace/prepare.py", "cpu": REMOTE_CPU, "timeout": 7200},
}

# Forwarded from the machine that runs `modal run` (e.g. RUN_ID=… python run.py train).
_FORWARD_ENV_KEYS = frozenset(
    {
        "RUN_ID",
        "SEED",
        "DATA_PATH",
        "TOKENIZER_PATH",
        "ITERATIONS",
        "VAL_BATCH_SIZE",
        "VAL_LOSS_EVERY",
        "TRAIN_LOG_EVERY",
        "TRAIN_BATCH_TOKENS",
        "TRAIN_SEQ_LEN",
        "MAX_WALLCLOCK_SECONDS",
        "WARMUP_STEPS",
        "WARMDOWN_ITERS",
        "VOCAB_SIZE",
        "NUM_LAYERS",
        "MODEL_DIM",
        "NUM_HEADS",
        "NUM_KV_HEADS",
        "MLP_MULT",
        "TIE_EMBEDDINGS",
        "ROPE_BASE",
        "LOGIT_SOFTCAP",
        "QK_GAIN_INIT",
        "EMBED_LR",
        "HEAD_LR",
        "TIED_EMBED_LR",
        "TIED_EMBED_INIT_STD",
        "MATRIX_LR",
        "SCALAR_LR",
        "MUON_MOMENTUM",
        "MUON_BACKEND_STEPS",
        "MUON_MOMENTUM_WARMUP_START",
        "MUON_MOMENTUM_WARMUP_STEPS",
        "BETA1",
        "BETA2",
        "ADAM_EPS",
        "GRAD_CLIP_NORM",
        "HF_TOKEN",
        "HUGGING_FACE_HUB_TOKEN",
        "MATCHED_FINEWEB_REPO_ID",
        "MATCHED_FINEWEB_REMOTE_ROOT_PREFIX",
    }
)


def _forwarded_env_from_client() -> dict[str, str]:
    return {k: os.environ[k] for k in _FORWARD_ENV_KEYS if k in os.environ}


app = modal.App(APP_NAME)
cache_volume = modal.Volume.from_name(f"{APP_NAME}-cache", create_if_missing=True)

image = modal.Image.debian_slim(python_version="3.12").uv_sync(
    uv_project_dir=str(RUNTIME_PROJECT_DIR), gpu=GPU_TYPE
)
for relative_path in RUNNER_FILES:
    image = image.add_local_file(
        TASK_ROOT / relative_path,
        remote_path=f"{REMOTE_TASK_DIR}/{relative_path}",
    )


def _run_python(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a task script inside the Modal container while streaming and collecting output."""
    env = os.environ.copy()
    env["HOME"] = VOLUME_ROOT
    env["PYTHONUNBUFFERED"] = "1"
    # FineWeb shards must survive separate prepare vs train containers (see data/cached_challenge_fineweb.py).
    data_root = f"{VOLUME_ROOT}/parameter-golf-data"
    env["PARAMETER_GOLF_MODAL_DATA_ROOT"] = data_root
    if "DATA_PATH" not in env:
        env["DATA_PATH"] = f"{data_root}/datasets/fineweb10B_sp1024"
    if "TOKENIZER_PATH" not in env:
        env["TOKENIZER_PATH"] = f"{data_root}/tokenizers/fineweb_1024_bpe.model"
    env["PARAMETER_GOLF_OUTPUT_ROOT"] = VOLUME_RUNS_ROOT
    proc = subprocess.Popen(
        ["python", *args],
        cwd=REMOTE_TASK_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.stdout is not None
    assert proc.stderr is not None

    selector = selectors.DefaultSelector()
    selector.register(proc.stdout, selectors.EVENT_READ, data="stdout")
    selector.register(proc.stderr, selectors.EVENT_READ, data="stderr")

    decoders = {
        "stdout": codecs.getincrementaldecoder("utf-8")(errors="replace"),
        "stderr": codecs.getincrementaldecoder("utf-8")(errors="replace"),
    }
    outputs: dict[str, list[str]] = {"stdout": [], "stderr": []}
    writers = {"stdout": sys.stdout, "stderr": sys.stderr}

    while selector.get_map():
        for key, _ in selector.select():
            chunk = os.read(key.fileobj.fileno(), 4096)
            stream_name = key.data
            if not chunk:
                selector.unregister(key.fileobj)
                continue
            text = decoders[stream_name].decode(chunk)
            if text:
                outputs[stream_name].append(text)
                writers[stream_name].write(text)
                writers[stream_name].flush()

    for stream_name, decoder in decoders.items():
        tail = decoder.decode(b"", final=True)
        if tail:
            outputs[stream_name].append(tail)
            writers[stream_name].write(tail)
            writers[stream_name].flush()

    return subprocess.CompletedProcess(
        args=["python", *args],
        returncode=proc.wait(),
        stdout="".join(outputs["stdout"]),
        stderr="".join(outputs["stderr"]),
    )


def _tail(text: str, max_lines: int = 50) -> str:
    """Keep only the tail of large logs so crash output stays readable."""
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[-max_lines:])


def _extra_args_from_env() -> list[str]:
    """Read forwarded action args from the local runner wrapper."""
    raw = os.environ.get("AUTORESEARCH_MODAL_ACTION_ARGS", "[]")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Invalid AUTORESEARCH_MODAL_ACTION_ARGS payload.") from exc
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RuntimeError("AUTORESEARCH_MODAL_ACTION_ARGS must be a JSON array of strings.")
    return value


def _quiet_mode_from_env() -> bool:
    """Read whether Modal progress output should be suppressed locally."""
    return os.environ.get("AUTORESEARCH_MODAL_QUIET", "1") != "0"


def _validate_gpu() -> dict[str, Any]:
    """Fail fast unless Modal exposed exactly one CUDA GPU."""
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available in the Modal GPU container.")
    device_count = torch.cuda.device_count()
    if device_count != 1:
        raise RuntimeError(f"Expected exactly one visible GPU, found {device_count}.")
    return {
        "device_name": torch.cuda.get_device_name(0),
        "device_count": device_count,
        "capability": torch.cuda.get_device_capability(0),
    }


@app.function(
    image=image,
    cpu=REMOTE_CPU,
    memory=REMOTE_MEMORY_MIB,
    timeout=7200,
    volumes={VOLUME_ROOT: cache_volume},
    env=_forwarded_env_from_client(),
)
def cpu_remote(entrypoint_file: str, extra_args: list[str] | None = None) -> dict[str, Any]:
    """Run a CPU-only entrypoint on Modal."""
    cache_volume.reload()
    proc = _run_python([entrypoint_file, *(extra_args or [])])
    cache_volume.commit()
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


@app.function(
    image=image,
    gpu=GPU_TYPE,
    cpu=REMOTE_CPU,
    memory=REMOTE_MEMORY_MIB,
    timeout=1800,
    volumes={VOLUME_ROOT: cache_volume},
    env=_forwarded_env_from_client(),
)
def gpu_remote(entrypoint_file: str, extra_args: list[str] | None = None) -> dict[str, Any]:
    """Run a GPU entrypoint on Modal."""
    cache_volume.reload()
    gpu_info = _validate_gpu()
    proc = _run_python([entrypoint_file, *(extra_args or [])])
    cache_volume.commit()
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "gpu": gpu_info,
    }


def _write_result(result: dict[str, Any]) -> None:
    """Write stdout/stderr from a remote result to local streams."""
    if result["stdout"]:
        sys.stdout.write(result["stdout"])
        if not result["stdout"].endswith("\n"):
            sys.stdout.write("\n")
    if result["stderr"]:
        sys.stderr.write(result["stderr"])
        if not result["stderr"].endswith("\n"):
            sys.stderr.write("\n")


@app.local_entrypoint()
def main(action: str) -> None:
    """Dispatch to the correct remote function based on the action name."""
    if action not in ENTRYPOINTS:
        valid = ", ".join(sorted(ENTRYPOINTS))
        raise SystemExit(f"Unknown action '{action}'. Valid actions: {valid}")

    spec = ENTRYPOINTS[action]
    extra_args = _extra_args_from_env()
    quiet_mode = _quiet_mode_from_env()

    with modal.enable_output() as output_manager:
        output_manager.set_quiet_mode(quiet_mode)
        if "gpu" in spec:
            result = gpu_remote.remote(spec["file"], extra_args)
        else:
            result = cpu_remote.remote(spec["file"], extra_args)

    _write_result(result)

    if result["returncode"] != 0:
        tail = _tail(
            result["stdout"]
            + ("\n" if result["stdout"] and result["stderr"] else "")
            + result["stderr"]
        )
        if tail:
            sys.stderr.write("\n--- remote tail ---\n")
            sys.stderr.write(tail)
            if not tail.endswith("\n"):
                sys.stderr.write("\n")
        raise SystemExit(result["returncode"])
