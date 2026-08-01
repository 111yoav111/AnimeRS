from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
)
from PyQt6.QtCore import Qt

from ui import theme
from ui.background_paint import load_pixmap

_ICON_PATH = Path(__file__).parent / "assets" / "app_icon.png"

REPO_URL = "https://github.com/111yoav111/AnimeRS"
LICENSE_URL = f"{REPO_URL}/blob/main/LICENSE"


def _link(url: str, text: str) -> str:
    return f'<a href="{url}" style="color: {theme.ACCENT}; text-decoration: none;">{text}</a>'


def _brw_links_label(html: str, color: str, size: int) -> QLabel:
    """
    Label for links that open in user browser.
    """
    label = QLabel(html)
    label.setWordWrap(True)
    label.setTextFormat(Qt.TextFormat.RichText)
    label.setOpenExternalLinks(True)
    label.setStyleSheet(f"color: {color}; font-size: {size}px; background: transparent;")
    return label


class AboutDialog(QDialog):
    """
    Small box about this project opened from the title bar, via the "i" btn.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About AnimeRS")
        self.setFixedSize(340, 270)
        self.setStyleSheet(f"background: {theme.BG_APP}; color: {theme.TEXT_PRIMARY};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Header - icon next to the name/tagline
        header = QHBoxLayout()
        header.setSpacing(12)

        icon_pixmap = load_pixmap(_ICON_PATH)
        if icon_pixmap is not None:
            icon_label = QLabel()
            icon_label.setPixmap(icon_pixmap.scaled(
                48, 48,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
            icon_label.setFixedSize(48, 48)
            header.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignTop)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        name = QLabel("AnimeRS")
        name.setStyleSheet(f"font-size: {theme.FONT_XL}px; font-weight: 600; color: {theme.TEXT_PRIMARY};")
        title_box.addWidget(name)

        tagline = QLabel("Anime Reverse Searcher")
        tagline.setStyleSheet(f"color: {theme.TEXT_FAINT}; font-size: {theme.FONT_SM}px;")
        title_box.addWidget(tagline)

        header.addLayout(title_box, stretch=1)
        layout.addLayout(header)

        developed_by = _brw_links_label(
            "Developed by " + _link("https://github.com/111yoav111", "111yoav111"),
            theme.TEXT_DEV, theme.FONT_SM,
        )
        layout.addWidget(developed_by)

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background: {theme.BORDER_SUBTLE};")
        layout.addWidget(divider)

        credits = _brw_links_label(
            "Scene matching by " + _link("https://trace.moe", "trace.moe") + "<br>"
            "Artwork &amp; metadata from " + _link("https://anilist.co", "AniList"),
            theme.TEXT_MUTED, theme.FONT_SM,
        )
        layout.addWidget(credits)

        layout.addStretch()

        license_label = _brw_links_label(
            _link(LICENSE_URL, "GPL-3.0") + " licensed &#183; "
            + _link(REPO_URL, "source on GitHub"),
            theme.TEXT_FAINT, theme.FONT_XS,
        )
        layout.addWidget(license_label)

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(theme.browse_btn_style())
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
