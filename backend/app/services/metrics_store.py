from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class RuntimeMetrics:
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    jobs_completed: int = 0
    jobs_failed: int = 0
    jobs_dead_letter: int = 0
    retries_scheduled: int = 0

    audio_seconds_processed: float = 0.0
    processing_seconds_total: float = 0.0
    estimated_cost_total: float = 0.0

    def record_job_success(self, audio_seconds: float, processing_seconds: float, cost_per_audio_minute: float) -> None:
        self.jobs_completed += 1
        self.audio_seconds_processed += max(0.0, float(audio_seconds))
        self.processing_seconds_total += max(0.0, float(processing_seconds))
        if cost_per_audio_minute > 0:
            self.estimated_cost_total += (max(0.0, float(audio_seconds)) / 60.0) * float(cost_per_audio_minute)

    def snapshot(self, cost_currency: str) -> dict:
        uptime_sec = max(0.001, (datetime.now(timezone.utc) - self.started_at).total_seconds())
        audio_minutes = self.audio_seconds_processed / 60.0
        throughput_audio_minutes_per_hour = (audio_minutes / uptime_sec) * 3600.0

        realtime_factor = 0.0
        if self.processing_seconds_total > 0:
            realtime_factor = self.audio_seconds_processed / self.processing_seconds_total

        return {
            "started_at": self.started_at.isoformat(),
            "uptime_seconds": uptime_sec,
            "jobs_completed_total": self.jobs_completed,
            "jobs_failed_total": self.jobs_failed,
            "jobs_dead_letter_total": self.jobs_dead_letter,
            "retries_scheduled_total": self.retries_scheduled,
            "audio_minutes_processed_total": audio_minutes,
            "processing_seconds_total": self.processing_seconds_total,
            "throughput_audio_minutes_per_hour": throughput_audio_minutes_per_hour,
            "realtime_factor": realtime_factor,
            "estimated_cost_total": self.estimated_cost_total,
            "estimated_cost_currency": cost_currency,
        }

    def as_prometheus(self) -> str:
        snapshot = self.snapshot(cost_currency="USD")
        lines = [
            '# HELP app_uptime_seconds Application uptime in seconds',
            '# TYPE app_uptime_seconds gauge',
            f"app_uptime_seconds {snapshot['uptime_seconds']:.3f}",
            '# HELP app_jobs_completed_total Completed jobs',
            '# TYPE app_jobs_completed_total counter',
            f"app_jobs_completed_total {self.jobs_completed}",
            '# HELP app_jobs_failed_total Failed jobs',
            '# TYPE app_jobs_failed_total counter',
            f"app_jobs_failed_total {self.jobs_failed}",
            '# HELP app_jobs_dead_letter_total Dead letter jobs',
            '# TYPE app_jobs_dead_letter_total counter',
            f"app_jobs_dead_letter_total {self.jobs_dead_letter}",
            '# HELP app_retries_scheduled_total Retries scheduled',
            '# TYPE app_retries_scheduled_total counter',
            f"app_retries_scheduled_total {self.retries_scheduled}",
            '# HELP app_audio_seconds_processed_total Audio seconds processed by workers',
            '# TYPE app_audio_seconds_processed_total counter',
            f"app_audio_seconds_processed_total {self.audio_seconds_processed:.3f}",
            '# HELP app_processing_seconds_total Wall-clock processing seconds spent by workers',
            '# TYPE app_processing_seconds_total counter',
            f"app_processing_seconds_total {self.processing_seconds_total:.3f}",
            '# HELP app_realtime_factor Real-time factor (audio_seconds / processing_seconds)',
            '# TYPE app_realtime_factor gauge',
            f"app_realtime_factor {snapshot['realtime_factor']:.6f}",
            '# HELP app_audio_minutes_per_hour Throughput in audio minutes per hour',
            '# TYPE app_audio_minutes_per_hour gauge',
            f"app_audio_minutes_per_hour {snapshot['throughput_audio_minutes_per_hour']:.6f}",
            '# HELP app_estimated_cost_total Estimated accumulated processing cost',
            '# TYPE app_estimated_cost_total counter',
            f"app_estimated_cost_total {self.estimated_cost_total:.6f}",
        ]
        return "\n".join(lines) + "\n"


runtime_metrics = RuntimeMetrics()
