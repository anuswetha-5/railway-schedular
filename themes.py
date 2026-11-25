"""
Theme registry and CSS variable definitions for the Indian Railways AI Corridor Scheduler.
Ensures single-source-of-truth styling across custom CSS and Plotly data visualizations.
"""

from typing import Dict, Any

THEMES = {
    "Light": {
        "color_scheme": "light",
        "bg": "#f1ecdf", "panel": "#fbf8ef", "panel2": "#f5f0e4",
        "line": "#cfc4ad", "line2": "#ded5c3", "soft": "#e7dfcf",
        "text": "#2d2b27", "muted": "#746d61",
        "input": "#fffdf7", "input_text": "#2d2b27",
        "blue": "#2e5d73", "navy": "#213d4a", "purple": "#684b6f",
        "red": "#7b302b", "brass": "#a67c3c", "green": "#315b4a",
        "amber": "#b38a4e",
        "sidebar": "#29483d", "sidebar2": "#365b4e", "sidebar_text": "#f6f0e3",
        "shadow": "0 1px 2px rgba(64,52,35,.10)",
        "chart_paper": "#fbf8ef", "chart_plot": "#fbf8ef",
        "chart_font": "#2d2b27", "chart_grid": "#ddd4c4",
        "texture_opacity": ".08",
        "status_colors": {"Scheduled": "#557d69", "Pending": "#b38a4e", "Delayed": "#a84f47"},
        "severity_colors": {"Low": "#6b806c", "Medium": "#a67c3c", "High": "#9b5b3f", "Critical": "#7b302b"},
        "dept_scale": [[0, "#c9b58c"], [0.55, "#8d6f42"], [1, "#5b4330"]],
    },
    "Dark": {
        "color_scheme": "dark",
        "bg": "#151816", "panel": "#202521", "panel2": "#292e2a",
        "line": "#485049", "line2": "#383f39", "soft": "#303631",
        "text": "#eee9dc", "muted": "#b8b1a3",
        "input": "#1b211d", "input_text": "#eee9dc",
        "blue": "#88aebc", "navy": "#a9bec6", "purple": "#ad91b3",
        "red": "#c56a60", "brass": "#c9a15f", "green": "#8fbaa0",
        "amber": "#d3ab6e",
        "sidebar": "#1e3930", "sidebar2": "#2c5144", "sidebar_text": "#f3eee2",
        "shadow": "0 1px 4px rgba(0,0,0,.32)",
        "chart_paper": "#202521", "chart_plot": "#202521",
        "chart_font": "#eee9dc", "chart_grid": "#414840",
        "texture_opacity": ".025",
        "status_colors": {"Scheduled": "#7fb497", "Pending": "#d3ab6e", "Delayed": "#c56a60"},
        "severity_colors": {"Low": "#8fbaa0", "Medium": "#c9a15f", "High": "#c98866", "Critical": "#c56a60"},
        "dept_scale": [[0, "#5b4330"], [0.55, "#8d6f42"], [1, "#c9b58c"]],
    },
}


def css_vars_block(theme: Dict[str, Any]) -> str:
    """Turn a theme dict into a `--name:value;` string for :root."""
    keys = [
        "bg", "panel", "panel2", "line", "line2", "text", "muted", "soft",
        "input", "input_text", "blue", "navy", "purple", "red", "brass",
        "green", "amber", "chart_grid", "chart_paper", "sidebar", "sidebar2",
        "sidebar_text", "shadow",
    ]
    return "".join(f"--{k.replace('_', '-')}:{theme[k]};" for k in keys)
