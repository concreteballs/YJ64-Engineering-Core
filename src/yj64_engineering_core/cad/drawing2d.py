"""Basic 2D orthographic SVG drawing for a cylindrical part.

This is a dimensioned visual reference, not a standards-certified drawing.
"""
from __future__ import annotations

import math
from pathlib import Path


def cylinder_orthographic_svg(*, radius_mm: float, height_mm: float) -> str:
    for name, value in (("radius_mm", radius_mm), ("height_mm", height_mm)):
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be a finite positive number")

    diameter = 2.0 * radius_mm
    scale = min(3.0, 220.0 / max(diameter, height_mm))
    r, h = radius_mm * scale, height_mm * scale
    top_cx, top_cy = 180.0, 170.0
    side_x, side_y = 390.0, 80.0
    left, right = side_x, side_x + h
    top, bottom = side_y, side_y + diameter * scale

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="640" height="340" viewBox="0 0 640 340">
  <title>YJ64 cylindrical part - orthographic drawing</title>
  <rect x="1" y="1" width="638" height="338" fill="white" stroke="black"/>
  <g fill="none" stroke="black" stroke-width="1.5">
    <circle cx="{top_cx}" cy="{top_cy}" r="{r:.3f}"/>
    <line x1="{top_cx-r-12:.3f}" y1="{top_cy}" x2="{top_cx+r+12:.3f}" y2="{top_cy}" stroke-dasharray="5 3"/>
    <line x1="{top_cx}" y1="{top_cy-r-12:.3f}" x2="{top_cx}" y2="{top_cy+r+12:.3f}" stroke-dasharray="5 3"/>
    <rect x="{left:.3f}" y="{top:.3f}" width="{h:.3f}" height="{diameter*scale:.3f}"/>
    <line x1="{left}" y1="{top-12:.3f}" x2="{left}" y2="{top-30:.3f}"/>
    <line x1="{right:.3f}" y1="{top-12:.3f}" x2="{right:.3f}" y2="{top-30:.3f}"/>
    <line x1="{left}" y1="{top-24:.3f}" x2="{right:.3f}" y2="{top-24:.3f}"/>
    <line x1="{left-12:.3f}" y1="{top:.3f}" x2="{left-30:.3f}" y2="{top:.3f}"/>
    <line x1="{left-12:.3f}" y1="{bottom:.3f}" x2="{left-30:.3f}" y2="{bottom:.3f}"/>
    <line x1="{left-24:.3f}" y1="{top:.3f}" x2="{left-24:.3f}" y2="{bottom:.3f}"/>
  </g>
  <g fill="black" font-family="sans-serif" font-size="13">
    <text x="{top_cx}" y="{top_cy+r+32:.3f}" text-anchor="middle">TOP VIEW</text>
    <text x="{(left+right)/2:.3f}" y="{bottom+34:.3f}" text-anchor="middle">SIDE VIEW</text>
    <text x="{(left+right)/2:.3f}" y="{top-31:.3f}" text-anchor="middle">L = {height_mm:g} mm</text>
    <text x="{left-34:.3f}" y="{(top+bottom)/2:.3f}" text-anchor="middle" transform="rotate(-90 {left-34:.3f} {(top+bottom)/2:.3f})">D = {diameter:g} mm</text>
    <text x="18" y="25" font-size="16" font-weight="bold">YJ64 ENGINEERING CORE</text>
    <text x="18" y="318" font-size="11">UNITS: mm | SCHEMATIC VIEW | NOT FOR MANUFACTURE</text>
  </g>
</svg>
'''


def write_cylinder_svg(*, radius_mm: float, height_mm: float,
                       output_path: str | Path) -> Path:
    path = Path(output_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(cylinder_orthographic_svg(
        radius_mm=radius_mm, height_mm=height_mm), encoding="utf-8")
    return path
