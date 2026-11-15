"""Run a transparent sail-polar force screening example.

The included polar is illustrative test data, not a validated sail polar.
Replace it with measured or independently validated data before engineering use.
"""
from yj64_engineering_core import AnalysisRequest, SailAerodynamicsSolver


request = AnalysisRequest(
    analysis_type="aerodynamics.sail_polar",
    parameters={
        "geometry": {
            "sail_area_m2": 120.0,
            "span_m": 18.0,
            "mean_chord_m": 6.67,
            "polar_source": "illustrative example only - replace with validated data",
            "polar_points": [
                {"alpha_deg": -8.0, "cl": -0.45, "cd": 0.075, "cm": 0.025},
                {"alpha_deg": 0.0, "cl": 0.0, "cd": 0.028, "cm": 0.0},
                {"alpha_deg": 5.0, "cl": 0.55, "cd": 0.040, "cm": -0.025},
                {"alpha_deg": 10.0, "cl": 0.95, "cd": 0.065, "cm": -0.045},
                {"alpha_deg": 15.0, "cl": 1.08, "cd": 0.105, "cm": -0.060},
                {"alpha_deg": 20.0, "cl": 0.92, "cd": 0.19, "cm": -0.055},
            ],
        },
        "operating_conditions": {
            "apparent_wind_speed_m_s": 12.0,
            "air_density_kg_m3": 1.225,
            "dynamic_viscosity_pa_s": 1.81e-5,
            "angle_of_attack_deg": 10.0,
            "apparent_wind_from_angle_deg": 35.0,
            "oswald_efficiency": 0.82,
        },
    },
)

result = SailAerodynamicsSolver().solve(request)
for key, value in result.values.items():
    print(f"{key}: {value:.4f}")
print(f"status: {result.status}")
for warning in result.warnings:
    print(f"WARNING: {warning}")
