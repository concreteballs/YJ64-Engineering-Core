"""Isolated CalculiX runner for a deliberately small axial-truss FEM case.

This adapter generates its own constrained T3D2 input deck. It does not accept
arbitrary solver decks or execute LLM-provided source code.
"""

from __future__ import annotations

import math
import re
import subprocess
from pathlib import Path
from typing import Any

from ..models import AnalysisRequest, AnalysisResult


_FLOAT = re.compile(
    r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][+-]?\d+)?$"
)
_SAFE_ID = re.compile(r"[^A-Za-z0-9_-]")


def _number(parameters: dict[str, Any], name: str, *, positive: bool = False) -> float:
    value = parameters.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if positive and value <= 0:
        raise ValueError(f"{name} must be positive")
    return float(value)


class CalculiXTrussSolver:
    """Run a one-element 3D truss FEM model using the external ccx executable."""

    name = "CalculiX T3D2 axial truss solver"
    version = "runtime-detected"

    def __init__(
        self,
        workspace: str | Path,
        executable: str = "ccx",
        timeout_seconds: float = 60.0,
    ) -> None:
        if not isinstance(executable, str) or not executable.strip():
            raise ValueError("executable must be a non-empty command or path")
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be finite and positive")
        self.workspace = Path(workspace).expanduser().resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.executable = executable
        self.timeout_seconds = float(timeout_seconds)

    def supports(self, analysis_type: str) -> bool:
        return analysis_type == "axial_truss_fem"

    def solve(self, request: AnalysisRequest) -> AnalysisResult:
        if request.analysis_type != "axial_truss_fem":
            raise ValueError(f"Unsupported analysis type: {request.analysis_type}")
        p = request.parameters
        force_n = _number(p, "force_n")
        area_m2 = _number(p, "area_m2", positive=True)
        length_m = _number(p, "length_m", positive=True)
        material = p.get("material")
        if not isinstance(material, dict):
            raise TypeError("material must be an object")
        youngs_modulus_pa = _number(material, "youngs_modulus_pa", positive=True)
        poisson_ratio = _number(material, "poisson_ratio")
        if not -1.0 < poisson_ratio < 0.5:
            raise ValueError("poisson_ratio must be between -1 and 0.5")

        request_id = p.get("request_id", "calculix-axial")
        if not isinstance(request_id, str) or not request_id.strip():
            raise ValueError("request_id must be a non-empty string")
        job_name = _SAFE_ID.sub("_", request_id)[:48] or "calculix_axial"
        input_path = self.workspace / f"{job_name}.inp"
        if input_path.parent != self.workspace:
            raise ValueError("CalculiX input path escaped the configured workspace")

        input_path.write_text(
            self._input_deck(
                force_n=force_n,
                area_m2=area_m2,
                length_m=length_m,
                youngs_modulus_pa=youngs_modulus_pa,
                poisson_ratio=poisson_ratio,
            ),
            encoding="utf-8",
        )

        solver_version = self._detect_version()
        try:
            completed = subprocess.run(
                [self.executable, "-i", job_name],
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(
                f"CalculiX exceeded the {self.timeout_seconds:g}s time limit"
            ) from exc
        except OSError as exc:
            raise RuntimeError(f"Could not start CalculiX executable: {exc}") from exc

        if completed.returncode != 0:
            details = (completed.stderr or completed.stdout or "").strip()
            raise RuntimeError(
                f"CalculiX exited with code {completed.returncode}: {details[-2000:]}"
            )

        dat_path = self.workspace / f"{job_name}.dat"
        if not dat_path.is_file():
            raise RuntimeError("CalculiX finished without producing the expected .dat file")
        displacement_m = self._read_tip_displacement(dat_path)
        axial_strain = displacement_m / length_m
        axial_stress_pa = youngs_modulus_pa * axial_strain

        return AnalysisResult(
            analysis_type="axial_truss_fem",
            status="completed",
            values={
                "tip_displacement_z_m": displacement_m,
                "axial_strain_from_displacement": axial_strain,
                "axial_stress_from_displacement_pa": axial_stress_pa,
                "applied_force_n": force_n,
                "cross_section_area_m2": area_m2,
                "member_length_m": length_m,
            },
            units={
                "tip_displacement_z_m": "m",
                "axial_strain_from_displacement": "dimensionless",
                "axial_stress_from_displacement_pa": "Pa",
                "applied_force_n": "N",
                "cross_section_area_m2": "m^2",
                "member_length_m": "m",
            },
            method="CalculiX T3D2 one-element linear-static FEM",
            assumptions=[
                "Straight prismatic axial member represented by one T3D2 truss element.",
                "Small-displacement linear elasticity.",
                "Isotropic material with the supplied Young's modulus and Poisson ratio.",
                "Node 1 is fixed; node 2 is free only in the member-axis direction.",
                "Axial stress is derived from the FEM tip displacement and supplied Young's modulus.",
            ],
            warnings=[
                "This is a one-element axial truss verification case, not a 3D solid stress analysis."
            ],
            limitations=[
                "No bending, shear, buckling, fatigue, contact, thermal effects, or stress concentrations.",
                "No CAD-to-mesh conversion or geometric equivalence check is performed.",
                "Results are not design certification or a substitute for independent validation.",
            ],
            solver_name=self.name,
            solver_version=solver_version,
        )

    def _detect_version(self) -> str:
        try:
            result = subprocess.run(
                [self.executable, "-v"],
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=min(self.timeout_seconds, 10.0),
                check=False,
                shell=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return "unknown"
        output = (result.stdout or result.stderr or "").strip()
        return output.splitlines()[0][:160] if result.returncode == 0 and output else "unknown"

    @staticmethod
    def _input_deck(
        *,
        force_n: float,
        area_m2: float,
        length_m: float,
        youngs_modulus_pa: float,
        poisson_ratio: float,
    ) -> str:
        return f"""*HEADING
YJ64 generated axial truss verification model
*NODE, NSET=ALL
1, 0.0, 0.0, 0.0
2, 0.0, 0.0, {length_m:.16g}
*NSET, NSET=TIP
2
*ELEMENT, TYPE=T3D2, ELSET=BAR
1, 1, 2
*MATERIAL, NAME=YJ64_MATERIAL
*ELASTIC
{youngs_modulus_pa:.16g}, {poisson_ratio:.16g}
*SOLID SECTION, ELSET=BAR, MATERIAL=YJ64_MATERIAL
{area_m2:.16g}
*BOUNDARY
1, 1, 3
2, 1, 2
*STEP
*STATIC
*CLOAD
2, 3, {force_n:.16g}
*NODE PRINT, NSET=TIP
U
*END STEP
"""

    @staticmethod
    def _read_tip_displacement(dat_path: Path) -> float:
        lines = dat_path.read_text(encoding="utf-8", errors="replace").splitlines()
        in_displacements = False
        for line in lines:
            lowered = line.lower()
            if "displacements" in lowered and "tip" in lowered:
                in_displacements = True
                continue
            if not in_displacements:
                continue
            fields = line.split()
            if len(fields) < 4 or fields[0] != "2":
                continue
            numeric = fields[1:4]
            if not all(_FLOAT.fullmatch(value) for value in numeric):
                continue
            values = [float(value.replace("D", "E").replace("d", "e")) for value in numeric]
            if not all(math.isfinite(value) for value in values):
                raise RuntimeError("CalculiX returned a non-finite displacement")
            return values[2]
        raise RuntimeError("Could not parse node 2 displacement from CalculiX .dat output")
