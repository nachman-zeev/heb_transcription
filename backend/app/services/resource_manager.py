from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import psutil
import torch

from app.core.config import get_settings


@dataclass
class ResourceSnapshot:
    timestamp: datetime
    cpu_percent: float
    ram_percent: float
    gpu_available: bool
    gpu_memory_used_percent: float
    recommended_workers: int


class ResourceManager:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._max_workers_cpu = max(1, self.settings.max_parallel_workers_cpu)
        self._max_workers_gpu = max(1, self.settings.max_parallel_workers_gpu)

    def snapshot(self) -> ResourceSnapshot:
        cpu = float(psutil.cpu_percent(interval=0.2))
        ram = float(psutil.virtual_memory().percent)
        gpu_avail = bool(torch.cuda.is_available())
        gpu_used_percent = 0.0

        if gpu_avail:
            try:
                free_bytes, total_bytes = torch.cuda.mem_get_info()
                used = max(0.0, float(total_bytes - free_bytes))
                gpu_used_percent = (used / float(total_bytes)) * 100.0 if total_bytes > 0 else 0.0
            except Exception:
                gpu_used_percent = 0.0

        rec = self._recommend_workers(cpu, ram, gpu_avail, gpu_used_percent)
        return ResourceSnapshot(
            timestamp=datetime.now(timezone.utc),
            cpu_percent=cpu,
            ram_percent=ram,
            gpu_available=gpu_avail,
            gpu_memory_used_percent=gpu_used_percent,
            recommended_workers=rec,
        )

    def _recommend_workers(self, cpu: float, ram: float, gpu_available: bool, gpu_used_percent: float) -> int:
        cpu_limit = float(self.settings.cpu_soft_limit_percent)
        ram_limit = float(self.settings.ram_soft_limit_percent)

        if cpu >= cpu_limit or ram >= ram_limit:
            return 1

        if gpu_available:
            if gpu_used_percent >= 85.0:
                return 1
            if gpu_used_percent >= 70.0:
                return max(1, min(self._max_workers_gpu, 2))
            return self._max_workers_gpu

        # CPU-only mode: scale conservatively while still allowing parallelism on strong hosts.
        if cpu <= 55.0 and ram <= 70.0:
            return self._max_workers_cpu

        return max(1, min(self._max_workers_cpu, 2))
