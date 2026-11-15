"""Image-reference ingestion and user markup contracts for visual design review.

This module preserves image identity, dimensions and structured annotations.
A vision-capable model performs semantic image interpretation; this module does
not pretend that metadata parsing is computer vision.
"""
from __future__ import annotations

import hashlib
import json
import math
import struct
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ImageAnnotation:
    kind: str
    points: tuple[tuple[float, float], ...]
    label: str = ""
    target_station_index: int | None = None
    target_field: str | None = None
    target_value: float | None = None

    def __post_init__(self) -> None:
        if self.kind not in {"point", "polyline", "arrow", "region", "note"}:
            raise ValueError("unsupported annotation kind")
        if not self.points:
            raise ValueError("annotation requires at least one normalized point")
        for point in self.points:
            if len(point) != 2:
                raise ValueError("annotation points must be normalized (x, y) pairs")
            for value in point:
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise TypeError("annotation coordinates must be numeric")
                if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                    raise ValueError("annotation coordinates must be within 0..1")
        if self.target_station_index is not None:
            if isinstance(self.target_station_index, bool) or not isinstance(self.target_station_index, int):
                raise TypeError("target_station_index must be an integer")
            if self.target_station_index < 0:
                raise ValueError("target_station_index cannot be negative")
        if self.target_value is not None:
            if isinstance(self.target_value, bool) or not isinstance(self.target_value, (int, float)):
                raise TypeError("target_value must be numeric")
            if not math.isfinite(self.target_value):
                raise ValueError("target_value must be finite")


@dataclass(frozen=True)
class VisualReference:
    image_uri: str
    media_type: str
    width_px: int
    height_px: int
    sha256: str
    annotations: tuple[ImageAnnotation, ...] = ()

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True, allow_nan=False)


def _image_dimensions(data: bytes, suffix: str) -> tuple[int, int, str]:
    if suffix in {".png"}:
        if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError("invalid PNG image")
        width, height = struct.unpack(">II", data[16:24])
        return width, height, "image/png"
    if suffix in {".jpg", ".jpeg"}:
        if len(data) < 4 or data[:2] != b"\xff\xd8":
            raise ValueError("invalid JPEG image")
        index = 2
        sof = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
        while index + 4 <= len(data):
            if data[index] != 0xFF:
                index += 1
                continue
            while index < len(data) and data[index] == 0xFF:
                index += 1
            if index >= len(data):
                break
            marker = data[index]
            index += 1
            if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
                continue
            if index + 2 > len(data):
                break
            segment_length = int.from_bytes(data[index:index+2], "big")
            if segment_length < 2 or index + segment_length > len(data):
                break
            if marker in sof:
                if segment_length < 7:
                    break
                height = int.from_bytes(data[index+3:index+5], "big")
                width = int.from_bytes(data[index+5:index+7], "big")
                return width, height, "image/jpeg"
            index += segment_length
        raise ValueError("could not find JPEG dimensions")
    raise ValueError("supported reference image formats are PNG and JPEG")


def ingest_reference_image(
    image_path: str | Path,
    annotations: tuple[ImageAnnotation, ...] = (),
) -> VisualReference:
    path = Path(image_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    data = path.read_bytes()
    width, height, media_type = _image_dimensions(data, path.suffix.lower())
    if width <= 0 or height <= 0:
        raise ValueError("image dimensions must be positive")
    if not all(isinstance(item, ImageAnnotation) for item in annotations):
        raise TypeError("annotations must contain ImageAnnotation values")
    return VisualReference(
        image_uri=path.as_uri(),
        media_type=media_type,
        width_px=width,
        height_px=height,
        sha256=hashlib.sha256(data).hexdigest(),
        annotations=annotations,
    )


def visual_changes(reference: VisualReference) -> list[dict[str, Any]]:
    """Return only explicit machine-readable changes attached to annotations."""
    changes = []
    for annotation in reference.annotations:
        if annotation.target_station_index is None:
            continue
        if annotation.target_field is None or annotation.target_value is None:
            continue
        changes.append({
            "operation": "set_station",
            "station_index": annotation.target_station_index,
            "field": annotation.target_field,
            "value": annotation.target_value,
            "source": "visual_annotation",
            "annotation_label": annotation.label,
        })
    return changes
