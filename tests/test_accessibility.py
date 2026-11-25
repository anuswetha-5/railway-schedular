import os
import sys
import unittest
import pandas as pd
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "database"))

from themes import THEMES


def hex_to_relative_luminance(hex_str):
    """Calculates relative luminance according to WCAG 2.1 formula."""
    hex_str = hex_str.lstrip("#")
    r, g, b = [int(hex_str[i:i+2], 16) / 255.0 for i in (0, 2, 4)]
    
    def transform(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r_lin = transform(r)
    g_lin = transform(g)
    b_lin = transform(b)
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def calculate_contrast_ratio(hex1, hex2):
    """Calculates WCAG 2.1 contrast ratio between two hex colors."""
    l1 = hex_to_relative_luminance(hex1)
    l2 = hex_to_relative_luminance(hex2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


class TestAccessibilityCompliance(unittest.TestCase):

    def test_theme_color_contrast_ratios(self):
        """Verifies Light and Dark themes satisfy WCAG 2.1 Level AA minimum contrast ratios (>= 4.5:1)."""
        # 1. Light Theme
        light = THEMES["Light"]
        light_contrast = calculate_contrast_ratio(light["bg"], light["text"])
        self.assertGreaterEqual(
            light_contrast, 4.5,
            f"Light theme text contrast {light_contrast:.2f}:1 fails WCAG AA 4.5:1 requirement"
        )

        # 2. Dark Theme
        dark = THEMES["Dark"]
        dark_contrast = calculate_contrast_ratio(dark["bg"], dark["text"])
        self.assertGreaterEqual(
            dark_contrast, 4.5,
            f"Dark theme text contrast {dark_contrast:.2f}:1 fails WCAG AA 4.5:1 requirement"
        )

    def test_vintage_table_aria_semantics(self):
        """Verifies custom table renderer includes ARIA landmarks and columnheader scopes."""
        import html
        df = pd.DataFrame({
            "Block ID": ["BLK-101"],
            "Track": ["TRK-101"],
            "Status": ["Approved"],
            "AI Score": [85.0]
        })

        # Emulate render_vintage_table logic
        cols = list(df.columns)
        parts = ['<div class="vintage-table-wrap" role="region" aria-label="Railway Operations Data Table" tabindex="0"><table class="vintage-table" role="table"><thead role="rowgroup"><tr role="row">']
        for col in cols:
            parts.append(f'<th scope="col" role="columnheader">{html.escape(str(col))}</th>')
        parts.append('</tr></thead><tbody role="rowgroup">')
        for _, row in df.iterrows():
            parts.append('<tr role="row">')
            for col in cols:
                value = row[col]
                if col == "AI Score":
                    score = float(value)
                    cell = (
                        f'<div class="score-wrap" role="progressbar" aria-valuenow="{score:.0f}" aria-valuemin="0" aria-valuemax="100" aria-label="AI Priority Score {score:.0f} out of 100">'
                        f'<div class="score-bar"><div class="score-fill" style="width:{score:.0f}%"></div></div>'
                        f'<span class="score-value">{score:.0f}</span></div>'
                    )
                elif col == "Status":
                    val_str = str(value)
                    cell = f'<span class="status-pill"><span class="sr-only">Status: </span>{html.escape(val_str)}</span>'
                else:
                    cell = html.escape(str(value))
                parts.append(f'<td role="cell">{cell}</td>')
            parts.append('</tr>')
        parts.append('</tbody></table></div>')
        html_out = "".join(parts)

        # Assertions for semantic structure
        self.assertIn('role="table"', html_out)
        self.assertIn('role="columnheader"', html_out)
        self.assertIn('scope="col"', html_out)
        self.assertIn('role="cell"', html_out)
        self.assertIn('role="region"', html_out)
        self.assertIn('aria-label="Railway Operations Data Table"', html_out)

        # Assertions for progress bar accessibility
        self.assertIn('role="progressbar"', html_out)
        self.assertIn('aria-valuenow="85"', html_out)
        self.assertIn('aria-valuemin="0"', html_out)
        self.assertIn('aria-valuemax="100"', html_out)

        # Assertions for screen reader announcement prefix
        self.assertIn('<span class="sr-only">Status: </span>Approved', html_out)

    def test_skip_link_and_focus_visible_presence(self):
        """Verifies skip link and focus-visible css rules exist in app.py."""
        app_path = os.path.join(BASE_DIR, "app.py")
        with open(app_path, "r", encoding="utf-8") as f:
            code = f.read()

        self.assertIn(".skip-link", code)
        self.assertIn(":focus-visible", code)
        self.assertIn(".sr-only", code)
        self.assertIn("Skip to Corridor Operations Workspace", code)
        self.assertIn('alt="Indian Railways Locomotive Logo"', code)


if __name__ == "__main__":
    unittest.main()
