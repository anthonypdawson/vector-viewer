"""Shared UI style constants for Vector Inspector."""

# Primary highlight color (used for selected tabs, status text, etc.)
HIGHLIGHT_COLOR = "rgba(0,122,204,1)"
# Subtle background tint for highlights (use where a faint background is desired)
HIGHLIGHT_COLOR_BG = "rgba(0,122,204,0.12)"

# Tab style defaults
TAB_FONT_WEIGHT = 600
TAB_PADDING = "8px 14px"
TAB_FONT_SIZE = "10pt"


def build_global_qss(highlight: str, highlight_bg: str) -> str:
    """Return a global QSS string using the provided highlight colors.

    This centralizes styling for tabs, progress bars, checkboxes/radios,
    hover states, sliders, and focus outlines so the entire app uses a
    consistent accent color.
    """
    return (
        f"QTabBar::tab {{ font-weight: {TAB_FONT_WEIGHT}; padding: {TAB_PADDING}; font-size: {TAB_FONT_SIZE};}}"
        f"QTabBar::tab:selected {{ background-color: {highlight_bg}; border-bottom: 2px solid {highlight}; color: {highlight}; }}"
        # Status / progress text
        f"QProgressDialog QLabel {{ color: {highlight}; }}"
        # ToolButton hover/active
        f"QToolButton:hover {{ background-color: {highlight_bg}; }}"
        f"QToolButton:checked, QToolButton:pressed {{ background-color: {highlight_bg}; border: 1px solid {highlight}; }}"
        # Primary buttons can be marked with property primary="true"
        f'QPushButton[primary="true"] {{ background: {highlight}; color: #fff; border-radius: 4px; padding: 6px 10px; }}'
        # Inputs focus
        f"QLineEdit:focus, QComboBox:focus {{ border: 1px solid {highlight}; }}"
        # Table/Tree selection
        f"QTableView::item:selected, QTreeView::item:selected {{ background: {highlight_bg}; color: {highlight}; }}"
        # Progress and slider accents
        f"QProgressBar::chunk {{ background-color: {highlight}; }}"
        f"QSlider::handle {{ background: {highlight}; border: 1px solid {highlight}; }}"
        # Accessibility focus outline
        f"*:focus {{ outline: 2px solid {highlight_bg}; }}"
    )
