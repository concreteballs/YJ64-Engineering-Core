"""Generate simple parametric OpenSCAD source without executing it."""

from __future__ import annotations

import math


def cylinder_scad(*, radius_mm: float, height_mm: float, facets: int = 96) -> str:
    """Return OpenSCAD source for a centered cylinder.

    The function only generates source text. It does not execute OpenSCAD
    or write files to disk.
    """
    if not math.isfinite(radius_mm) or radius_mm <= 0:
        raise ValueError("radius_mm must be a finite positive number")
    if not math.isfinite(height_mm) or height_mm <= 0:
        raise ValueError("height_mm must be a finite positive number")
    if not isinstance(facets, int) or not 12 <= facets <= 512:
        raise ValueError("facets must be an integer between 12 and 512")

    return (
        f"$fn = {facets};\n"
        f"radius = {radius_mm:.6f}; // mm\n"
        f"height = {height_mm:.6f}; // mm\n"
        "cylinder(h = height, r = radius, center = true);\n"
    )
