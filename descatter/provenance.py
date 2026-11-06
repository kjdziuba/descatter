"""Run provenance: every run writes results/<exp>/<run_id>/run.json (see CLAUDE.md)."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent


def git_state() -> dict[str, Any]:
    def run(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()

    try:
        return {
            "commit": run("rev-parse", "HEAD"),
            "branch": run("rev-parse", "--abbrev-ref", "HEAD"),
            "dirty": bool(run("status", "--porcelain")),
        }
    except Exception as exc:  # pragma: no cover - only if git is unavailable
        return {"commit": None, "branch": None, "dirty": None, "error": repr(exc)}


def sha256(path: str | Path, chunk: int = 1 << 22) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while block := fh.read(chunk):
            h.update(block)
    return h.hexdigest()


def library_versions() -> dict[str, str | None]:
    out: dict[str, str | None] = {"python": platform.python_version()}
    for mod in ("numpy", "scipy", "h5py", "matplotlib", "torch", "miepython", "dynesty", "emcee"):
        try:
            out[mod] = __import__(mod).__version__
        except Exception:
            out[mod] = None
    return out


def peak_vram_mib() -> float | None:
    try:
        import torch

        if torch.cuda.is_available() and torch.cuda.max_memory_allocated() > 0:
            return round(torch.cuda.max_memory_allocated() / 2**20, 2)
    except Exception:
        pass
    return None


class Run:
    """Context manager that writes run.json on exit.

    with Run("e0", "inspect_raw_core", config={...}) as run:
        run.add_data_file(path)
        ...
    """

    def __init__(
        self,
        exp: str,
        run_id: str,
        config: dict[str, Any] | None = None,
        seeds: dict[str, int] | None = None,
        results_root: Path | None = None,
    ) -> None:
        self.exp = exp
        self.run_id = run_id
        self.config = config or {}
        self.seeds = seeds or {}
        root = results_root or (REPO_ROOT / "results")
        self.dir = root / exp / run_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.data_files: list[dict[str, Any]] = []
        self.notes: dict[str, Any] = {}
        self._t0 = 0.0

    def add_data_file(self, path: str | Path, with_hash: bool = True) -> None:
        p = Path(path)
        self.data_files.append(
            {
                "path": str(p),
                "bytes": p.stat().st_size,
                "sha256": sha256(p) if with_hash else None,
            }
        )

    def __enter__(self) -> "Run":
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        payload = {
            "exp": self.exp,
            "run_id": self.run_id,
            "git": git_state(),
            "config": self.config,
            "data_files": self.data_files,
            "seeds": self.seeds,
            "host": socket.gethostname(),
            "platform": platform.platform(),
            "libraries": library_versions(),
            "env": {
                k: os.environ.get(k)
                for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")
            },
            "wall_time_s": round(time.perf_counter() - self._t0, 3),
            "peak_vram_mib": peak_vram_mib(),
            "status": "ok" if exc_type is None else f"failed: {exc_type.__name__}: {exc}",
            "notes": self.notes,
            "argv": sys.argv,
        }
        (self.dir / "run.json").write_text(json.dumps(payload, indent=2) + "\n")
        return False
