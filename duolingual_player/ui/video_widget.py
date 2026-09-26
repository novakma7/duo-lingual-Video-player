from __future__ import annotations

import numpy as np
from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QMouseEvent, QPainter, QPixmap
from PySide6.QtWidgets import QWidget


class VideoWidget(QWidget):
    fullscreen_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(640, 360)
        self.setStyleSheet("background: #090b10;")
        self._pixmap: QPixmap | None = None
        self._subtitle = ""
        self._smoothing = True
        self._message = (
            "Open an MKV file\n\n"
            "For two languages, select two different audio tracks\n"
            "and two different outputs in the panel on the right."
        )

    def set_frame(self, rgb: np.ndarray) -> None:
        height, width, channels = rgb.shape
        image = QImage(
            rgb.data, width, height, channels * width, QImage.Format.Format_RGB888
        ).copy()
        self._pixmap = QPixmap.fromImage(image)
        self._message = ""
        self.update()

    def set_subtitle(self, text: str) -> None:
        self._subtitle = text
        self.update()

    def set_message(self, text: str) -> None:
        self._message = text
        self.update()

    def clear_frame(self) -> None:
        self._pixmap = None
        self.update()

    def set_smoothing(self, enabled: bool) -> None:
        self._smoothing = bool(enabled)
        self.update()

    @property
    def smoothing(self) -> bool:
        return self._smoothing

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.fullscreen_requested.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#090b10"))
        if self._pixmap is not None:
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, self._smoothing)
            target = self._pixmap.size()
            target.scale(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
            x = (self.width() - target.width()) // 2
            y = (self.height() - target.height()) // 2
            painter.drawPixmap(QRect(x, y, target.width(), target.height()), self._pixmap)
        if self._message:
            painter.setPen(QColor("#cbd5e1"))
            painter.setFont(QFont("Segoe UI", 13))
            painter.drawText(
                self.rect().adjusted(30, 30, -30, -30),
                Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                self._message,
            )
        if self._subtitle:
            painter.setFont(QFont("Segoe UI", 16, QFont.Weight.DemiBold))
            metrics = painter.fontMetrics()
            area = QRect(40, 0, max(0, self.width() - 80), self.height() - 28)
            bounds = metrics.boundingRect(
                area,
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom | Qt.TextFlag.TextWordWrap,
                self._subtitle,
            ).adjusted(-12, -7, 12, 7)
            painter.fillRect(bounds, QColor(0, 0, 0, 180))
            painter.setPen(Qt.GlobalColor.white)
            painter.drawText(
                area,
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom | Qt.TextFlag.TextWordWrap,
                self._subtitle,
            )
