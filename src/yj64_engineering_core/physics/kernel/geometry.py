"""Validated, solver-neutral geometry primitives in SI metres."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

from .coordinate_frames import Vector


def _finite(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _vec(value: Iterable[float], name: str) -> Vector:
    values = tuple(_finite(v, name) for v in value)
    if len(values) != 3:
        raise ValueError(f"{name} must contain three coordinates")
    return values  # type: ignore[return-value]


def _norm(v: Vector) -> float:
    return math.sqrt(sum(x * x for x in v))


@dataclass(frozen=True, slots=True)
class GeometryPoint:
    x_m: float
    y_m: float
    z_m: float
    frame_id: str = "world"

    def __post_init__(self) -> None:
        for name in ("x_m", "y_m", "z_m"):
            object.__setattr__(self, name, _finite(getattr(self, name), name))
        if not isinstance(self.frame_id, str) or not self.frame_id.strip():
            raise ValueError("frame_id must be non-empty")

    @property
    def coordinates_m(self) -> Vector:
        return (self.x_m, self.y_m, self.z_m)


@dataclass(frozen=True, slots=True)
class GeometryVector:
    x: float
    y: float
    z: float
    frame_id: str = "world"

    def __post_init__(self) -> None:
        for name in ("x", "y", "z"):
            object.__setattr__(self, name, _finite(getattr(self, name), name))
        if not isinstance(self.frame_id, str) or not self.frame_id.strip():
            raise ValueError("frame_id must be non-empty")

    @property
    def components(self) -> Vector:
        return (self.x, self.y, self.z)

    @property
    def magnitude(self) -> float:
        return _norm(self.components)

    def normalized(self) -> "GeometryVector":
        magnitude = self.magnitude
        if magnitude <= 0.0:
            raise ValueError("zero vector cannot be normalized")
        return GeometryVector(*(v / magnitude for v in self.components), frame_id=self.frame_id)


@dataclass(frozen=True, slots=True)
class LineSegment:
    start: GeometryPoint
    end: GeometryPoint

    def __post_init__(self) -> None:
        if self.start.frame_id != self.end.frame_id:
            raise ValueError("segment endpoints must use the same coordinate frame")
        if self.length_m <= 0.0:
            raise ValueError("line segment length must be positive")

    @property
    def length_m(self) -> float:
        return _norm(tuple(b - a for a, b in zip(self.start.coordinates_m, self.end.coordinates_m)))


@dataclass(frozen=True, slots=True)
class Plane:
    point: GeometryPoint
    normal: GeometryVector

    def __post_init__(self) -> None:
        if self.point.frame_id != self.normal.frame_id:
            raise ValueError("plane point and normal must use the same coordinate frame")
        if not math.isclose(self.normal.magnitude, 1.0, rel_tol=1e-8, abs_tol=1e-8):
            raise ValueError("plane normal must be a unit vector")


@dataclass(frozen=True, slots=True)
class AxisAlignedBoundingBox:
    minimum: GeometryPoint
    maximum: GeometryPoint

    def __post_init__(self) -> None:
        if self.minimum.frame_id != self.maximum.frame_id:
            raise ValueError("bounding-box corners must use the same coordinate frame")
        if any(a > b for a, b in zip(self.minimum.coordinates_m, self.maximum.coordinates_m)):
            raise ValueError("bounding-box minimum must not exceed maximum")

    @property
    def dimensions_m(self) -> Vector:
        return tuple(b - a for a, b in zip(self.minimum.coordinates_m, self.maximum.coordinates_m))  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class Sphere:
    center: GeometryPoint
    radius_m: float

    def __post_init__(self) -> None:
        radius = _finite(self.radius_m, "radius_m")
        if radius <= 0.0:
            raise ValueError("sphere radius must be positive")
        object.__setattr__(self, "radius_m", radius)


@dataclass(frozen=True, slots=True)
class Cylinder:
    start: GeometryPoint
    end: GeometryPoint
    radius_m: float

    def __post_init__(self) -> None:
        if self.start.frame_id != self.end.frame_id:
            raise ValueError("cylinder axis endpoints must use the same coordinate frame")
        if _norm(tuple(b - a for a, b in zip(self.start.coordinates_m, self.end.coordinates_m))) <= 0.0:
            raise ValueError("cylinder axis length must be positive")
        radius = _finite(self.radius_m, "radius_m")
        if radius <= 0.0:
            raise ValueError("cylinder radius must be positive")
        object.__setattr__(self, "radius_m", radius)
