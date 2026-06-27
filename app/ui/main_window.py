from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QStackedWidget,
    QHBoxLayout, QVBoxLayout, QLabel
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from ui.theme import (
    BG_APP, DOT_RED, DOT_YELLOW, DOT_GREEN,
    WINDOW_WIDTH, WINDOW_HEIGHT,
    titlebar_style, app_style, credit_style,
    TEXT_GHOST, FONT_XS
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AnimeRS")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(app_style())

        root = QWidget()
        root.setObjectName("central")
        self.setCentralWidget(root)

        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        titlebar = QWidget()
        titlebar.setObjectName("titlebar")
        titlebar.setFixedHeight(44)
        titlebar.setStyleSheet(titlebar_style())

        tb_layout = QHBoxLayout(titlebar)
        tb_layout.setContentsMargins(16, 0, 16, 0)
        tb_layout.setSpacing(8)

        for color in (DOT_RED, DOT_YELLOW, DOT_GREEN):
            dot = QLabel()
            dot.setFixedSize(12, 12)
            dot.setStyleSheet(f"""
                QLabel {{
                    background: {color};
                    border-radius: 6px;
                }}
            """)
            tb_layout.addWidget(dot)

        tb_layout.addStretch()

        title_label = QLabel("AnimeRS")
        title_label.setObjectName("titlebar_label")
        tb_layout.addWidget(title_label)

        tb_layout.addStretch()

        # placeholder to balance the dots on the right side
        spacer = QWidget()
        spacer.setFixedWidth(12 * 3 + (8 * 2))  # 3 dots + 2 gaps
        tb_layout.addWidget(spacer)

        root_layout.addWidget(titlebar)

        self.stack = QStackedWidget()
        root_layout.addWidget(self.stack, stretch=1)

        credit_bar = QWidget()
        credit_bar.setStyleSheet(f"background: {BG_APP};")
        credit_layout = QHBoxLayout(credit_bar)
        credit_layout.setContentsMargins(16, 6, 16, 10)

        credit_label = QLabel("Developed by 111yoav111")
        credit_label.setStyleSheet(credit_style())
        credit_layout.addWidget(credit_label, alignment=Qt.AlignmentFlag.AlignLeft)

        root_layout.addWidget(credit_bar)

    def show_screen(self, index: int) -> None:
        """
        Switch the visible screen by stack index.
        0 = upload screen, 1 = result screen.
        """
        self.stack.setCurrentIndex(index)
