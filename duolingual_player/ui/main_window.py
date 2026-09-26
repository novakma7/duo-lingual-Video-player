from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QPlainTextEdit,
)

from duolingual_player.core.controller import PlaybackController
from duolingual_player.core.models import MediaInfo, PlaybackState

from .video_widget import VideoWidget


def format_time(seconds: float) -> str:
    value = max(0, int(seconds))
    hours, remainder = divmod(value, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


class AudioRouteBox(QGroupBox):
    def __init__(self, channel: str, parent=None) -> None:
        super().__init__(f"Výstup {channel}", parent)
        self.track = QComboBox()
        self.track.setToolTip(f"Stopa pro výstup {channel}")
        self.device = QComboBox()
        self.device.setToolTip(f"WASAPI / zvukové zařízení pro výstup {channel}")
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 150)
        self.volume.setValue(100)
        self.volume_label = QLabel("100 %")
        volume_row = QHBoxLayout()
        volume_row.addWidget(self.volume, 1)
        volume_row.addWidget(self.volume_label)
        self.offset = QSpinBox()
        self.offset.setRange(-5000, 5000)
        self.offset.setSingleStep(10)
        self.offset.setSuffix(" ms")
        self.offset.setToolTip("Kladná hodnota zvuk zpozdí, záporná jej předsune.")
        layout = QFormLayout(self)
        layout.addRow("Zvuková stopa:", self.track)
        layout.addRow("Zařízení:", self.device)
        layout.addRow("Hlasitost:", volume_row)
        layout.addRow("Synchronizace:", self.offset)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("DuoLingual Player")
        self.resize(1280, 780)
        self.setMinimumSize(900, 600)
        self.controller = PlaybackController()
        self._updating = False
        self._slider_dragging = False
        self._fullscreen = False
        self._external_subtitle_path: str | None = None
        self._build_ui()
        self._connect_signals()
        self._install_shortcuts()
        self._apply_style()
        self._devices_changed(self.controller.devices)

    def _build_ui(self) -> None:
        self.video = VideoWidget()
        self.open_button = QPushButton("Otevřít MKV")
        self.play_button = QToolButton()
        self.play_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.play_button.setToolTip("Přehrát / pauza (mezerník)")
        self.stop_button = QToolButton()
        self.stop_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self.stop_button.setToolTip("Zastavit")
        self.timeline = QSlider(Qt.Orientation.Horizontal)
        self.timeline.setRange(0, 0)
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setMinimumWidth(115)

        controls = QHBoxLayout()
        controls.setContentsMargins(8, 8, 8, 8)
        controls.addWidget(self.open_button)
        controls.addWidget(self.play_button)
        controls.addWidget(self.stop_button)
        controls.addWidget(self.timeline, 1)
        controls.addWidget(self.time_label)
        self.controls_widget = QWidget()
        self.controls_widget.setLayout(controls)

        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self.video, 1)
        left_layout.addWidget(self.controls_widget)
        left = QWidget()
        left.setLayout(left_layout)

        self.route_a = AudioRouteBox("A")
        self.route_b = AudioRouteBox("B")
        self.refresh_devices_button = QPushButton("Obnovit zvuková zařízení")
        self.route_hint = QLabel(
            "Pro oddělený poslech vyberte dvě různé jazykové stopy a dvě různá "
            "výstupní zařízení. VoiceMeeter vstupy se zobrazí stejně jako ostatní výstupy."
        )
        self.route_hint.setWordWrap(True)
        self.route_hint.setObjectName("hint")

        subtitle_box = QGroupBox("Titulky")
        subtitle_layout = QVBoxLayout(subtitle_box)
        self.subtitle_combo = QComboBox()
        self.subtitle_combo.addItem("Vypnuto", None)
        self.external_subtitle_button = QPushButton("Načíst externí SRT…")
        subtitle_layout.addWidget(self.subtitle_combo)
        subtitle_layout.addWidget(self.external_subtitle_button)

        diagnostics_box = QGroupBox("Diagnostika")
        diagnostics_layout = QVBoxLayout(diagnostics_box)
        self.diagnostics = QPlainTextEdit()
        self.diagnostics.setReadOnly(True)
        self.diagnostics.setMaximumBlockCount(30)
        self.diagnostics.setMinimumHeight(190)
        self.diagnostics.setPlainText("Čekám na otevření média…")
        diagnostics_layout.addWidget(self.diagnostics)

        side_layout = QVBoxLayout()
        side_layout.addWidget(self.route_hint)
        side_layout.addWidget(self.route_a)
        side_layout.addWidget(self.route_b)
        side_layout.addWidget(self.refresh_devices_button)
        side_layout.addWidget(subtitle_box)
        side_layout.addWidget(diagnostics_box)
        side_layout.addStretch()
        side_content = QWidget()
        side_content.setLayout(side_layout)
        self.side_scroll = QScrollArea()
        self.side_scroll.setWidgetResizable(True)
        self.side_scroll.setWidget(side_content)
        self.side_scroll.setMinimumWidth(350)
        self.side_scroll.setMaximumWidth(460)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(left)
        self.splitter.addWidget(self.side_scroll)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.setCentralWidget(self.splitter)
        self.statusBar().showMessage("Připraveno – otevřete soubor MKV.")

        file_menu = self.menuBar().addMenu("Soubor")
        open_action = QAction("Otevřít…", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)
        file_menu.addSeparator()
        quit_action = QAction("Ukončit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)
        view_menu = self.menuBar().addMenu("Zobrazení")
        self.fullscreen_action = QAction("Celá obrazovka", self)
        self.fullscreen_action.setCheckable(True)
        self.fullscreen_action.setShortcut("F")
        self.fullscreen_action.triggered.connect(self.toggle_fullscreen)
        view_menu.addAction(self.fullscreen_action)
        self.smoothing_action = QAction("Vyhlazení obrazu", self)
        self.smoothing_action.setCheckable(True)
        self.smoothing_action.setChecked(True)
        self.smoothing_action.setToolTip(
            "Jemnější interpolace při zvětšování videa; může mírně zvýšit zatížení GPU/CPU."
        )
        self.smoothing_action.toggled.connect(self._set_video_smoothing)
        view_menu.addAction(self.smoothing_action)

    def _connect_signals(self) -> None:
        self.open_button.clicked.connect(self.open_file)
        self.video.fullscreen_requested.connect(self.toggle_fullscreen)
        self.play_button.clicked.connect(self.controller.play_pause)
        self.stop_button.clicked.connect(self.controller.stop)
        self.refresh_devices_button.clicked.connect(self.controller.refresh_devices)
        self.timeline.sliderPressed.connect(lambda: setattr(self, "_slider_dragging", True))
        self.timeline.sliderReleased.connect(self._seek_from_slider)
        self.timeline.sliderMoved.connect(self._preview_seek)
        self.route_a.track.currentIndexChanged.connect(self._routes_edited)
        self.route_b.track.currentIndexChanged.connect(self._routes_edited)
        self.route_a.device.currentIndexChanged.connect(self._routes_edited)
        self.route_b.device.currentIndexChanged.connect(self._routes_edited)
        for channel, box in (("A", self.route_a), ("B", self.route_b)):
            box.volume.valueChanged.connect(
                lambda value, ch=channel, widget=box: self._volume_changed(ch, widget, value)
            )
            box.offset.valueChanged.connect(
                lambda value, ch=channel: self.controller.set_offset(ch, value)
            )
        self.subtitle_combo.currentIndexChanged.connect(self._subtitle_selected)
        self.external_subtitle_button.clicked.connect(self._load_external_subtitle)

        self.controller.media_loaded.connect(self._media_loaded)
        self.controller.devices_changed.connect(self._devices_changed)
        self.controller.frame_ready.connect(lambda frame, _pts: self.video.set_frame(frame))
        self.controller.subtitle_changed.connect(self.video.set_subtitle)
        self.controller.position_changed.connect(self._position_changed)
        self.controller.state_changed.connect(self._state_changed)
        self.controller.diagnostics_changed.connect(self.diagnostics.setPlainText)
        self.controller.error_occurred.connect(self._show_error)
        self.controller.routes_changed.connect(self._sync_route_selections)

    def _install_shortcuts(self) -> None:
        shortcuts = [
            ("Space", self.controller.play_pause),
            ("Left", lambda: self.controller.jump(-5)),
            ("Right", lambda: self.controller.jump(5)),
            ("Shift+Left", lambda: self.controller.jump(-30)),
            ("Shift+Right", lambda: self.controller.jump(30)),
            ("M", self._toggle_mute),
            ("Escape", self._leave_fullscreen),
        ]
        self._shortcuts = []
        for key, callback in shortcuts:
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(callback)
            self._shortcuts.append(shortcut)

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #151922; color: #e5e7eb; }
            QMenuBar, QMenu { background: #202633; }
            QGroupBox { border: 1px solid #394150; border-radius: 6px; margin-top: 12px; padding-top: 8px; font-weight: 600; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
            QPushButton, QToolButton, QComboBox, QSpinBox { background: #293142; border: 1px solid #475569; border-radius: 4px; padding: 6px; }
            QPushButton:hover, QToolButton:hover { background: #354158; }
            QComboBox QAbstractItemView { background: #202633; color: #e5e7eb; selection-background-color: #2563eb; }
            QPlainTextEdit { background: #0f131b; border: 1px solid #394150; font-family: Consolas; font-size: 11px; }
            QSlider::groove:horizontal { height: 5px; background: #394150; border-radius: 2px; }
            QSlider::handle:horizontal { width: 14px; margin: -5px 0; background: #60a5fa; border-radius: 7px; }
            QLabel#hint { color: #bfdbfe; background: #172554; border: 1px solid #1d4ed8; border-radius: 6px; padding: 9px; }
            QStatusBar { background: #202633; }
            """
        )

    def open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Otevřít video", str(Path.home()), "Matroska video (*.mkv);;Všechna média (*.*)"
        )
        if path:
            self.statusBar().showMessage(f"Načítám {Path(path).name}…")
            self.controller.open_media(path)

    def _media_loaded(self, info: MediaInfo) -> None:
        self._updating = True
        try:
            for box in (self.route_a, self.route_b):
                box.track.clear()
                box.track.addItem("— nevybráno —", None)
                for track in info.audio_tracks:
                    box.track.addItem(track.label, track.index)
            self.subtitle_combo.clear()
            self.subtitle_combo.addItem("Vypnuto", None)
            for track in info.subtitle_tracks:
                self.subtitle_combo.addItem(track.label, track.index)
            self.timeline.setRange(0, max(0, int(info.duration * 1000)))
        finally:
            self._updating = False
        self._sync_route_selections(
            (self.controller.track_a, self.controller.track_b, self.controller.device_a, self.controller.device_b)
        )
        self.video.clear_frame()
        self.video.set_message(f"{info.path.name}\n\nStiskněte mezerník nebo tlačítko Přehrát.")
        self.setWindowTitle(f"{info.path.name} – DuoLingual Player")
        self.statusBar().showMessage(
            f"Načteno: {len(info.audio_tracks)} zvukových a {len(info.subtitle_tracks)} titulkových stop."
        )

    def _devices_changed(self, devices: list) -> None:
        self._updating = True
        try:
            for box in (self.route_a, self.route_b):
                box.device.clear()
                box.device.addItem("— nevybráno —", None)
                for device in devices:
                    box.device.addItem(device.label, device.index)
        finally:
            self._updating = False
        self._sync_route_selections(
            (self.controller.track_a, self.controller.track_b, self.controller.device_a, self.controller.device_b)
        )
        self.statusBar().showMessage(f"Nalezeno {len(devices)} výstupních zvukových zařízení.", 5000)

    def _sync_route_selections(self, routes: tuple) -> None:
        self._updating = True
        try:
            for combo, value in (
                (self.route_a.track, routes[0]),
                (self.route_b.track, routes[1]),
                (self.route_a.device, routes[2]),
                (self.route_b.device, routes[3]),
            ):
                index = combo.findData(value)
                combo.setCurrentIndex(max(0, index))
        finally:
            self._updating = False

    def _routes_edited(self) -> None:
        if self._updating:
            return
        self.controller.set_tracks(self.route_a.track.currentData(), self.route_b.track.currentData())
        self.controller.set_devices(self.route_a.device.currentData(), self.route_b.device.currentData())

    def _volume_changed(self, channel: str, box: AudioRouteBox, value: int) -> None:
        box.volume_label.setText(f"{value} %")
        self.controller.set_volume(channel, value / 100)

    def _position_changed(self, position: float, duration: float) -> None:
        if not self._slider_dragging:
            self.timeline.setValue(int(position * 1000))
            self.time_label.setText(f"{format_time(position)} / {format_time(duration)}")

    def _preview_seek(self, value: int) -> None:
        duration = self.controller.info.duration if self.controller.info else 0
        self.time_label.setText(f"{format_time(value / 1000)} / {format_time(duration)}")

    def _seek_from_slider(self) -> None:
        self._slider_dragging = False
        self.controller.seek(self.timeline.value() / 1000)

    def _state_changed(self, state: PlaybackState) -> None:
        icon = (
            QStyle.StandardPixmap.SP_MediaPause
            if state == PlaybackState.PLAYING
            else QStyle.StandardPixmap.SP_MediaPlay
        )
        self.play_button.setIcon(self.style().standardIcon(icon))
        self.statusBar().showMessage(f"Stav: {state.value}")

    def _subtitle_selected(self) -> None:
        if self._updating:
            return
        stream_index = self.subtitle_combo.currentData()
        if stream_index is None:
            self.controller.set_subtitle_off()
        elif stream_index == "external" and self._external_subtitle_path:
            self.controller.load_external_subtitle(self._external_subtitle_path)
        else:
            self.controller.load_embedded_subtitle(stream_index)

    def _load_external_subtitle(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Načíst externí titulky", str(Path.home()), "SubRip titulky (*.srt)"
        )
        if path:
            self._external_subtitle_path = path
            self.controller.load_external_subtitle(path)
            self._updating = True
            self.subtitle_combo.addItem(f"Externí: {Path(path).name}", "external")
            self.subtitle_combo.setCurrentIndex(self.subtitle_combo.count() - 1)
            self._updating = False

    def _show_error(self, message: str) -> None:
        self.statusBar().showMessage(message, 10000)
        QMessageBox.warning(self, "DuoLingual Player", message)

    def _toggle_mute(self) -> None:
        muted = self.controller.toggle_mute()
        self.statusBar().showMessage("Zvuk ztlumen" if muted else "Zvuk obnoven", 3000)

    def _set_video_smoothing(self, enabled: bool) -> None:
        self.video.set_smoothing(enabled)
        state = "zapnuto" if enabled else "vypnuto"
        self.statusBar().showMessage(f"Vyhlazení obrazu: {state}", 3000)

    def toggle_fullscreen(self) -> None:
        if self._fullscreen:
            self._leave_fullscreen()
            return
        self._fullscreen = True
        self.fullscreen_action.setChecked(True)
        self.side_scroll.hide()
        self.controls_widget.hide()
        self.menuBar().hide()
        self.statusBar().hide()
        self.showFullScreen()

    def _leave_fullscreen(self) -> None:
        if not self._fullscreen:
            return
        self._fullscreen = False
        self.fullscreen_action.setChecked(False)
        self.showNormal()
        self.side_scroll.show()
        self.controls_widget.show()
        self.menuBar().show()
        self.statusBar().show()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.controller.shutdown()
        event.accept()

