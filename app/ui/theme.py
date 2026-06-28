"""
AnimeRS UI Theme

Source of every color, size, radius etc...
All UI files import from here - nothing is hardcoded elsewhere.
"""
 
# Backgrounds
BG_APP        = "#0d0d0f"   # main window / titlebar
BG_SURFACE    = "#111115"   # drop zone, result card
BG_SURFACE_2  = "#141418"   # result hero section
BG_ELEVATED   = "#1a1a22"   # browse btn, frame dots, stat boxes
BG_ELEVATED_2 = "#13131a"   # drop zone hover, active frame dot bg
BG_HOVER      = "#222230"   # button hover
 
# Borders
BORDER_SUBTLE  = "#1e1e24"  # app border, titlebar separator, card border
BORDER_DEFAULT = "#2a2a35"  # browse btn, frame dots
BORDER_ACCENT  = "#7F77DD"  # drop zone hover, progress, frame dot done/active
 
# Accent — purple
ACCENT         = "#7F77DD"  # progress bar, similarity bar, active dots
 
# Text
TEXT_PRIMARY   = "#e8e8f0"  # anime title, headings
TEXT_SECONDARY = "#c0c0d0"  # stat values
TEXT_MUTED     = "#aaa"     # browse btn, back btn hover
TEXT_DIM       = "#666"     # progress label, browse btn default
TEXT_FAINT     = "#555"     # drop sub, back btn default
TEXT_GHOST     = "#444"     # titlebar label, native title, stat labels, divider
TEXT_DEEP      = "#3e3e50"  # stat sub, drop icon default
 
# Badge - episode (purple tint)
BADGE_EP_BG     = "#1a1a28"
BADGE_EP_BORDER = "#3C3489"
BADGE_EP_TEXT   = "#AFA9EC"
 
# Badge - timestamp (green tint)
BADGE_TS_BG     = "#1a1f1a"
BADGE_TS_BORDER = "#0F6E56"
BADGE_TS_TEXT   = "#5DCAA5"
 
# Badge - timestamp range (neutral)
BADGE_RANGE_BG     = "#151515"
BADGE_RANGE_BORDER = "#2a2a35"
BADGE_RANGE_TEXT   = "#888"
 
# Confidence - high (green)
CONFIDENCE_BG     = "#0f1f17"
CONFIDENCE_BORDER = "#1D9E75"
CONFIDENCE_TEXT   = "#1D9E75"
 
# Confidence - low (muted yellow)
CONFIDENCE_LOW_BG     = "#1a1a10"
CONFIDENCE_LOW_BORDER = "#6e6210"
CONFIDENCE_LOW_TEXT   = "#b0a030"
 
# Titlebar dots (macOS style)
DOT_RED    = "#ff5f57"
DOT_YELLOW = "#febc2e"
DOT_GREEN  = "#28c840"
 
 
 
WINDOW_WIDTH  = 480
WINDOW_HEIGHT = 620
 
RADIUS_APP     = 16
RADIUS_CARD    = 16
RADIUS_BTN     = 8
RADIUS_STAT    = 10
RADIUS_DOT_BTN = 6   # frame dots
 
BORDER_WIDTH = 1
 
COVER_W = 72
COVER_H = 100
 
 
# Size
FONT_FAMILY = "Inter, Segoe UI, SF Pro Display, Arial, sans-serif"
 
FONT_XS  = 11
FONT_SM  = 12
FONT_MD  = 13
FONT_BASE = 14
FONT_LG  = 18
FONT_XL  = 20
FONT_2XL = 24
 


def app_style() -> str:
    return f"""
        QMainWindow {{
            background: {BG_APP};
        }}
        QWidget#central {{
            background: {BG_APP};
            border: {BORDER_WIDTH}px solid {BORDER_SUBTLE};
            border-radius: {RADIUS_APP}px;
        }}
    """
 
def titlebar_style() -> str:
    return f"""
        QWidget#titlebar {{
            background: {BG_APP};
            border-bottom: 1px solid {BORDER_SUBTLE};
        }}
        QLabel#titlebar_label {{
            color: {TEXT_GHOST};
            font-size: {FONT_MD}px;
            letter-spacing: 1px;
        }}
    """
 
def drop_zone_style(hover: bool = False) -> str:
    border_color = BORDER_ACCENT if hover else BORDER_DEFAULT
    bg           = BG_ELEVATED_2 if hover else BG_SURFACE
    return f"""
        QFrame#drop_zone {{
            background: {bg};
            border: 2px dashed {border_color};
            border-radius: {RADIUS_CARD}px;
        }}
    """
 
def browse_btn_style() -> str:
    return f"""
        QPushButton {{
            background: {BG_ELEVATED};
            border: 1px solid {BORDER_DEFAULT};
            border-radius: {RADIUS_BTN}px;
            padding: 10px 28px;
            color: {TEXT_MUTED};
            font-size: {FONT_BASE}px;
        }}
        QPushButton:hover {{
            background: {BG_HOVER};
            color: {TEXT_PRIMARY};
        }}
    """
 
def progress_bar_style() -> str:
    return f"""
        QProgressBar {{
            background: {BORDER_SUBTLE};
            border: none;
            border-radius: 2px;
            height: 3px;
        }}
        QProgressBar::chunk {{
            background: {ACCENT};
            border-radius: 2px;
        }}
    """
 
def frame_dot_style(state: str = "default") -> str:
    # state: "default" | "done" | "active"
    if state in ("done", "active"):
        return f"""
            QLabel {{
                background: {BG_ELEVATED};
                border: 1px solid {ACCENT};
                border-radius: {RADIUS_DOT_BTN}px;
                color: {ACCENT};
                font-size: {FONT_XS}px;
            }}
        """
    return f"""
        QLabel {{
            background: {BG_ELEVATED};
            border: 1px solid {BORDER_DEFAULT};
            border-radius: {RADIUS_DOT_BTN}px;
            color: {TEXT_GHOST};
            font-size: {FONT_XS}px;
        }}
    """
 
def result_card_style() -> str:
    return f"""
        QFrame#result_card {{
            background: {BG_SURFACE};
            border: 1px solid {BORDER_SUBTLE};
            border-radius: {RADIUS_CARD}px;
        }}
        QFrame#result_hero {{
            background: {BG_SURFACE_2};
            border-bottom: 1px solid {BORDER_SUBTLE};
        }}
    """
 
def badge_ep_style() -> str:
    return f"""
        QLabel {{
            background: {BADGE_EP_BG};
            border: 1px solid {BADGE_EP_BORDER};
            border-radius: 6px;
            padding: 4px 10px;
            font-size: {FONT_SM}px;
            color: {BADGE_EP_TEXT};
            font-weight: 500;
        }}
    """
 
def badge_ts_style() -> str:
    return f"""
        QLabel {{
            background: {BADGE_TS_BG};
            border: 1px solid {BADGE_TS_BORDER};
            border-radius: 6px;
            padding: 4px 10px;
            font-size: {FONT_SM}px;
            color: {BADGE_TS_TEXT};
            font-weight: 500;
        }}
    """
 
def badge_range_style() -> str:
    return f"""
        QLabel {{
            background: {BADGE_RANGE_BG};
            border: 1px solid {BADGE_RANGE_BORDER};
            border-radius: 6px;
            padding: 4px 10px;
            font-size: {FONT_SM}px;
            color: {BADGE_RANGE_TEXT};
            font-weight: 500;
        }}
    """
 
def confidence_badge_style(high: bool = True) -> str:
    bg     = CONFIDENCE_BG     if high else CONFIDENCE_LOW_BG
    border = CONFIDENCE_BORDER if high else CONFIDENCE_LOW_BORDER
    color  = CONFIDENCE_TEXT   if high else CONFIDENCE_LOW_TEXT
    return f"""
        QLabel {{
            background: {bg};
            border: 1px solid {border};
            border-radius: {RADIUS_APP}px;
            padding: 3px 10px;
            font-size: {FONT_XS}px;
            color: {color};
        }}
    """
 
def stat_box_style() -> str:
    return f"""
        QFrame {{
            background: {BG_APP};
            border-radius: {RADIUS_STAT}px;
        }}
    """
 
def back_btn_style() -> str:
    return f"""
        QPushButton {{
            background: none;
            border: none;
            color: {TEXT_FAINT};
            font-size: {FONT_MD}px;
        }}
        QPushButton:hover {{
            color: {TEXT_MUTED};
        }}
    """
 
def try_again_btn_style() -> str:
    return f"""
        QPushButton {{
            background: {BG_ELEVATED};
            border: 1px solid {BORDER_DEFAULT};
            border-radius: 10px;
            padding: 12px;
            color: {TEXT_DIM};
            font-size: {FONT_BASE}px;
        }}
        QPushButton:hover {{
            background: {BG_HOVER};
            color: {TEXT_MUTED};
        }}
    """
 
def credit_style() -> str:
    return f"""
        QLabel {{
            color: {TEXT_GHOST};
            font-size: {FONT_XS}px;
        }}
    """
