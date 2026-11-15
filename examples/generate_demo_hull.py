"""Generate the sample yacht hull drawing and 3D CAD artifacts in build/hull-demo."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from yj64_engineering_core.cad.hull import HullStation, YachtHull
from yj64_engineering_core.cad.hull_adapters import YachtHullCADBackend


def main() -> None:
    hull = YachtHull(
        name="YJ64 12m demonstrator mono-hull",
        stations=(
            HullStation(0.0, 0.025, -0.55, -0.20, 0.75),
            HullStation(1.0, 0.55, -0.90, -0.35, 1.05),
            HullStation(3.0, 1.25, -1.10, -0.48, 1.30),
            HullStation(5.0, 1.65, -1.20, -0.52, 1.45),
            HullStation(7.0, 1.75, -1.18, -0.50, 1.45),
            HullStation(9.0, 1.45, -1.00, -0.42, 1.35),
            HullStation(11.0, 0.65, -0.72, -0.28, 1.10),
            HullStation(12.0, 0.025, -0.45, -0.16, 0.80),
        ),
    )
    output = Path("build/hull-demo").resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "hull-parameters.json").write_text(
        json.dumps(hull.to_parameters(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    backend = YachtHullCADBackend(
        output,
        openscad_executable=shutil.which("openscad"),
        render_stl=True,
        timeout_seconds=180,
    )
    result = backend.generate({
        "request_id": "yj64-12m-demonstrator",
        "geometry_type": "yacht_hull",
        "parameters": hull.to_parameters(),
    })
    print(json.dumps(result, indent=2))
    for path in sorted(output.iterdir()):
        print(f"GENERATED: {path.name} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
