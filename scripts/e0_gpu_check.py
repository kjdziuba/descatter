"""E0 step 2: GPU check under the rat-lung exclusive lock and the 25 GB cap.

Writes a JSON blob to stdout. Skips the matmul (and says so) if the lock is held.
"""
from __future__ import annotations

import fcntl
import json
import os
import platform
import socket
import subprocess
import sys
import time
from pathlib import Path

LOCK_PATH = Path.home() / ".cache" / "rat_lung_gpu.lock"
MEM_FRACTION = 25.0 / 32.0  # 25 GB of the 32 GB card


def nvidia_smi_query() -> dict:
    fields = "name,driver_version,memory.total,memory.used,memory.free"
    out = subprocess.run(
        ["nvidia-smi", f"--query-gpu={fields}", "--format=csv,noheader,nounits"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    vals = [v.strip() for v in out.split(",")]
    return {
        "name": vals[0],
        "driver_version": vals[1],
        "vram_total_mib": int(vals[2]),
        "vram_used_mib": int(vals[3]),
        "vram_free_mib": int(vals[4]),
    }


def main() -> int:
    import torch

    info = {
        "host": socket.gethostname(),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "torch_cuda_build": torch.version.cuda,
        "cuda_available": bool(torch.cuda.is_available()),
        "omp_num_threads": os.environ.get("OMP_NUM_THREADS"),
        "nvidia_smi": nvidia_smi_query(),
    }

    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    fh = open(LOCK_PATH, "a+")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        info["lock"] = "HELD_BY_OTHER"
        info["matmul"] = "SKIPPED: rat-lung GPU lock is held by another process"
        print(json.dumps(info, indent=2))
        return 0

    info["lock"] = "ACQUIRED"
    try:
        if not torch.cuda.is_available():
            info["matmul"] = "SKIPPED: torch.cuda.is_available() is False"
        else:
            torch.cuda.set_per_process_memory_fraction(MEM_FRACTION, 0)
            info["memory_fraction_cap"] = MEM_FRACTION
            info["device_name"] = torch.cuda.get_device_name(0)
            info["device_capability"] = list(torch.cuda.get_device_capability(0))
            n = 4096
            a = torch.randn(n, n, device="cuda", dtype=torch.float32)
            b = torch.randn(n, n, device="cuda", dtype=torch.float32)
            torch.cuda.synchronize()
            t0 = time.perf_counter()
            c = a @ b
            torch.cuda.synchronize()
            dt = time.perf_counter() - t0
            info["matmul"] = {
                "shape": [n, n],
                "dtype": "float32",
                "wall_s": round(dt, 6),
                "tflops": round(2 * n**3 / dt / 1e12, 3),
                "checksum": float(c.sum().item()),
                "peak_vram_mib": round(torch.cuda.max_memory_allocated(0) / 2**20, 2),
            }
            del a, b, c
            torch.cuda.empty_cache()
        info["nvidia_smi_after"] = nvidia_smi_query()
    finally:
        fcntl.flock(fh, fcntl.LOCK_UN)
        fh.close()

    print(json.dumps(info, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
