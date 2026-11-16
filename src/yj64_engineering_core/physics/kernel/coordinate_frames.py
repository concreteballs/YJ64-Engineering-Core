"""Right-handed Cartesian coordinate frames and rigid transforms.

A frame's pose is expressed in its parent's coordinates. The rotation matrix
maps column vectors from the frame's local coordinates into parent coordinates.
Translations are metres. Only proper rigid rotations are accepted.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

Vector = tuple[float, float, float]
Matrix3 = tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]
IDENTITY: Matrix3 = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def _vector3(value: Iterable[float], name: str) -> Vector:
    result = tuple(value)
    if len(result) != 3:
        raise ValueError(f"{name} must contain exactly three values")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in result):
        raise TypeError(f"{name} values must be numeric")
    result = tuple(float(v) for v in result)
    if not all(math.isfinite(v) for v in result):
        raise ValueError(f"{name} values must be finite")
    return result  # type: ignore[return-value]


def _matrix3(value: Iterable[Iterable[float]]) -> Matrix3:
    rows = tuple(tuple(row) for row in value)
    if len(rows) != 3 or any(len(row) != 3 for row in rows):
        raise ValueError("rotation_matrix must be 3 by 3")
    flat = [v for row in rows for v in row]
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in flat):
        raise TypeError("rotation_matrix values must be numeric")
    matrix = tuple(tuple(float(v) for v in row) for row in rows)
    if not all(math.isfinite(v) for v in flat):
        raise ValueError("rotation_matrix values must be finite")
    return matrix  # type: ignore[return-value]


def _mat_vec(m: Matrix3, v: Vector) -> Vector:
    return tuple(sum(m[i][j] * v[j] for j in range(3)) for i in range(3))  # type: ignore[return-value]


def _mat_mul(a: Matrix3, b: Matrix3) -> Matrix3:
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3))  # type: ignore[return-value]


def _transpose(m: Matrix3) -> Matrix3:
    return tuple(tuple(m[j][i] for j in range(3)) for i in range(3))  # type: ignore[return-value]


def _add(a: Vector, b: Vector) -> Vector:
    return tuple(a[i] + b[i] for i in range(3))  # type: ignore[return-value]


def _det(m: Matrix3) -> float:
    return (
        m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
        - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
        + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
    )


def _validate_rotation(m: Matrix3, tolerance: float = 1e-8) -> None:
    mtm = _mat_mul(_transpose(m), m)
    for i in range(3):
        for j in range(3):
            expected = 1.0 if i == j else 0.0
            if not math.isclose(mtm[i][j], expected, abs_tol=tolerance):
                raise ValueError("rotation_matrix must be orthonormal")
    if not math.isclose(_det(m), 1.0, abs_tol=tolerance):
        raise ValueError("rotation_matrix must be a proper right-handed rotation (determinant +1)")


@dataclass(frozen=True, slots=True)
class RigidTransform:
    """Transform mapping coordinates in source_frame into target_frame."""

    source_frame: str
    target_frame: str
    rotation: Matrix3 = IDENTITY
    translation_m: Vector = (0.0, 0.0, 0.0)

    def __post_init__(self) -> None:
        if not self.source_frame or not self.target_frame:
            raise ValueError("source_frame and target_frame must be non-empty")
        rotation = _matrix3(self.rotation)
        translation = _vector3(self.translation_m, "translation_m")
        _validate_rotation(rotation)
        object.__setattr__(self, "rotation", rotation)
        object.__setattr__(self, "translation_m", translation)

    def apply_point(self, point_m: Iterable[float]) -> Vector:
        return _add(_mat_vec(self.rotation, _vector3(point_m, "point_m")), self.translation_m)

    def apply_vector(self, vector: Iterable[float]) -> Vector:
        return _mat_vec(self.rotation, _vector3(vector, "vector"))

    def inverse(self) -> "RigidTransform":
        inverse_rotation = _transpose(self.rotation)
        inverse_translation = _mat_vec(inverse_rotation, tuple(-v for v in self.translation_m))
        return RigidTransform(self.target_frame, self.source_frame, inverse_rotation, inverse_translation)

    def then(self, next_transform: "RigidTransform") -> "RigidTransform":
        """Compose self followed by next_transform."""
        if self.target_frame != next_transform.source_frame:
            raise ValueError("transform frames do not connect")
        rotation = _mat_mul(next_transform.rotation, self.rotation)
        translation = _add(_mat_vec(next_transform.rotation, self.translation_m), next_transform.translation_m)
        return RigidTransform(self.source_frame, next_transform.target_frame, rotation, translation)


@dataclass(frozen=True, slots=True)
class CoordinateFrame:
    frame_id: str
    parent_id: str | None = None
    rotation_to_parent: Matrix3 = IDENTITY
    translation_to_parent_m: Vector = (0.0, 0.0, 0.0)

    def __post_init__(self) -> None:
        if not isinstance(self.frame_id, str) or not self.frame_id.strip():
            raise ValueError("frame_id must be non-empty")
        if self.parent_id is not None and (not isinstance(self.parent_id, str) or not self.parent_id.strip()):
            raise ValueError("parent_id must be None or a non-empty string")
        rotation = _matrix3(self.rotation_to_parent)
        translation = _vector3(self.translation_to_parent_m, "translation_to_parent_m")
        _validate_rotation(rotation)
        object.__setattr__(self, "rotation_to_parent", rotation)
        object.__setattr__(self, "translation_to_parent_m", translation)


class CoordinateFrameRegistry:
    """A single-root tree of frames with explicit local-to-parent poses."""

    def __init__(self) -> None:
        self._frames: dict[str, CoordinateFrame] = {}

    def add(self, frame: CoordinateFrame) -> None:
        if not isinstance(frame, CoordinateFrame):
            raise TypeError("frame must be a CoordinateFrame")
        if frame.frame_id in self._frames:
            raise ValueError(f"frame '{frame.frame_id}' is already registered")
        if frame.parent_id is None:
            if self._frames:
                raise ValueError("only one root coordinate frame is allowed")
        elif frame.parent_id not in self._frames:
            raise ValueError(f"parent frame '{frame.parent_id}' is not registered")
        self._frames[frame.frame_id] = frame

    def get(self, frame_id: str) -> CoordinateFrame:
        try:
            return self._frames[frame_id]
        except KeyError as exc:
            raise ValueError(f"unknown coordinate frame '{frame_id}'") from exc

    def ids(self) -> tuple[str, ...]:
        return tuple(self._frames)

    def transform(self, source_frame: str, target_frame: str) -> RigidTransform:
        self.get(source_frame)
        self.get(target_frame)

        def to_root(frame_id: str) -> RigidTransform:
            current = self.get(frame_id)
            result = RigidTransform(frame_id, frame_id)
            while current.parent_id is not None:
                step = RigidTransform(
                    current.frame_id, current.parent_id,
                    current.rotation_to_parent, current.translation_to_parent_m,
                )
                result = result.then(step)
                current = self.get(current.parent_id)
            return result

        source_to_root = to_root(source_frame)
        target_to_root = to_root(target_frame)
        return source_to_root.then(target_to_root.inverse())
