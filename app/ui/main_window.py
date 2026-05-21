"""Main application window."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QThread, QTimer
from PySide6.QtGui import QAction, QFontDatabase, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.config import Config
from app.core.logger import get_logger
from app.ui.preview import PreviewWidget
from app.ui.style import STYLE_SHEET
from app.ui.widgets import Card, Heading, SectionLabel, TitleBar, hbox, vbox
from app.ui.workers import AnalyzeWorker, ExportWorker, LyricsWorker, RewriteLyricsWorker
from audio_analyzer import MusicAnalysis
from export_engine import ExportSettings, RESOLUTIONS, detect_gpu_encoder, resolution_pair
from lyrics_generator import LyricsBundle
from project_manager import Project, ProjectManager
from renderer import RenderJob, RenderSettings, render_thumbnail
from spectrum_engine import SpectrumStyle

log = get_logger(__name__)


SPECTRUM_MODES = ["bar", "mirror", "wave", "circular", "rgb", "neon", "dual"]
PALETTE_PRESETS = {
    "Neon Night": ["#00e5ff", "#7c4dff", "#ff4081"],
    "Aurora": ["#84fab0", "#8fd3f4", "#a18cd1"],
    "Fire": ["#ff5722", "#ffeb3b", "#ff00aa"],
    "Cinematic Noir": ["#0d0d23", "#3a0ca3", "#b5179e"],
    "Pastel Dream": ["#a18cd1", "#fbc2eb", "#84fab0"],
}


class MainWindow(QMainWindow):
    def __init__(self, config: Config | None = None) -> None:
        super().__init__()
        self.config = config or Config.load()
        self.setWindowTitle("Spectrum AI")
        self.resize(1480, 880)

        if self.config.get("ui.frameless", True):
            self.setWindowFlags(Qt.FramelessWindowHint)

        self.project_manager = ProjectManager(self.config.path("projects"))
        self.current_project = Project()
        self._analysis: MusicAnalysis | None = None
        self._lyrics: LyricsBundle | None = None
        self._workers: list[QThread] = []

        self._init_ui()
        self._init_shortcuts()
        self._connect_autosave()

        self.setStyleSheet(STYLE_SHEET)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _init_ui(self) -> None:
        container = QWidget(self)
        container.setObjectName("MainContainer")
        self.setCentralWidget(container)

        root_layout = QVBoxLayout(container)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # --- Title bar -------------------------------------------------
        self.title_bar = TitleBar(self)
        self.title_bar.minimize_clicked.connect(self.showMinimized)
        self.title_bar.maximize_clicked.connect(self._toggle_maximize)
        self.title_bar.close_clicked.connect(self.close)
        root_layout.addWidget(self.title_bar)

        # --- Main split: sidebar | center | right panel ----------------
        splitter = QSplitter(Qt.Horizontal, self)
        splitter.setHandleWidth(1)
        root_layout.addWidget(splitter, 1)

        # --- Sidebar (projects) ---------------------------------------
        self.sidebar = self._build_sidebar()
        splitter.addWidget(self.sidebar)

        # --- Center (preview + transport + timeline) ------------------
        self.center_panel = self._build_center()
        splitter.addWidget(self.center_panel)

        # --- Right panel (controls / AI / export) ---------------------
        self.right_panel = self._build_right_panel()
        splitter.addWidget(self.right_panel)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        splitter.setStretchFactor(2, 2)
        splitter.setSizes([220, 880, 380])

        # --- Status bar -----------------------------------------------
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)

        self.lbl_status = QLabel("Siap. Pilih audio untuk mulai.")
        self.lbl_status.setStyleSheet("color: #9a9ac0;")
        self.lbl_fps = QLabel("FPS: -")
        self.lbl_fps.setStyleSheet("color: #9a9ac0; padding-right: 12px;")
        self.lbl_audio_info = QLabel("Audio: -")
        self.lbl_audio_info.setStyleSheet("color: #9a9ac0; padding-right: 12px;")

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedWidth(220)
        self.progress_bar.setVisible(False)

        self.status_bar.addWidget(self.lbl_status, 1)
        self.status_bar.addPermanentWidget(self.lbl_audio_info)
        self.status_bar.addPermanentWidget(self.lbl_fps)
        self.status_bar.addPermanentWidget(self.progress_bar)

    # ----- sidebar ----------------------------------------------------
    def _build_sidebar(self) -> QFrame:
        frame = QFrame(self)
        frame.setObjectName("Sidebar")
        frame.setMinimumWidth(200)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 14, 12, 12)
        layout.setSpacing(8)

        layout.addWidget(Heading("Project"))

        self.btn_new = QPushButton("+  Project baru")
        self.btn_new.setObjectName("AccentButton")
        self.btn_new.clicked.connect(self._on_new_project)
        layout.addWidget(self.btn_new)

        self.btn_open_audio = QPushButton("\U0001F3B5  Pilih audio…")
        self.btn_open_audio.setObjectName("PrimaryButton")
        self.btn_open_audio.clicked.connect(self._on_open_audio)
        layout.addWidget(self.btn_open_audio)

        layout.addWidget(SectionLabel("Project Saved"))
        self.project_list = QListWidget()
        self.project_list.itemDoubleClicked.connect(self._on_load_project)
        layout.addWidget(self.project_list, 1)

        btn_open = QPushButton("Buka project…")
        btn_open.clicked.connect(self._on_open_project_dialog)
        layout.addWidget(btn_open)

        btn_save = QPushButton("Simpan project")
        btn_save.setObjectName("AccentButton")
        btn_save.clicked.connect(self._on_save_project)
        layout.addWidget(btn_save)

        self._refresh_project_list()
        return frame

    def _refresh_project_list(self) -> None:
        self.project_list.clear()
        for path in self.project_manager.list_projects():
            item = QListWidgetItem(path.stem)
            item.setData(Qt.UserRole, str(path))
            self.project_list.addItem(item)

    # ----- center -----------------------------------------------------
    def _build_center(self) -> QWidget:
        wrap = QWidget(self)
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Preview frame
        preview_frame = QFrame()
        preview_frame.setObjectName("PreviewFrame")
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(8, 8, 8, 8)
        self.preview = PreviewWidget(preview_frame)
        self.preview.fps_callback = self._on_preview_fps
        preview_layout.addWidget(self.preview)
        layout.addWidget(preview_frame, 1)

        # Transport
        transport = QFrame()
        transport_layout = QHBoxLayout(transport)
        transport_layout.setContentsMargins(0, 0, 0, 0)
        transport_layout.setSpacing(8)

        self.btn_play = QPushButton("\u25B6  Play")
        self.btn_play.setObjectName("PrimaryButton")
        self.btn_play.clicked.connect(self._toggle_play)

        self.btn_stop = QPushButton("\u25A0  Stop")
        self.btn_stop.clicked.connect(self.preview.stop)

        self.btn_one_click = QPushButton("\u26A1  ONE-CLICK GENERATE")
        self.btn_one_click.setObjectName("PrimaryButton")
        self.btn_one_click.setMinimumHeight(40)
        self.btn_one_click.clicked.connect(self._on_one_click_generate)

        transport_layout.addWidget(self.btn_play)
        transport_layout.addWidget(self.btn_stop)
        transport_layout.addStretch(1)
        transport_layout.addWidget(self.btn_one_click)
        layout.addWidget(transport)

        # Timeline scrub
        scrub_card = Card()
        scrub_layout = QVBoxLayout(scrub_card)
        scrub_layout.setContentsMargins(12, 8, 12, 8)
        scrub_layout.setSpacing(6)
        scrub_layout.addWidget(SectionLabel("Timeline"))
        self.timeline = QSlider(Qt.Horizontal)
        self.timeline.setRange(0, 1000)
        self.timeline.sliderMoved.connect(self._on_timeline_moved)
        scrub_layout.addWidget(self.timeline)
        self.lbl_time = QLabel("00:00 / 00:00")
        self.lbl_time.setStyleSheet("color: #9a9ac0;")
        scrub_layout.addWidget(self.lbl_time, 0, Qt.AlignRight)
        layout.addWidget(scrub_card)

        # Lyric editor preview
        self.lyric_card = Card()
        ll = QVBoxLayout(self.lyric_card)
        ll.setContentsMargins(12, 10, 12, 10)
        ll.setSpacing(6)
        ll.addWidget(SectionLabel("Lirik (editable)"))
        self.lyric_edit = QPlainTextEdit()
        self.lyric_edit.setPlaceholderText("Lirik akan muncul di sini setelah AI generate. Edit langsung untuk customize.")
        self.lyric_edit.setFixedHeight(140)
        ll.addWidget(self.lyric_edit)
        layout.addWidget(self.lyric_card)

        return wrap

    # ----- right panel ------------------------------------------------
    def _build_right_panel(self) -> QFrame:
        frame = QFrame(self)
        frame.setObjectName("RightPanel")
        frame.setMinimumWidth(360)
        outer = QVBoxLayout(frame)
        outer.setContentsMargins(12, 14, 12, 12)
        outer.setSpacing(10)

        tabs = QTabWidget()
        tabs.addTab(self._build_visual_tab(), "Visual")
        tabs.addTab(self._build_ai_tab(), "AI")
        tabs.addTab(self._build_export_tab(), "Export")
        tabs.addTab(self._build_chat_tab(), "Chat AI")
        outer.addWidget(tabs, 1)
        return frame

    def _build_visual_tab(self) -> QWidget:
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(10)

        layout.addWidget(SectionLabel("Mode Spectrum"))
        self.cmb_mode = QComboBox()
        self.cmb_mode.addItems(SPECTRUM_MODES)
        self.cmb_mode.currentTextChanged.connect(self._update_spectrum_style)
        layout.addWidget(self.cmb_mode)

        layout.addWidget(SectionLabel("Palet Warna"))
        self.cmb_palette = QComboBox()
        self.cmb_palette.addItems(PALETTE_PRESETS.keys())
        self.cmb_palette.currentTextChanged.connect(self._update_spectrum_style)
        layout.addWidget(self.cmb_palette)

        layout.addWidget(SectionLabel("Sensitivity"))
        self.sld_sens = QSlider(Qt.Horizontal)
        self.sld_sens.setRange(50, 250)
        self.sld_sens.setValue(120)
        self.sld_sens.valueChanged.connect(self._update_spectrum_style)
        layout.addWidget(self.sld_sens)

        layout.addWidget(SectionLabel("Smoothing"))
        self.sld_smooth = QSlider(Qt.Horizontal)
        self.sld_smooth.setRange(0, 95)
        self.sld_smooth.setValue(80)
        self.sld_smooth.valueChanged.connect(self._update_spectrum_style)
        layout.addWidget(self.sld_smooth)

        layout.addWidget(SectionLabel("Bands"))
        self.spn_bands = QSpinBox()
        self.spn_bands.setRange(16, 256)
        self.spn_bands.setValue(64)
        self.spn_bands.setSingleStep(8)
        self.spn_bands.valueChanged.connect(self._update_spectrum_style)
        layout.addWidget(self.spn_bands)

        self.chk_glow = QCheckBox("Glow")
        self.chk_glow.setChecked(True)
        self.chk_glow.toggled.connect(self._update_spectrum_style)
        layout.addWidget(self.chk_glow)

        self.chk_particles = QCheckBox("Partikel reaktif")
        self.chk_particles.setChecked(True)
        self.chk_particles.toggled.connect(self._update_spectrum_style)
        layout.addWidget(self.chk_particles)

        self.chk_karaoke = QCheckBox("Karaoke lyric sync")
        self.chk_karaoke.setChecked(True)
        self.chk_karaoke.toggled.connect(self._update_spectrum_style)
        layout.addWidget(self.chk_karaoke)

        layout.addStretch(1)
        return wrap

    def _build_ai_tab(self) -> QWidget:
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(10)

        layout.addWidget(SectionLabel("Model Groq"))
        self.cmb_model = QComboBox()
        self.cmb_model.addItems(self.config.get("ai.models_available", []))
        self.cmb_model.setCurrentText(self.config.get("ai.model", "llama-3.3-70b-versatile"))
        layout.addWidget(self.cmb_model)

        layout.addWidget(SectionLabel("Tema Lirik"))
        self.txt_theme = QLineEdit()
        self.txt_theme.setPlaceholderText("misal: kebebasan, malam neon, patah hati…")
        layout.addWidget(self.txt_theme)

        layout.addWidget(SectionLabel("Gaya Visual"))
        self.txt_style = QLineEdit()
        self.txt_style.setPlaceholderText("misal: neon night, pastel dream, cinematic noir")
        layout.addWidget(self.txt_style)

        btn_gen_lyrics = QPushButton("\u2728  Generate lirik")
        btn_gen_lyrics.setObjectName("PrimaryButton")
        btn_gen_lyrics.clicked.connect(self._on_generate_lyrics)
        layout.addWidget(btn_gen_lyrics)

        btn_rewrite = QPushButton("Rewrite lirik (humanize)")
        btn_rewrite.clicked.connect(self._on_rewrite_lyrics)
        layout.addWidget(btn_rewrite)

        layout.addWidget(SectionLabel("Status API"))
        self.lbl_ai_status = QLabel(self._ai_status_text())
        self.lbl_ai_status.setWordWrap(True)
        layout.addWidget(self.lbl_ai_status)

        layout.addStretch(1)
        return wrap

    def _build_export_tab(self) -> QWidget:
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(10)

        layout.addWidget(SectionLabel("Resolusi"))
        self.cmb_res = QComboBox()
        self.cmb_res.addItems(list(RESOLUTIONS.keys()))
        self.cmb_res.setCurrentText("1080p")
        layout.addWidget(self.cmb_res)

        layout.addWidget(SectionLabel("FPS"))
        self.spn_fps = QSpinBox()
        self.spn_fps.setRange(24, 60)
        self.spn_fps.setValue(30)
        layout.addWidget(self.spn_fps)

        layout.addWidget(SectionLabel("GPU Encoder"))
        self.cmb_gpu = QComboBox()
        self.cmb_gpu.addItems(["auto", "cpu", "nvidia", "amd", "intel"])
        layout.addWidget(self.cmb_gpu)

        layout.addWidget(SectionLabel("CRF (kualitas, makin kecil makin bagus)"))
        self.spn_crf = QSpinBox()
        self.spn_crf.setRange(12, 30)
        self.spn_crf.setValue(18)
        layout.addWidget(self.spn_crf)

        self.chk_shorts = QCheckBox("Mode TikTok / Shorts (1080x1920)")
        layout.addWidget(self.chk_shorts)

        layout.addWidget(SectionLabel("Output"))
        self.txt_output = QLineEdit()
        self.txt_output.setPlaceholderText("exports/<auto>.mp4")
        layout.addWidget(self.txt_output)

        btn_browse = QPushButton("Pilih lokasi…")
        btn_browse.clicked.connect(self._on_browse_output)
        layout.addWidget(btn_browse)

        btn_thumb = QPushButton("Generate thumbnail PNG")
        btn_thumb.clicked.connect(self._on_generate_thumbnail)
        layout.addWidget(btn_thumb)

        btn_export = QPushButton("\u25B6  Render & Export")
        btn_export.setObjectName("PrimaryButton")
        btn_export.clicked.connect(self._on_export)
        layout.addWidget(btn_export)

        layout.addStretch(1)
        return wrap

    def _build_chat_tab(self) -> QWidget:
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        layout.addWidget(SectionLabel("Chat AI — kontrol visual via bahasa"))
        self.chat_log = QTextEdit()
        self.chat_log.setReadOnly(True)
        self.chat_log.setPlaceholderText("Contoh: \"buat visualizer EDM neon biru\" lalu tekan Apply.")
        layout.addWidget(self.chat_log, 1)
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Ketik perintah, lalu Enter…")
        self.chat_input.returnPressed.connect(self._on_chat_apply)
        layout.addWidget(self.chat_input)
        btn_apply = QPushButton("Apply")
        btn_apply.setObjectName("AccentButton")
        btn_apply.clicked.connect(self._on_chat_apply)
        layout.addWidget(btn_apply)
        return wrap

    # ------------------------------------------------------------------
    # Shortcuts
    # ------------------------------------------------------------------
    def _init_shortcuts(self) -> None:
        QShortcut(QKeySequence("Space"), self, activated=self._toggle_play)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self._on_save_project)
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self._on_open_audio)
        QShortcut(QKeySequence("Ctrl+R"), self, activated=self._on_export)
        QShortcut(QKeySequence("Ctrl+G"), self, activated=self._on_one_click_generate)

    def _toggle_maximize(self) -> None:
        self.showNormal() if self.isMaximized() else self.showMaximized()

    # ------------------------------------------------------------------
    # Autosave
    # ------------------------------------------------------------------
    def _connect_autosave(self) -> None:
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(60_000)
        self._autosave_timer.timeout.connect(self._do_autosave)
        self._autosave_timer.start()

    def _do_autosave(self) -> None:
        try:
            self._sync_lyrics_from_editor()
            self.project_manager.autosave(self._snapshot_project())
        except Exception as exc:
            log.warning("Autosave failed: %s", exc)

    # ------------------------------------------------------------------
    # Project state
    # ------------------------------------------------------------------
    def _snapshot_project(self) -> Project:
        proj = self.current_project
        proj.audio_path = self._analysis.path if self._analysis else proj.audio_path
        proj.spectrum_style = self._build_style()
        if self._lyrics is not None:
            proj.lyrics = self._lyrics
        proj.render_width, proj.render_height = resolution_pair(self.cmb_res.currentText())
        if self.chk_shorts.isChecked():
            proj.render_width, proj.render_height = 1080, 1920
        proj.fps = self.spn_fps.value()
        proj.karaoke = self.chk_karaoke.isChecked()
        return proj

    def _build_style(self) -> SpectrumStyle:
        palette = PALETTE_PRESETS.get(self.cmb_palette.currentText(), ["#00e5ff", "#7c4dff", "#ff4081"])
        bg_map = {
            "Neon Night": ["#0a0a14", "#1a0a2e"],
            "Aurora": ["#0f1a2e", "#1b3a4b"],
            "Fire": ["#170028", "#3a0ca3"],
            "Cinematic Noir": ["#05050f", "#100a1a"],
            "Pastel Dream": ["#1a0f3d", "#3d246c"],
        }
        bg = bg_map.get(self.cmb_palette.currentText(), ["#0a0a14", "#1a0a2e"])
        return SpectrumStyle(
            mode=self.cmb_mode.currentText(),
            bands=self.spn_bands.value(),
            sensitivity=self.sld_sens.value() / 100.0,
            smoothing=self.sld_smooth.value() / 100.0,
            glow=self.chk_glow.isChecked(),
            motion_blur=0.15,
            palette=list(palette),
            background=bg,
            beat_flash=0.1,
            rgb_split=2.0 if self.cmb_mode.currentText() == "rgb" else 0.0,
            film_grain=0.04,
            vignette=0.3,
            particle_count=60 if self.chk_particles.isChecked() else 0,
        )

    def _build_job(self) -> RenderJob | None:
        if self._analysis is None:
            return None
        settings = RenderSettings(
            width=1920,
            height=1080,
            fps=self.spn_fps.value(),
            karaoke=self.chk_karaoke.isChecked(),
            show_subtitles=bool(self._lyrics and self._lyrics.lines),
        )
        if self.chk_shorts.isChecked():
            settings.width, settings.height = 1080, 1920
        else:
            settings.width, settings.height = resolution_pair(self.cmb_res.currentText())
        return RenderJob(
            analysis=self._analysis,
            lyrics=self._lyrics or LyricsBundle(),
            spectrum_style=self._build_style(),
            settings=settings,
        )

    # ------------------------------------------------------------------
    # Slots — audio / project
    # ------------------------------------------------------------------
    def _on_open_audio(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Pilih audio", "", "Audio (*.mp3 *.wav *.flac *.ogg *.m4a)"
        )
        if not path:
            return
        self._set_status(f"Analisa: {Path(path).name}")
        self._run_analyze(path)

    def _run_analyze(self, path: str) -> None:
        worker = AnalyzeWorker(path)
        thread = worker.start_in_thread()
        worker.finished.connect(self._on_analysis_done)
        worker.failed.connect(self._on_worker_failed)
        worker.progress.connect(self._on_worker_progress)
        worker.finished.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._workers.append(thread)
        thread.start()
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # busy

    def _on_analysis_done(self, analysis: MusicAnalysis) -> None:
        self._analysis = analysis
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.progress_bar.setVisible(False)
        self.lbl_audio_info.setText(
            f"Audio: {Path(analysis.path).name} \u00b7 {analysis.duration:.1f}s \u00b7 "
            f"BPM {analysis.bpm:.0f} \u00b7 {analysis.mood}"
        )
        self._set_status("Analisis selesai. Tekan Play untuk preview, atau Generate lirik.")
        self.timeline.setMaximum(max(1, int(analysis.duration * 10)))
        # auto-pick palette
        if analysis.mood == "energetic":
            self.cmb_palette.setCurrentText("Neon Night")
        elif analysis.mood == "dreamy":
            self.cmb_palette.setCurrentText("Pastel Dream")
        elif analysis.mood == "dark":
            self.cmb_palette.setCurrentText("Cinematic Noir")
        # Refresh preview
        job = self._build_job()
        self.preview.set_job(job)

    def _on_new_project(self) -> None:
        self.current_project = Project()
        self._analysis = None
        self._lyrics = None
        self.preview.set_job(None)
        self.lyric_edit.setPlainText("")
        self.lbl_audio_info.setText("Audio: -")
        self._set_status("Project baru.")

    def _on_save_project(self) -> None:
        self._sync_lyrics_from_editor()
        proj = self._snapshot_project()
        path = self.project_manager.save(proj)
        self._refresh_project_list()
        self._set_status(f"Project disimpan: {path.name}")

    def _on_open_project_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Buka project", str(self.project_manager.projects_dir), "Spectrum AI (*.spxai)")
        if not path:
            return
        self._load_project_from_path(Path(path))

    def _on_load_project(self, item: QListWidgetItem) -> None:
        self._load_project_from_path(Path(item.data(Qt.UserRole)))

    def _load_project_from_path(self, path: Path) -> None:
        try:
            proj = self.project_manager.load(path)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Gagal membuka project: {exc}")
            return
        self.current_project = proj
        self._lyrics = proj.lyrics
        self._apply_project_to_ui(proj)
        if proj.audio_path and Path(proj.audio_path).exists():
            self._run_analyze(proj.audio_path)
        else:
            self._set_status("Project dibuka. Audio tidak ditemukan — pilih audio baru.")

    def _apply_project_to_ui(self, proj: Project) -> None:
        style = proj.spectrum_style
        if style.mode in SPECTRUM_MODES:
            self.cmb_mode.setCurrentText(style.mode)
        self.spn_bands.setValue(style.bands)
        self.sld_sens.setValue(int(style.sensitivity * 100))
        self.sld_smooth.setValue(int(style.smoothing * 100))
        self.chk_glow.setChecked(style.glow)
        self.chk_particles.setChecked(style.particle_count > 0)
        self.chk_karaoke.setChecked(proj.karaoke)
        if proj.lyrics.lines:
            self.lyric_edit.setPlainText("\n".join(line.text for line in proj.lyrics.lines))

    # ------------------------------------------------------------------
    # Lyrics
    # ------------------------------------------------------------------
    def _on_generate_lyrics(self) -> None:
        if self._analysis is None:
            QMessageBox.information(self, "Info", "Pilih audio terlebih dahulu.")
            return
        theme = self.txt_theme.text().strip() or "kebebasan dan harapan"
        style = self.txt_style.text().strip() or None
        self._set_status("Generate lirik dengan AI…")
        worker = LyricsWorker(self._analysis, theme=theme, style=style)
        thread = worker.start_in_thread()
        worker.finished.connect(self._on_lyrics_done)
        worker.failed.connect(self._on_worker_failed)
        worker.progress.connect(self._on_worker_progress)
        worker.finished.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._workers.append(thread)
        thread.start()
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)

    def _on_lyrics_done(self, bundle: LyricsBundle) -> None:
        self._lyrics = bundle
        self.lyric_edit.setPlainText("\n".join(line.text for line in bundle.lines))
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.progress_bar.setVisible(False)
        self._set_status(f"Lirik siap: {bundle.title}")
        job = self._build_job()
        self.preview.set_job(job)

    def _on_rewrite_lyrics(self) -> None:
        if self._lyrics is None or not self._lyrics.lines:
            QMessageBox.information(self, "Info", "Generate lirik dulu sebelum rewrite.")
            return
        self._sync_lyrics_from_editor()
        worker = RewriteLyricsWorker(self._lyrics, instruction="Buat lebih natural dan emosional")
        thread = worker.start_in_thread()
        worker.finished.connect(self._on_lyrics_done)
        worker.failed.connect(self._on_worker_failed)
        worker.progress.connect(self._on_worker_progress)
        worker.finished.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._workers.append(thread)
        thread.start()

    def _sync_lyrics_from_editor(self) -> None:
        if self._lyrics is None:
            return
        edited = [ln.strip() for ln in self.lyric_edit.toPlainText().splitlines() if ln.strip()]
        if not edited:
            return
        for line, new_text in zip(self._lyrics.lines, edited):
            line.text = new_text
            if line.words:
                step = (line.end - line.start) / max(1, len(new_text.split()))
                cursor = line.start
                line.words = []
                from lyrics_generator import LyricWord

                for w in new_text.split():
                    line.words.append(LyricWord(text=w, start=cursor, end=cursor + step))
                    cursor += step

    # ------------------------------------------------------------------
    # Export & thumbnail
    # ------------------------------------------------------------------
    def _on_browse_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Output video", str(self.config.path("exports") / "spectrum.mp4"), "MP4 (*.mp4)"
        )
        if path:
            self.txt_output.setText(path)

    def _on_export(self) -> None:
        job = self._build_job()
        if job is None:
            QMessageBox.information(self, "Info", "Pilih audio dulu.")
            return
        self._sync_lyrics_from_editor()
        job.lyrics = self._lyrics or LyricsBundle()
        # Build output path
        out_text = self.txt_output.text().strip()
        if not out_text:
            stem = (self._lyrics.title if self._lyrics else None) or Path(job.analysis.path).stem
            out_text = str(self.config.path("exports") / f"{stem}.mp4")
            self.txt_output.setText(out_text)
        settings = ExportSettings(
            output_path=Path(out_text),
            codec=detect_gpu_encoder(self.cmb_gpu.currentText()),
            crf=self.spn_crf.value(),
            preset=self.config.get("render.preset", "medium"),
            audio_bitrate=self.config.get("render.audio_bitrate", "192k"),
            gpu=self.cmb_gpu.currentText(),
        )
        worker = ExportWorker(job, settings)
        thread = worker.start_in_thread()
        worker.finished.connect(self._on_export_done)
        worker.failed.connect(self._on_worker_failed)
        worker.progress.connect(self._on_worker_progress)
        worker.finished.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._workers.append(thread)
        thread.start()
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 100)
        self._set_status("Rendering video…")

    def _on_export_done(self, path: str) -> None:
        self.progress_bar.setVisible(False)
        self._set_status(f"Selesai. Video tersimpan: {path}")
        QMessageBox.information(self, "Render selesai", f"Video tersimpan:\n{path}")

    def _on_generate_thumbnail(self) -> None:
        job = self._build_job()
        if job is None:
            QMessageBox.information(self, "Info", "Pilih audio dulu.")
            return
        img = render_thumbnail(job)
        out = self.config.path("exports") / f"thumb_{int(__import__('time').time())}.png"
        import cv2
        cv2.imwrite(str(out), img)
        self._set_status(f"Thumbnail disimpan: {out}")
        QMessageBox.information(self, "Thumbnail", f"Thumbnail disimpan:\n{out}")

    # ------------------------------------------------------------------
    # One-click generate
    # ------------------------------------------------------------------
    def _on_one_click_generate(self) -> None:
        if self._analysis is None:
            self._on_open_audio()
            return
        # Trigger lyric generation; once done, the user just hits Export.
        self._on_generate_lyrics()

    # ------------------------------------------------------------------
    # Chat AI
    # ------------------------------------------------------------------
    def _on_chat_apply(self) -> None:
        text = self.chat_input.text().strip()
        if not text:
            return
        self.chat_log.append(f"<b style='color:#00e5ff'>You:</b> {text}")
        self.chat_input.clear()
        # naive keyword-based handler that flips UI controls
        lowered = text.lower()
        if "neon" in lowered or "edm" in lowered:
            self.cmb_palette.setCurrentText("Neon Night")
            self.cmb_mode.setCurrentText("neon")
        elif "pastel" in lowered or "dreamy" in lowered:
            self.cmb_palette.setCurrentText("Pastel Dream")
            self.cmb_mode.setCurrentText("wave")
        elif "noir" in lowered or "cinematic" in lowered:
            self.cmb_palette.setCurrentText("Cinematic Noir")
            self.cmb_mode.setCurrentText("circular")
        elif "fire" in lowered or "energetic" in lowered:
            self.cmb_palette.setCurrentText("Fire")
            self.cmb_mode.setCurrentText("bar")
        # tweak based on keywords
        if "sensitif" in lowered or "kencang" in lowered:
            self.sld_sens.setValue(min(250, self.sld_sens.value() + 30))
        if "halus" in lowered or "smooth" in lowered:
            self.sld_smooth.setValue(min(95, self.sld_smooth.value() + 10))
        self.chat_log.append("<b style='color:#7c4dff'>AI:</b> Style sudah disesuaikan. Pratinjau diperbarui.")
        self._update_spectrum_style()

    # ------------------------------------------------------------------
    # Misc UI slots
    # ------------------------------------------------------------------
    def _on_timeline_moved(self, value: int) -> None:
        if self._analysis is None:
            return
        ratio = value / max(1, self.timeline.maximum())
        t = ratio * self._analysis.duration
        self.lbl_time.setText(f"{int(t//60):02d}:{int(t%60):02d} / "
                              f"{int(self._analysis.duration//60):02d}:{int(self._analysis.duration%60):02d}")

    def _on_preview_fps(self, fps: float) -> None:
        self.lbl_fps.setText(f"FPS: {fps:.1f}")

    def _toggle_play(self) -> None:
        if self._analysis is None:
            self._on_open_audio()
            return
        if self.preview._paused:  # accessing semi-private for simplicity
            self.preview.play()
            self.btn_play.setText("\u275A\u275A  Pause")
        else:
            self.preview.pause()
            self.btn_play.setText("\u25B6  Play")

    def _update_spectrum_style(self, *args) -> None:
        if self._analysis is None:
            return
        job = self._build_job()
        self.preview.set_job(job)

    def _ai_status_text(self) -> str:
        from ai_engine import AIEngine
        ai = AIEngine(self.config)
        if ai.available:
            return "<span style='color:#7c4dff'>OK</span> \u00b7 Groq API key terdeteksi."
        return ("<span style='color:#ff4081'>Mock mode</span> \u00b7 set env var "
                "<code>GROQ_API_KEY</code> atau isi <code>ai.api_key</code> di "
                "<code>config/settings.json</code>.")

    # ----- worker generic hooks ---------------------------------------
    def _on_worker_progress(self, current: int, total: int, label: str) -> None:
        if total > 0:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(current)
        else:
            self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)
        if label:
            self._set_status(label)

    def _on_worker_failed(self, message: str) -> None:
        self.progress_bar.setVisible(False)
        log.error("Worker failed: %s", message)
        QMessageBox.critical(self, "Error", message)
        self._set_status("Gagal: " + message)

    def _set_status(self, text: str) -> None:
        self.lbl_status.setText(text)
        log.info(text)

    # ------------------------------------------------------------------
    def closeEvent(self, event) -> None:
        try:
            self._sync_lyrics_from_editor()
            self.project_manager.autosave(self._snapshot_project())
        except Exception:
            pass
        super().closeEvent(event)
