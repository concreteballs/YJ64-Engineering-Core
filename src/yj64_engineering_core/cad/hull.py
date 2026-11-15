"""Parametric mono-hull geometry and deterministic 2D/3D CAD source generation.

Coordinates are SI metres in a right-handed system:
X = bow-to-stern, Y = port/starboard, Z = vertical.
This is an outer moulded hull envelope, not a scantling or laminate model.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class HullStation:
    x_m: float
    half_beam_m: float
    keel_z_m: float
    chine_z_m: float
    deck_z_m: float

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be numeric")
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if self.half_beam_m <= 0:
            raise ValueError("half_beam_m must be positive")
        if not self.keel_z_m < self.chine_z_m < self.deck_z_m:
            raise ValueError("station heights must satisfy keel < chine < deck")


@dataclass(frozen=True)
class YachtHull:
    name: str
    stations: tuple[HullStation, ...]
    chine_fraction: float = 0.72

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("hull name must be non-empty")
        if len(self.stations) < 3:
            raise ValueError("a hull requires at least three longitudinal stations")
        if not 0.1 <= self.chine_fraction <= 0.95:
            raise ValueError("chine_fraction must be between 0.1 and 0.95")
        xs = [station.x_m for station in self.stations]
        if any(b <= a for a, b in zip(xs, xs[1:])):
            raise ValueError("station x_m values must be strictly increasing")

    @property
    def length_m(self) -> float:
        return self.stations[-1].x_m - self.stations[0].x_m

    @property
    def maximum_beam_m(self) -> float:
        return 2.0 * max(station.half_beam_m for station in self.stations)

    @property
    def maximum_depth_m(self) -> float:
        return max(s.deck_z_m for s in self.stations) - min(s.keel_z_m for s in self.stations)

    def to_parameters(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "chine_fraction": self.chine_fraction,
            "stations": [asdict(station) for station in self.stations],
        }

    @classmethod
    def from_parameters(cls, parameters: dict[str, Any]) -> "YachtHull":
        if not isinstance(parameters, dict):
            raise TypeError("hull parameters must be an object")
        stations_data = parameters.get("stations")
        if not isinstance(stations_data, list):
            raise ValueError("hull parameters require a stations array")
        stations = tuple(
            item if isinstance(item, HullStation) else HullStation(**item)
            for item in stations_data
        )
        return cls(
            name=parameters.get("name", "YJ64 yacht hull"),
            stations=stations,
            chine_fraction=parameters.get("chine_fraction", 0.72),
        )


def hull_vertices_mm(hull: YachtHull) -> list[tuple[float, float, float]]:
    """Five points per station: keel, starboard chine/sheer, port sheer/chine."""
    points: list[tuple[float, float, float]] = []
    for station in hull.stations:
        x = station.x_m * 1000.0
        beam = station.half_beam_m * 1000.0
        points.extend([
            (x, 0.0, station.keel_z_m * 1000.0),
            (x, beam * hull.chine_fraction, station.chine_z_m * 1000.0),
            (x, beam, station.deck_z_m * 1000.0),
            (x, -beam, station.deck_z_m * 1000.0),
            (x, -beam * hull.chine_fraction, station.chine_z_m * 1000.0),
        ])
    return points


def hull_triangles(hull: YachtHull) -> list[tuple[int, int, int]]:
    """Triangulate the closed outer envelope with consistent station connectivity."""
    faces: list[tuple[int, int, int]] = []
    count = len(hull.stations)
    # End caps: bow faces -X, stern faces +X.
    faces.extend([(4, 3, 2), (4, 2, 1), (4, 1, 0)])
    last = (count - 1) * 5
    faces.extend([(last, last + 1, last + 2), (last, last + 2, last + 3),
                  (last, last + 3, last + 4)])
    # Four longitudinal surfaces plus the keel-to-port chine closure.
    for index in range(count - 1):
        a, b = index * 5, (index + 1) * 5
        for edge in range(5):
            nxt = (edge + 1) % 5
            faces.append((a + edge, b + edge, b + nxt))
            faces.append((a + edge, b + nxt, a + nxt))
    return faces


def yacht_hull_openscad(hull: YachtHull) -> str:
    """Generate an editable OpenSCAD polyhedron (units: mm)."""
    points = hull_vertices_mm(hull)
    faces = hull_triangles(hull)
    point_text = ",\n".join(
        f"    [{x:.6f}, {y:.6f}, {z:.6f}]" for x, y, z in points
    )
    face_text = ",\n".join(
        f"    [{a}, {b}, {c}]" for a, b, c in faces
    )
    return (
        "// YJ64 Engineering Core — parametric station-based yacht hull\n"
        "// Outer envelope only; not a structural laminate/scantling model.\n"
        f"// Hull: {hull.name.replace(chr(10), ' ')}\n"
        f"// Length: {hull.length_m:.4f} m | Maximum beam: {hull.maximum_beam_m:.4f} m\n"
        "polyhedron(\n"
        "  points = [\n" + point_text + "\n  ],\n"
        "  faces = [\n" + face_text + "\n  ],\n"
        "  convexity = 10\n"
        ");\n"
    )


def yacht_hull_technical_svg(hull: YachtHull) -> str:
    """Create a three-view 2D technical sketch: plan, profile, and sections."""
    width, height = 1200.0, 760.0
    left, right = 100.0, 1080.0
    length_scale = (right - left) / hull.length_m
    x0 = hull.stations[0].x_m
    plan_y = 190.0
    max_half_beam = max(s.half_beam_m for s in hull.stations)
    plan_scale = min(length_scale, 125.0 / max_half_beam)
    plan_points_port = [
        (left + (s.x_m - x0) * length_scale, plan_y - s.half_beam_m * plan_scale)
        for s in hull.stations
    ]
    plan_points_starboard = [
        (left + (s.x_m - x0) * length_scale, plan_y + s.half_beam_m * plan_scale)
        for s in reversed(hull.stations)
    ]
    plan_path = " ".join(
        [f"M {plan_points_port[0][0]:.2f} {plan_points_port[0][1]:.2f}"]
        + [f"L {x:.2f} {y:.2f}" for x, y in plan_points_port[1:]]
        + [f"L {x:.2f} {y:.2f}" for x, y in plan_points_starboard]
        + ["Z"]
    )

    z_min = min(s.keel_z_m for s in hull.stations)
    z_max = max(s.deck_z_m for s in hull.stations)
    profile_scale = min(length_scale, 230.0 / max(z_max - z_min, 0.01))
    profile_base = 565.0
    def px(s: HullStation) -> float:
        return left + (s.x_m - x0) * length_scale
    def pz(value: float) -> float:
        return profile_base - (value - z_min) * profile_scale
    keel = " ".join(
        [f"M {px(hull.stations[0]):.2f} {pz(hull.stations[0].keel_z_m):.2f}"]
        + [f"L {px(s):.2f} {pz(s.keel_z_m):.2f}" for s in hull.stations[1:]]
    )
    sheer = " ".join(
        [f"M {px(hull.stations[0]):.2f} {pz(hull.stations[0].deck_z_m):.2f}"]
        + [f"L {px(s):.2f} {pz(s.deck_z_m):.2f}" for s in hull.stations[1:]]
    )
    chine = " ".join(
        [f"M {px(hull.stations[0]):.2f} {pz(hull.stations[0].chine_z_m):.2f}"]
        + [f"L {px(s):.2f} {pz(s.chine_z_m):.2f}" for s in hull.stations[1:]]
    )

    section_y = 865.0
    section_scale = min(125.0 / max_half_beam, 95.0 / max(z_max-z_min, 0.01))
    chosen = [hull.stations[0], hull.stations[len(hull.stations)//2], hull.stations[-1]]
    centers = [250.0, 590.0, 930.0]
    sections = []
    for station, center in zip(chosen, centers):
        b = station.half_beam_m * section_scale
        top = section_y - (station.deck_z_m-z_min) * section_scale
        chine_z = section_y - (station.chine_z_m-z_min) * section_scale
        keel_z = section_y - (station.keel_z_m-z_min) * section_scale
        points = [
            (center, keel_z),
            (center+b*hull.chine_fraction, chine_z),
            (center+b, top),
            (center-b, top),
            (center-b*hull.chine_fraction, chine_z),
        ]
        sections.append(
            '<polygon points="' + " ".join(f"{x:.2f},{y:.2f}" for x,y in points)
            + '" fill="none" stroke="#111" stroke-width="2"/>'
        )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="920" viewBox="0 0 1200 920">
<title>{hull.name} — preliminary three-view hull technical sketch</title>
<rect x="1" y="1" width="1198" height="918" fill="white" stroke="black"/>
<g font-family="sans-serif" fill="#111">
  <text x="28" y="36" font-size="22" font-weight="bold">YJ64 ENGINEERING CORE — {hull.name}</text>
  <text x="28" y="62" font-size="13">PRELIMINARY OUTER HULL GEOMETRY | UNITS: m | NOT FOR MANUFACTURE</text>
  <text x="28" y="95" font-size="16" font-weight="bold">PLAN VIEW</text>
  <text x="28" y="350" font-size="16" font-weight="bold">PROFILE VIEW</text>
  <text x="28" y="650" font-size="16" font-weight="bold">TRANSVERSE SECTIONS</text>
  <text x="28" y="690" font-size="12">Bow</text><text x="1080" y="690" font-size="12" text-anchor="end">Stern</text>
  <text x="250" y="900" font-size="13" text-anchor="middle">BOW SECTION</text>
  <text x="590" y="900" font-size="13" text-anchor="middle">MIDSHIP SECTION</text>
  <text x="930" y="900" font-size="13" text-anchor="middle">STERN SECTION</text>
  <text x="28" y="735" font-size="12">L = {hull.length_m:.3f} m | Bmax = {hull.maximum_beam_m:.3f} m | Depth envelope = {hull.maximum_depth_m:.3f} m</text>
</g>
<g fill="none" stroke="#111" stroke-width="2">
  <path d="{plan_path}"/>
  <path d="{keel}"/>
  <path d="{sheer}" stroke="#155a9c"/>
  <path d="{chine}" stroke="#777" stroke-dasharray="6 4"/>
  <line x1="{left}" y1="190" x2="{right}" y2="190" stroke="#aaa" stroke-dasharray="4 5"/>
  <line x1="{left}" y1="565" x2="{right}" y2="565" stroke="#aaa" stroke-dasharray="4 5"/>
  {"".join(sections)}
</g>
</svg>
'''
