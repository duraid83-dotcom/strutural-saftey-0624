"""
Structural safety calculations for the educational Flask calculator.

All internal math uses SI base units:
    force in N, length in m, area in m^2, stress/modulus in Pa, I in m^4.

Results are converted back to conventional civil-engineering display units
(kN, mm, MPa, etc.) in each result dictionary.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Optional


CALC_TYPES = {
    "axial": "Axial Member Safety",
    "tension": "Tension Member",
    "compression": "Compression Member",
    "beam": "Simple Beam Bending",
    "shear": "Shear Stress",
}

# Conversion factors: multiply the entered number by these to reach SI base units.
FORCE_TO_N = {"N": 1.0, "kN": 1000.0}
LENGTH_TO_M = {"m": 1.0, "mm": 0.001}
AREA_TO_M2 = {"m2": 1.0, "mm2": 1.0e-6}
STRESS_TO_PA = {"Pa": 1.0, "MPa": 1.0e6, "GPa": 1.0e9}
I_TO_M4 = {"m4": 1.0, "mm4": 1.0e-12}
UDL_TO_NPM = {"N/m": 1.0, "kN/m": 1000.0}

# Common end-fixity factors K for Euler buckling (effective length = K * L).
K_PRESETS = {
    "0.5": ("Both ends fixed (theoretical)", 0.5),
    "0.7": ("One end fixed, one pinned (recommended)", 0.7),
    "1.0": ("Both ends pinned", 1.0),
    "2.0": ("One end fixed, one free (cantilever)", 2.0),
    "custom": ("Custom K", None),
}


class ValidationError(Exception):
    """Raised when form values are missing, non-numeric, or physically invalid."""

    def __init__(self, errors: dict[str, str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors.values()))


def fmt(value: float, digits: int = 4) -> str:
    """Format a number with a stable number of significant figures."""
    if value == 0:
        return "0"
    return f"{value:.{digits}g}"


def out(name: str, value: float, unit: str) -> dict[str, Any]:
    """One results-table row: formatted text plus the raw float for tests."""
    return {"name": name, "value": fmt(value), "unit": unit, "raw": value}


def _get_str(form: Mapping[str, str], name: str) -> str:
    raw = form.get(name, "")
    return raw.strip() if isinstance(raw, str) else str(raw).strip()


def _parse_float(
    form: Mapping[str, str],
    name: str,
    label: str,
    errors: dict[str, str],
    *,
    required: bool = True,
    positive: bool = True,
    allow_zero: bool = False,
) -> Optional[float]:
    raw = _get_str(form, name)
    if raw == "":
        if required:
            errors[name] = f"{label} is required."
        return None
    try:
        value = float(raw)
    except ValueError:
        errors[name] = f"{label} must be a number."
        return None
    if math.isnan(value) or math.isinf(value):
        errors[name] = f"{label} must be a finite number."
        return None
    if positive and value < 0:
        errors[name] = f"{label} cannot be negative."
        return None
    if positive and (not allow_zero) and value == 0:
        errors[name] = f"{label} must be greater than zero (division by zero is not allowed)."
        return None
    return value


def _unit(form: Mapping[str, str], name: str, allowed: dict[str, float], default: str) -> str:
    raw = _get_str(form, name) or default
    return raw if raw in allowed else default


def _si(value: Optional[float], unit: str, table: dict[str, float]) -> Optional[float]:
    if value is None:
        return None
    return value * table[unit]


def calculate(form: Mapping[str, str]) -> dict[str, Any]:
    """Dispatch to the selected structural case. Returns a display-ready dict."""
    calc_type = _get_str(form, "calc_type")
    if calc_type not in CALC_TYPES:
        raise ValidationError({"calc_type": "Please select a valid calculation type."})

    material = _get_str(form, "material") or "custom"

    if calc_type == "axial":
        result = _axial(form, tension_only=False, compression_only=False)
    elif calc_type == "tension":
        result = _axial(form, tension_only=True, compression_only=False)
    elif calc_type == "compression":
        result = _compression(form)
    elif calc_type == "beam":
        result = _beam(form)
    else:
        result = _shear(form)

    result["calc_type"] = calc_type
    result["calc_title"] = CALC_TYPES[calc_type]
    result["material"] = material
    return result


def _axial(
    form: Mapping[str, str],
    *,
    tension_only: bool,
    compression_only: bool,
) -> dict[str, Any]:
    """
    Uniform axial stress in a prismatic bar.

    sigma = P / A
    epsilon = sigma / E          (Hooke's law, linear elastic)
    delta = P * L / (A * E)      (axial elongation or shortening)
    FoS = sigma_allow / sigma
    P_allow = sigma_allow * A
    """
    errors: dict[str, str] = {}

    p_unit = _unit(form, "force_unit", FORCE_TO_N, "kN")
    a_unit = _unit(form, "area_unit", AREA_TO_M2, "mm2")
    l_unit = _unit(form, "length_unit", LENGTH_TO_M, "m")
    e_unit = _unit(form, "e_unit", STRESS_TO_PA, "GPa")

    p = _parse_float(form, "force", "Applied load", errors)
    a = _parse_float(form, "area", "Cross-sectional area", errors)
    sigma_allow = _parse_float(form, "allowable_stress", "Allowable stress", errors)
    length = _parse_float(form, "length", "Length", errors, required=False)
    e_val = _parse_float(form, "youngs_modulus", "Young's modulus", errors, required=False)

    net_area = _parse_float(form, "net_area", "Net area", errors, required=False)
    if tension_only and net_area is not None and a is not None and net_area > a:
        errors["net_area"] = "Net area cannot be larger than the gross area."

    if errors:
        raise ValidationError(errors)

    p_n = _si(p, p_unit, FORCE_TO_N)
    a_m2 = _si(a, a_unit, AREA_TO_M2)
    allow_pa = _si(sigma_allow, "MPa", STRESS_TO_PA)
    l_m = _si(length, l_unit, LENGTH_TO_M)
    e_pa = _si(e_val, e_unit, STRESS_TO_PA)

    # Tension members: use net area when provided (holes / bolts reduce the section).
    a_used = a_m2
    area_note = "gross area A"
    if tension_only and net_area is not None:
        a_used = _si(net_area, a_unit, AREA_TO_M2)
        area_note = "net area A_net"

    assert p_n is not None and a_used is not None and allow_pa is not None

    sigma_pa = p_n / a_used  # Pa = N / m^2
    sigma_mpa = sigma_pa / 1.0e6
    fos = allow_pa / sigma_pa
    p_allow_n = allow_pa * a_used
    safe = sigma_pa <= allow_pa

    strain = None
    delta_m = None
    steps = [
        f"Convert applied load: P = {fmt(p)} {p_unit} = {fmt(p_n)} N",
        f"Convert {area_note}: A = {fmt(a_used)} m²",
        f"Axial stress: σ = P / A = {fmt(p_n)} / {fmt(a_used)} = {fmt(sigma_pa)} Pa = {fmt(sigma_mpa)} MPa",
        f"Allowable stress: σ_allow = {fmt(sigma_allow)} MPa = {fmt(allow_pa)} Pa",
        f"Factor of safety: FoS = σ_allow / σ = {fmt(allow_pa)} / {fmt(sigma_pa)} = {fmt(fos)}",
        f"Allowable load capacity: P_allow = σ_allow × A = {fmt(allow_pa)} × {fmt(a_used)} = {fmt(p_allow_n)} N = {fmt(p_allow_n / 1000.0)} kN",
    ]

    formula_lines = [
        "σ = P / A",
        "FoS = σ_allow / σ",
        "P_allow = σ_allow × A",
    ]

    if e_pa is not None:
        strain = sigma_pa / e_pa  # dimensionless
        formula_lines.append("ε = σ / E")
        steps.append(
            f"Axial strain (Hooke's law): ε = σ / E = {fmt(sigma_pa)} / {fmt(e_pa)} = {fmt(strain)}"
        )
        if l_m is not None:
            delta_m = (p_n * l_m) / (a_used * e_pa)
            formula_lines.append("δ = P L / (A E)")
            steps.append(
                f"Axial deformation: δ = P L / (A E) = ({fmt(p_n)} × {fmt(l_m)}) / "
                f"({fmt(a_used)} × {fmt(e_pa)}) = {fmt(delta_m)} m = {fmt(delta_m * 1000.0)} mm"
            )

    if tension_only:
        assumptions = [
            "The member is in pure tension with a uniformly distributed axial force.",
            "If net area is omitted, the gross area is used (no hole deduction).",
            "If net area is given, tensile stress is P / A_net (AISC/Eurocode-style net-section idea, simplified).",
            "Linear-elastic Hooke's law is used only when E is provided.",
            "SAFE means σ ≤ σ_allow (equivalently FoS ≥ 1). The allowable stress you enter should already include any code factor you want to apply.",
        ]
        case_name = "Tension member"
    elif compression_only:
        assumptions = []
        case_name = "Axial compression (stress only)"
    else:
        assumptions = [
            "The member is prismatic and loaded by a concentric axial force (no bending).",
            "Stress is assumed uniform over the cross-section: σ = P / A.",
            "Buckling is not checked in this case; use Compression Member for Euler buckling.",
            "Linear-elastic strain and elongation are reported only when E (and L) are provided.",
            "SAFE means σ ≤ σ_allow (FoS ≥ 1 against the allowable stress you entered).",
        ]
        case_name = "Axial member"

    inputs = [
        ("Applied load P", f"{fmt(p)} {p_unit}"),
        ("Gross area A", f"{fmt(a)} {a_unit}"),
        ("Allowable stress σ_allow", f"{fmt(sigma_allow)} MPa"),
    ]
    if tension_only and net_area is not None:
        inputs.append(("Net area A_net", f"{fmt(net_area)} {a_unit}"))
    if length is not None:
        inputs.append(("Length L", f"{fmt(length)} {l_unit}"))
    if e_val is not None:
        inputs.append(("Young's modulus E", f"{fmt(e_val)} {e_unit}"))

    outputs = [
        out("Axial stress σ", sigma_mpa, "MPa"),
        out("Factor of safety FoS", fos, "—"),
        out("Allowable load P_allow", p_allow_n / 1000.0, "kN"),
    ]
    if strain is not None:
        outputs.append(out("Axial strain ε", strain, "dimensionless"))
    if delta_m is not None:
        outputs.append(out("Axial deformation δ", delta_m * 1000.0, "mm"))

    return {
        "case_name": case_name,
        "inputs": inputs,
        "formula": formula_lines,
        "steps": steps,
        "outputs": outputs,
        "fos": fos,
        "status": "SAFE" if safe else "UNSAFE",
        "safe": safe,
        "assumptions": assumptions,
    }


def _compression(form: Mapping[str, str]) -> dict[str, Any]:
    """
    Concentric compression member: crushing stress and Euler buckling.

    Crushing:     sigma = P / A
                  P_crush = sigma_allow * A
    Euler load:   P_cr = π² E I / (K L)²
                  r = sqrt(I / A)
                  λ = K L / r
    Governing capacity is the smaller of P_crush and P_cr.
    """
    errors: dict[str, str] = {}

    p_unit = _unit(form, "force_unit", FORCE_TO_N, "kN")
    a_unit = _unit(form, "area_unit", AREA_TO_M2, "mm2")
    l_unit = _unit(form, "length_unit", LENGTH_TO_M, "m")
    e_unit = _unit(form, "e_unit", STRESS_TO_PA, "GPa")
    i_unit = _unit(form, "inertia_unit", I_TO_M4, "mm4")

    p = _parse_float(form, "force", "Applied compressive load", errors)
    a = _parse_float(form, "area", "Cross-sectional area", errors)
    length = _parse_float(form, "length", "Unsupported length", errors)
    e_val = _parse_float(form, "youngs_modulus", "Young's modulus", errors)
    i_val = _parse_float(form, "inertia", "Moment of inertia I", errors)
    sigma_allow = _parse_float(form, "allowable_stress", "Allowable compressive stress", errors)

    k_choice = _get_str(form, "k_factor") or "1.0"
    if k_choice == "custom":
        k = _parse_float(form, "k_custom", "Custom effective-length factor K", errors)
    elif k_choice in K_PRESETS and K_PRESETS[k_choice][1] is not None:
        k = K_PRESETS[k_choice][1]
    else:
        errors["k_factor"] = "Select a valid effective-length factor K."
        k = None

    if errors:
        raise ValidationError(errors)

    p_n = _si(p, p_unit, FORCE_TO_N)
    a_m2 = _si(a, a_unit, AREA_TO_M2)
    l_m = _si(length, l_unit, LENGTH_TO_M)
    e_pa = _si(e_val, e_unit, STRESS_TO_PA)
    i_m4 = _si(i_val, i_unit, I_TO_M4)
    allow_pa = _si(sigma_allow, "MPa", STRESS_TO_PA)

    assert all(v is not None for v in (p_n, a_m2, l_m, e_pa, i_m4, allow_pa, k))

    sigma_pa = p_n / a_m2
    sigma_mpa = sigma_pa / 1.0e6
    fos_crush = allow_pa / sigma_pa
    p_crush_n = allow_pa * a_m2

    kl = k * l_m
    if kl == 0:
        raise ValidationError({"k_factor": "Effective length K·L must be greater than zero."})

    # Euler critical load for a linearly elastic, perfectly straight column.
    p_cr_n = (math.pi ** 2) * e_pa * i_m4 / (kl ** 2)
    r_m = math.sqrt(i_m4 / a_m2)  # radius of gyration
    slenderness = kl / r_m
    fos_buckling = p_cr_n / p_n

    p_capacity_n = min(p_crush_n, p_cr_n)
    governing = "crushing (σ_allow × A)" if p_crush_n <= p_cr_n else "Euler buckling (P_cr)"
    fos = min(fos_crush, fos_buckling)
    safe = p_n <= p_capacity_n

    k_label = K_PRESETS.get(k_choice, ("Custom K", None))[0]

    steps = [
        f"Convert load: P = {fmt(p)} {p_unit} = {fmt(p_n)} N (compression)",
        f"Convert area: A = {fmt(a_m2)} m²",
        f"Compressive stress: σ = P / A = {fmt(p_n)} / {fmt(a_m2)} = {fmt(sigma_mpa)} MPa",
        f"Crushing capacity: P_crush = σ_allow × A = {fmt(sigma_allow)} MPa × {fmt(a_m2)} m² = {fmt(p_crush_n / 1000.0)} kN",
        f"FoS against crushing: FoS_crush = σ_allow / σ = {fmt(fos_crush)}",
        f"Effective length: KL = {fmt(k)} × {fmt(l_m)} m = {fmt(kl)} m  ({k_label})",
        f"Radius of gyration: r = √(I / A) = √({fmt(i_m4)} / {fmt(a_m2)}) = {fmt(r_m)} m = {fmt(r_m * 1000.0)} mm",
        f"Slenderness ratio: λ = KL / r = {fmt(slenderness)}",
        f"Euler critical load: P_cr = π² E I / (KL)² = π² × {fmt(e_pa)} × {fmt(i_m4)} / ({fmt(kl)})² = {fmt(p_cr_n / 1000.0)} kN",
        f"FoS against buckling: FoS_buckling = P_cr / P = {fmt(fos_buckling)}",
        f"Governing capacity = min(P_crush, P_cr) = {fmt(p_capacity_n / 1000.0)} kN  → {governing}",
        f"Governing FoS = min(FoS_crush, FoS_buckling) = {fmt(fos)}",
    ]

    return {
        "case_name": "Compression member (crushing + Euler buckling)",
        "inputs": [
            ("Applied compressive load P", f"{fmt(p)} {p_unit}"),
            ("Area A", f"{fmt(a)} {a_unit}"),
            ("Length L", f"{fmt(length)} {l_unit}"),
            ("Effective-length factor K", f"{fmt(k)} ({k_label})"),
            ("Moment of inertia I", f"{fmt(i_val)} {i_unit}"),
            ("Young's modulus E", f"{fmt(e_val)} {e_unit}"),
            ("Allowable compressive stress", f"{fmt(sigma_allow)} MPa"),
        ],
        "formula": [
            "σ = P / A",
            "P_crush = σ_allow × A",
            "r = √(I / A)",
            "λ = K L / r",
            "P_cr = π² E I / (K L)²",
            "P_capacity = min(P_crush, P_cr)",
            "FoS_crush = σ_allow / σ",
            "FoS_buckling = P_cr / P",
            "FoS = min(FoS_crush, FoS_buckling)",
        ],
        "steps": steps,
        "outputs": [
            out("Compressive stress σ", sigma_mpa, "MPa"),
            out("Radius of gyration r", r_m * 1000.0, "mm"),
            out("Slenderness ratio λ", slenderness, "—"),
            out("Crushing capacity P_crush", p_crush_n / 1000.0, "kN"),
            out("Euler critical load P_cr", p_cr_n / 1000.0, "kN"),
            out("Governing capacity", p_capacity_n / 1000.0, "kN"),
            out("FoS (crushing)", fos_crush, "—"),
            out("FoS (buckling)", fos_buckling, "—"),
            out("Governing FoS", fos, "—"),
        ],
        "fos": fos,
        "status": "SAFE" if safe else "UNSAFE",
        "safe": safe,
        "assumptions": [
            "Concentric (no eccentricity) compressive load on a prismatic column.",
            "Euler's formula assumes a perfectly straight, linearly elastic column with pinned theoretical ends modified by K.",
            "Euler P_cr is the theoretical bifurcation load. Real columns have imperfections, so design codes use much larger safety margins and different formulas (e.g. AISC, Eurocode 3).",
            "Euler theory is intended for slender columns. Very stocky columns are governed by crushing / yielding, which is why the smaller of P_crush and P_cr is used.",
            "Residual stresses, local buckling, and crookedness are not modelled.",
            "SAFE means the applied load does not exceed the governing capacity (governing FoS ≥ 1).",
        ],
    }


def _beam(form: Mapping[str, str]) -> dict[str, Any]:
    """
    Simply supported prismatic beam, elastic flexure.

    Point load at midspan:  M_max = P L / 4
                            δ_max = P L³ / (48 E I)
                            V_max = P / 2
    Uniform load w:         M_max = w L² / 8
                            δ_max = 5 w L⁴ / (384 E I)
                            V_max = w L / 2
    Bending stress:         σ = M c / I
    Rectangle:              I = b h³ / 12 ,  c = h / 2  →  σ = 6 M / (b h²)
    """
    errors: dict[str, str] = {}

    load_type = _get_str(form, "beam_load_type") or "point_midspan"
    if load_type not in ("point_midspan", "udl"):
        errors["beam_load_type"] = "Select a valid beam load type."

    section = _get_str(form, "beam_section") or "rectangle"
    if section not in ("rectangle", "custom"):
        errors["beam_section"] = "Select a valid cross-section type."

    l_unit = _unit(form, "length_unit", LENGTH_TO_M, "m")
    e_unit = _unit(form, "e_unit", STRESS_TO_PA, "GPa")
    dim_unit = _unit(form, "dim_unit", LENGTH_TO_M, "mm")
    i_unit = _unit(form, "inertia_unit", I_TO_M4, "mm4")

    length = _parse_float(form, "length", "Span length L", errors)
    e_val = _parse_float(form, "youngs_modulus", "Young's modulus", errors)
    sigma_allow = _parse_float(form, "allowable_stress", "Allowable bending stress", errors)

    p = w = None
    p_unit = "kN"
    w_unit = "kN/m"
    if load_type == "point_midspan":
        p_unit = _unit(form, "force_unit", FORCE_TO_N, "kN")
        p = _parse_float(form, "force", "Concentrated load P", errors)
    else:
        w_unit = _unit(form, "udl_unit", UDL_TO_NPM, "kN/m")
        w = _parse_float(form, "udl", "Uniform load w", errors)

    b = h = i_val = c_val = None
    if section == "rectangle":
        b = _parse_float(form, "width", "Section width b", errors)
        h = _parse_float(form, "height", "Section height h", errors)
    else:
        i_val = _parse_float(form, "inertia", "Moment of inertia I", errors)
        c_val = _parse_float(form, "section_c", "Distance c to extreme fibre", errors)

    if errors:
        raise ValidationError(errors)

    l_m = _si(length, l_unit, LENGTH_TO_M)
    e_pa = _si(e_val, e_unit, STRESS_TO_PA)
    allow_pa = _si(sigma_allow, "MPa", STRESS_TO_PA)
    assert l_m is not None and e_pa is not None and allow_pa is not None

    if load_type == "point_midspan":
        p_n = _si(p, p_unit, FORCE_TO_N)
        m_max = p_n * l_m / 4.0  # N·m
        v_max = p_n / 2.0
        load_label = f"Midspan point load P = {fmt(p)} {p_unit}"
        m_formula = "M_max = P L / 4"
        d_formula = "δ_max = P L³ / (48 E I)"
        v_formula = "V_max = P / 2"
    else:
        w_npm = _si(w, w_unit, UDL_TO_NPM)
        p_n = None
        m_max = w_npm * l_m ** 2 / 8.0
        v_max = w_npm * l_m / 2.0
        load_label = f"Uniform load w = {fmt(w)} {w_unit}"
        m_formula = "M_max = w L² / 8"
        d_formula = "δ_max = 5 w L⁴ / (384 E I)"
        v_formula = "V_max = w L / 2"

    if section == "rectangle":
        b_m = _si(b, dim_unit, LENGTH_TO_M)
        h_m = _si(h, dim_unit, LENGTH_TO_M)
        i_m4 = b_m * (h_m ** 3) / 12.0
        c_m = h_m / 2.0
        section_note = f"Rectangle b × h = {fmt(b)} × {fmt(h)} {dim_unit}"
        i_step = (
            f"I = b h³ / 12 = {fmt(b_m)} × ({fmt(h_m)})³ / 12 = {fmt(i_m4)} m⁴"
        )
        c_step = f"c = h / 2 = {fmt(c_m)} m"
    else:
        i_m4 = _si(i_val, i_unit, I_TO_M4)
        c_m = _si(c_val, dim_unit, LENGTH_TO_M)
        section_note = f"Custom section I = {fmt(i_val)} {i_unit}, c = {fmt(c_val)} {dim_unit}"
        i_step = f"I = {fmt(i_m4)} m⁴ (entered)"
        c_step = f"c = {fmt(c_m)} m (entered)"

    sigma_pa = m_max * c_m / i_m4  # Pa
    sigma_mpa = sigma_pa / 1.0e6
    fos = allow_pa / sigma_pa
    safe = sigma_pa <= allow_pa

    if load_type == "point_midspan":
        delta_m = p_n * (l_m ** 3) / (48.0 * e_pa * i_m4)
        d_step = (
            f"δ_max = P L³ / (48 E I) = {fmt(p_n)} × ({fmt(l_m)})³ / "
            f"(48 × {fmt(e_pa)} × {fmt(i_m4)}) = {fmt(delta_m)} m = {fmt(delta_m * 1000.0)} mm"
        )
    else:
        delta_m = 5.0 * w_npm * (l_m ** 4) / (384.0 * e_pa * i_m4)
        d_step = (
            f"δ_max = 5 w L⁴ / (384 E I) = 5 × {fmt(w_npm)} × ({fmt(l_m)})⁴ / "
            f"(384 × {fmt(e_pa)} × {fmt(i_m4)}) = {fmt(delta_m)} m = {fmt(delta_m * 1000.0)} mm"
        )

    steps = [
        f"Simply supported span L = {fmt(length)} {l_unit} = {fmt(l_m)} m",
        load_label,
        f"{m_formula} = {fmt(m_max)} N·m = {fmt(m_max / 1000.0)} kN·m",
        f"{v_formula} = {fmt(v_max)} N = {fmt(v_max / 1000.0)} kN",
        section_note,
        i_step,
        c_step,
        f"Bending stress: σ = M c / I = {fmt(m_max)} × {fmt(c_m)} / {fmt(i_m4)} = {fmt(sigma_mpa)} MPa",
        f"FoS = σ_allow / σ = {fmt(sigma_allow)} / {fmt(sigma_mpa)} = {fmt(fos)}",
        d_step,
    ]

    inputs = [
        ("Load case", load_label),
        ("Span L", f"{fmt(length)} {l_unit}"),
        ("Section", section_note),
        ("Young's modulus E", f"{fmt(e_val)} {e_unit}"),
        ("Allowable bending stress", f"{fmt(sigma_allow)} MPa"),
    ]

    return {
        "case_name": "Simply supported beam (elastic bending)",
        "inputs": inputs,
        "formula": [
            m_formula,
            v_formula,
            "σ = M c / I",
            "Rectangle: I = b h³ / 12, c = h / 2",
            d_formula,
            "FoS = σ_allow / σ",
        ],
        "steps": steps,
        "outputs": [
            out("Maximum moment M_max", m_max / 1000.0, "kN·m"),
            out("Maximum shear V_max", v_max / 1000.0, "kN"),
            out("Second moment of area I", i_m4, "m⁴"),
            out("Bending stress σ", sigma_mpa, "MPa"),
            out("Midspan deflection δ_max", delta_m * 1000.0, "mm"),
            out("Factor of safety FoS", fos, "—"),
        ],
        "fos": fos,
        "status": "SAFE" if safe else "UNSAFE",
        "safe": safe,
        "assumptions": [
            "Simply supported beam of constant cross-section (prismatic).",
            "Point load is applied at midspan only. UDL is constant along the full span.",
            "Euler–Bernoulli beam theory: plane sections remain plane; shear deformation is neglected in the deflection formula.",
            "Linear-elastic material; small deflections.",
            "Self-weight is not added unless you include it in P or w.",
            "Lateral-torsional buckling, support settlement, and shear stress checks are not included here (use Shear Stress for τ).",
            "SAFE means σ_bending ≤ σ_allow (FoS ≥ 1). Deflection is reported but does not change the SAFE/UNSAFE flag.",
        ],
    }


def _shear(form: Mapping[str, str]) -> dict[str, Any]:
    """
    Transverse shear stress.

    Average (engineering):     tau = V / A
    Rectangular beam (max):    tau_max = 1.5 V / A     at the neutral axis
    Circular section (max):    tau_max = 4 V / (3 A)   at the centre
    """
    errors: dict[str, str] = {}

    shear_case = _get_str(form, "shear_case") or "average"
    if shear_case not in ("average", "rectangle", "circular"):
        errors["shear_case"] = "Select a valid shear stress case."

    v_unit = _unit(form, "force_unit", FORCE_TO_N, "kN")
    a_unit = _unit(form, "area_unit", AREA_TO_M2, "mm2")

    v = _parse_float(form, "force", "Shear force V", errors)
    tau_allow = _parse_float(form, "allowable_stress", "Allowable shear stress", errors)
    a = _parse_float(form, "area", "Cross-sectional area", errors)

    if errors:
        raise ValidationError(errors)

    v_n = _si(v, v_unit, FORCE_TO_N)
    a_m2 = _si(a, a_unit, AREA_TO_M2)
    allow_pa = _si(tau_allow, "MPa", STRESS_TO_PA)
    assert v_n is not None and a_m2 is not None and allow_pa is not None

    tau_avg_pa = v_n / a_m2

    if shear_case == "average":
        tau_pa = tau_avg_pa
        formula = "τ = V / A  (average shear stress)"
        factor_note = "Average shear uses the full area with no shape factor."
        case_name = "Average shear stress"
    elif shear_case == "rectangle":
        tau_pa = 1.5 * tau_avg_pa
        formula = "τ_max = (3/2) V / A  (rectangular beam, at the neutral axis)"
        factor_note = "For a rectangle, the Jourawski formula τ = V Q / (I t) reduces to 1.5 V/A at the NA."
        case_name = "Maximum shear stress — rectangular section"
    else:
        tau_pa = (4.0 / 3.0) * tau_avg_pa
        formula = "τ_max = (4/3) V / A  (solid circular section, at the centre)"
        factor_note = "For a solid circle, τ = V Q / (I t) reduces to 4V/(3A) at the centre."
        case_name = "Maximum shear stress — circular section"

    tau_mpa = tau_pa / 1.0e6
    tau_avg_mpa = tau_avg_pa / 1.0e6
    fos = allow_pa / tau_pa
    safe = tau_pa <= allow_pa

    steps = [
        f"Shear force: V = {fmt(v)} {v_unit} = {fmt(v_n)} N",
        f"Area: A = {fmt(a)} {a_unit} = {fmt(a_m2)} m²",
        f"Average shear: τ_avg = V / A = {fmt(v_n)} / {fmt(a_m2)} = {fmt(tau_avg_mpa)} MPa",
        factor_note,
        f"Design shear stress: {formula.split('  ')[0]} = {fmt(tau_mpa)} MPa",
        f"FoS = τ_allow / τ = {fmt(tau_allow)} / {fmt(tau_mpa)} = {fmt(fos)}",
    ]

    return {
        "case_name": case_name,
        "inputs": [
            ("Shear force V", f"{fmt(v)} {v_unit}"),
            ("Area A", f"{fmt(a)} {a_unit}"),
            ("Shear case", case_name),
            ("Allowable shear stress", f"{fmt(tau_allow)} MPa"),
        ],
        "formula": [
            "τ_avg = V / A",
            formula,
            "FoS = τ_allow / τ",
        ],
        "steps": steps,
        "outputs": [
            out("Average shear τ_avg", tau_avg_mpa, "MPa"),
            out("Governing shear stress τ", tau_mpa, "MPa"),
            out("Factor of safety FoS", fos, "—"),
        ],
        "fos": fos,
        "status": "SAFE" if safe else "UNSAFE",
        "safe": safe,
        "assumptions": [
            "V is the transverse shear force on the cross-section (not an axial load).",
            "Average shear τ = V/A is an engineering approximation; the true peak depends on the shape.",
            "Rectangular and circular maxima come from the elastic formula τ = VQ/(I t) for a homogeneous section.",
            "Torsion, punching shear, and reinforced-concrete shear (stirrups, aggregate interlock) are not modelled.",
            "SAFE means the governing shear stress ≤ allowable shear stress (FoS ≥ 1).",
        ],
    }
