"""Shared badge color palette for POIs and zones."""

POI_COLORS = [
    {"name": "blue", "color": "#1d4ed8", "bg": "#dbeafe", "dark_color": "#93c5fd", "dark_bg": "#172554"},
    {"name": "orange", "color": "#c2410c", "bg": "#ffedd5", "dark_color": "#fdba74", "dark_bg": "#431407"},
    {"name": "purple", "color": "#7c3aed", "bg": "#ede9fe", "dark_color": "#c4b5fd", "dark_bg": "#2e1065"},
    {"name": "teal", "color": "#0f766e", "bg": "#ccfbf1", "dark_color": "#2dd4bf", "dark_bg": "#042f2e"},
    {"name": "rose", "color": "#be123c", "bg": "#ffe4e6", "dark_color": "#fda4af", "dark_bg": "#4c0519"},
    {"name": "amber", "color": "#b45309", "bg": "#fef3c7", "dark_color": "#fcd34d", "dark_bg": "#451a03"},
    {"name": "emerald", "color": "#047857", "bg": "#d1fae5", "dark_color": "#34d399", "dark_bg": "#064e3b"},
    {"name": "slate", "color": "#475569", "bg": "#f1f5f9", "dark_color": "#94a3b8", "dark_bg": "#1e293b"},
]


def color_for(color_index: int) -> dict:
    return POI_COLORS[color_index % len(POI_COLORS)]
