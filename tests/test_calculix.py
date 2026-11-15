import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from yj64_engineering_core.models import AnalysisRequest
from yj64_engineering_core.physics.calculix import CalculiXTrussSolver


class CalculiXTrussSolverTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tempdir.name)
        self.solver = CalculiXTrussSolver(self.workspace)
        self.request = AnalysisRequest(
            analysis_type="axial_truss_fem",
            parameters={
                "request_id": "ccx-test-001",
                "force_n": 1000.0,
                "area_m2": 0.001,
                "length_m": 2.0,
                "material": {
                    "name": "Test steel",
                    "youngs_modulus_pa": 200e9,
                    "poisson_ratio": 0.3,
                },
            },
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_writes_deck_runs_solver_and_returns_fem_displacement(self):
        def fake_run(args, **kwargs):
            if args[-1] == "-v":
                return subprocess.CompletedProcess(
                    args, 0, stdout="CalculiX Version 2.21\n", stderr=""
                )
            job_name = args[-1]
            Path(kwargs["cwd"], f"{job_name}.dat").write_text(
                "displacements (vx,vy,vz) for set TIP and time 0.1000000E+01\n"
                " 2 0.000000E+00 0.000000E+00 1.000000E-05\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(args, 0, stdout="completed", stderr="")

        with patch(
            "yj64_engineering_core.physics.calculix.subprocess.run",
            side_effect=fake_run,
        ) as run:
            result = self.solver.solve(self.request)

        self.assertEqual(result.status, "completed")
        self.assertAlmostEqual(result.values["tip_displacement_z_m"], 1e-5)
        self.assertAlmostEqual(result.values["axial_stress_from_displacement_pa"], 1e6)
        self.assertEqual(result.solver_version, "CalculiX Version 2.21")
        self.assertEqual(run.call_count, 2)
        deck = (self.workspace / "ccx-test-001.inp").read_text(encoding="utf-8")
        self.assertIn("*ELEMENT, TYPE=T3D2, ELSET=BAR", deck)
        self.assertIn("*NODE PRINT, NSET=TIP", deck)
        self.assertIn("2, 3, 1000", deck)

    def test_rejects_invalid_poisson_ratio_before_running(self):
        parameters = dict(self.request.parameters)
        parameters["material"] = dict(parameters["material"], poisson_ratio=0.5)
        request = AnalysisRequest("axial_truss_fem", parameters)
        with patch("yj64_engineering_core.physics.calculix.subprocess.run") as run:
            with self.assertRaisesRegex(ValueError, "poisson_ratio"):
                self.solver.solve(request)
        run.assert_not_called()

    def test_rejects_non_finite_force(self):
        parameters = dict(self.request.parameters, force_n=float("inf"))
        request = AnalysisRequest("axial_truss_fem", parameters)
        with self.assertRaisesRegex(ValueError, "force_n must be finite"):
            self.solver.solve(request)

    def test_reports_solver_nonzero_exit(self):
        def fake_run(args, **kwargs):
            if args[-1] == "-v":
                return subprocess.CompletedProcess(args, 0, stdout="CalculiX 2.21", stderr="")
            return subprocess.CompletedProcess(args, 2, stdout="", stderr="solver failure")

        with patch(
            "yj64_engineering_core.physics.calculix.subprocess.run",
            side_effect=fake_run,
        ):
            with self.assertRaisesRegex(RuntimeError, "solver failure"):
                self.solver.solve(self.request)

    def test_reports_unparseable_solver_output(self):
        def fake_run(args, **kwargs):
            if args[-1] == "-v":
                return subprocess.CompletedProcess(args, 0, stdout="CalculiX 2.21", stderr="")
            Path(kwargs["cwd"], f"{args[-1]}.dat").write_text(
                "no displacement table\n", encoding="utf-8"
            )
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        with patch(
            "yj64_engineering_core.physics.calculix.subprocess.run",
            side_effect=fake_run,
        ):
            with self.assertRaisesRegex(RuntimeError, "Could not parse"):
                self.solver.solve(self.request)


@unittest.skipUnless(shutil.which("ccx"), "CalculiX executable is not installed")
class CalculiXIntegrationTests(unittest.TestCase):
    def test_real_calculix_axial_truss_case(self):
        with tempfile.TemporaryDirectory() as tempdir:
            solver = CalculiXTrussSolver(tempdir, timeout_seconds=30)
            request = AnalysisRequest(
                analysis_type="axial_truss_fem",
                parameters={
                    "request_id": "real-ccx-check",
                    "force_n": 1000.0,
                    "area_m2": 0.001,
                    "length_m": 2.0,
                    "material": {
                        "name": "Test steel",
                        "youngs_modulus_pa": 200e9,
                        "poisson_ratio": 0.3,
                    },
                },
            )
            result = solver.solve(request)
            print((Path(tempdir) / "real-ccx-check.dat").read_text(encoding="utf-8"))
            expected = 1000.0 * 2.0 / (0.001 * 200e9)
            self.assertAlmostEqual(
                result.values["tip_displacement_z_m"], expected, delta=expected * 1e-5
            )
            self.assertEqual(result.status, "completed")


if __name__ == "__main__":
    unittest.main()
