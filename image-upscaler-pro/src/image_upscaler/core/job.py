"""Job dataclass shared between UI and worker."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..constants import JOB_STATUS_PENDING


@dataclass
class Job:
    input_path: Path
    output_path: Path | None = None
    status: str = JOB_STATUS_PENDING
    message: str = ""
    progress: float = 0.0
    width: int = 0
    height: int = 0
    in_size_bytes: int = 0
    out_size_bytes: int = 0
    duration_s: float = 0.0
    job_id: str = field(default_factory=lambda: "")

    @property
    def display_name(self) -> str:
        return self.input_path.name
