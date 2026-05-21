"""Project save/load + autosave + crash recovery."""
from __future__ import annotations

import json
import shutil
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.core.logger import get_logger
from lyrics_generator import LyricsBundle
from spectrum_engine import SpectrumStyle

log = get_logger(__name__)


PROJECT_VERSION = 1


@dataclass
class Project:
    name: str = "Untitled Project"
    audio_path: str = ""
    background_path: str = ""
    spectrum_style: SpectrumStyle = field(default_factory=SpectrumStyle)
    lyrics: LyricsBundle = field(default_factory=LyricsBundle)
    render_width: int = 1920
    render_height: int = 1080
    fps: int = 30
    subtitle_color: str = "#ffffff"
    subtitle_highlight: str = "#00e5ff"
    subtitle_y_ratio: float = 0.55
    karaoke: bool = True
    show_subtitles: bool = True
    theme: str = "dark-glass"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    version: int = PROJECT_VERSION
    notes: str = ""

    # ----- serialization -------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        # lyrics + spectrum_style already nested dicts via asdict
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Project":
        style_data = data.get("spectrum_style", {})
        lyrics_data = data.get("lyrics", {})
        lyrics = LyricsBundle.from_dict(lyrics_data) if isinstance(lyrics_data, dict) else LyricsBundle()
        style = SpectrumStyle(**{k: v for k, v in style_data.items() if k in SpectrumStyle.__annotations__})
        kwargs = {k: v for k, v in data.items() if k in cls.__annotations__}
        kwargs["spectrum_style"] = style
        kwargs["lyrics"] = lyrics
        return cls(**kwargs)


# Patch LyricsBundle with a from_dict method (project may receive nested dicts)
def _lyrics_from_dict(data: dict[str, Any]) -> LyricsBundle:
    from lyrics_generator import LyricLine, LyricWord

    lines = []
    for line in data.get("lines", []) or []:
        words = [LyricWord(**w) for w in line.get("words", []) or []]
        lines.append(
            LyricLine(
                text=line.get("text", ""),
                start=float(line.get("start", 0.0)),
                end=float(line.get("end", 0.0)),
                words=words,
                kind=line.get("kind", "verse"),
            )
        )
    return LyricsBundle(
        title=data.get("title", "Untitled"),
        description=data.get("description", ""),
        hashtags=list(data.get("hashtags", []) or []),
        thumbnail_text=data.get("thumbnail_text", ""),
        lines=lines,
        mood=data.get("mood", "balanced"),
        palette=list(data.get("palette", []) or []),
        raw_text=data.get("raw_text", ""),
    )


# Inject as classmethod
LyricsBundle.from_dict = classmethod(lambda cls, data: _lyrics_from_dict(data))  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------


class ProjectManager:
    """Owns the on-disk project list under ``/projects``."""

    def __init__(self, projects_dir: Path) -> None:
        self.projects_dir = Path(projects_dir)
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.autosave_dir = self.projects_dir / ".autosave"
        self.autosave_dir.mkdir(parents=True, exist_ok=True)
        self.recovery_dir = self.projects_dir / ".recovery"
        self.recovery_dir.mkdir(parents=True, exist_ok=True)

    # ----- IO -----------------------------------------------------------
    def save(self, project: Project, *, path: Path | None = None) -> Path:
        project.updated_at = time.time()
        target = path or self._path_for(project)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(json.dumps(project.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(target)
        log.info("Saved project: %s", target)
        return target

    def load(self, path: Path) -> Project:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return Project.from_dict(data)

    def list_projects(self) -> list[Path]:
        return sorted(p for p in self.projects_dir.glob("*.spxai") if p.is_file())

    def delete(self, path: Path) -> None:
        Path(path).unlink(missing_ok=True)

    # ----- autosave & crash recovery -----------------------------------
    def autosave(self, project: Project) -> Path:
        return self.save(project, path=self.autosave_dir / "current.spxai")

    def recover(self) -> Project | None:
        candidate = self.autosave_dir / "current.spxai"
        if candidate.exists():
            try:
                return self.load(candidate)
            except Exception as exc:
                log.warning("Recovery failed: %s", exc)
                shutil.move(str(candidate), self.recovery_dir / f"crash_{int(time.time())}.spxai")
        return None

    def clear_autosave(self) -> None:
        for p in self.autosave_dir.glob("*.spxai"):
            p.unlink(missing_ok=True)

    # ----- helpers ------------------------------------------------------
    def _path_for(self, project: Project) -> Path:
        safe = "".join(c for c in project.name if c.isalnum() or c in "-_ ").strip() or "Untitled"
        return self.projects_dir / f"{safe}.spxai"
