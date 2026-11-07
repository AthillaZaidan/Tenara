"""Garment template definitions (T01-T05).

All numbers are DEMO values. The PRD leaves final bounds, option lists and material rules to tailoring
configuration; changing a definition creates a new template version so quotes stay bound to the
version they were issued against.
"""
import copy

DEMO_NOTICE = "Nilai demo; penjahit/produk mengonfirmasi batas dan aturan akhir."

_BUTTONS = {"type": "enum", "values": ["plain_01", "wood_option_01", "shell_option_01"],
            "default": "plain_01"}
_MOTIF = {"type": "enum", "values": ["all_over", "center_front", "left_chest", "hem_border"],
          "default": "all_over"}


def _num(lo, hi, unit="cm"):
    return {"type": "number", "min": lo, "max": hi, "unit": unit, "default": 0}


def _enum(values, default):
    return {"type": "enum", "values": values, "default": default}


_COMMON_DIMS = ["chest_circumference", "shoulder_width", "back_length"]

DEFINITIONS: dict[str, dict] = {
    "T01": {
        "name": "Kemeja lengan pendek",
        "base_cut": "Blok kemeja lengan pendek standar platform",
        "required_dimensions": [*_COMMON_DIMS, "sleeve_length"],
        "options": {
            "collar": _enum(["classic", "mandarin", "none"], "classic"),
            "pockets": _enum(["none", "left_chest_single", "double_chest"], "none"),
            "buttons": _BUTTONS,
            "hem_length_delta_cm": _num(-10, 10),
            "sleeve_length_delta_cm": _num(-5, 5),
            "motif_placement": _MOTIF,
        },
        "material_rules": {
            "ease_cm": 14, "seam_allowance_cm": 2, "hem_allowance_cm": 4,
            "sleeve_width_ratio": 0.38, "min_fabric_width_cm": 90,
            "option_extra_cm": {"collar": {"classic": 10, "mandarin": 6},
                                "pockets": {"left_chest_single": 12, "double_chest": 24}},
        },
    },
    "T02": {
        "name": "Blouse",
        "base_cut": "Blok blouse standar platform",
        "required_dimensions": [*_COMMON_DIMS, "sleeve_length"],
        "options": {
            "collar": _enum(["round_neck", "v_neck", "mandarin", "none"], "round_neck"),
            "pockets": _enum(["none", "left_chest_single"], "none"),
            "closure": _enum(["buttons_front", "side_zip", "none"], "buttons_front"),
            "buttons": _BUTTONS,
            "hem_length_delta_cm": _num(-8, 8),
            "sleeve_length_delta_cm": _num(-5, 10),
            "motif_placement": _MOTIF,
        },
        "material_rules": {
            "ease_cm": 10, "seam_allowance_cm": 2, "hem_allowance_cm": 4,
            "sleeve_width_ratio": 0.36, "min_fabric_width_cm": 90,
            "option_extra_cm": {"collar": {"v_neck": 4, "mandarin": 6},
                                "pockets": {"left_chest_single": 12}},
        },
    },
    "T03": {
        "name": "Rompi",
        "base_cut": "Blok rompi tanpa lengan standar platform",
        "required_dimensions": list(_COMMON_DIMS),
        "options": {
            "collar": _enum(["v_neck", "round_neck"], "v_neck"),
            "pockets": _enum(["none", "double_welt"], "none"),
            "buttons": _BUTTONS,
            "hem_length_delta_cm": _num(-8, 8),
            "motif_placement": _MOTIF,
        },
        "material_rules": {
            "ease_cm": 12, "seam_allowance_cm": 2, "hem_allowance_cm": 4,
            "sleeve_width_ratio": 0.0, "min_fabric_width_cm": 80,
            "option_extra_cm": {"pockets": {"double_welt": 20}},
        },
    },
    "T04": {
        "name": "Outer",
        "base_cut": "Blok outer standar platform",
        "required_dimensions": [*_COMMON_DIMS, "sleeve_length"],
        "options": {
            "closure": _enum(["open_front", "buttons_front", "tie_front"], "open_front"),
            "collar": _enum(["none", "shawl", "mandarin"], "none"),
            "pockets": _enum(["none", "side_double", "left_chest_single"], "none"),
            "buttons": _BUTTONS,
            "hem_length_delta_cm": _num(-10, 15),
            "sleeve_length_delta_cm": _num(-5, 8),
            "motif_placement": _MOTIF,
        },
        "material_rules": {
            "ease_cm": 20, "seam_allowance_cm": 2.5, "hem_allowance_cm": 5,
            "sleeve_width_ratio": 0.42, "min_fabric_width_cm": 100,
            "option_extra_cm": {"collar": {"shawl": 25, "mandarin": 6},
                                "pockets": {"side_double": 28, "left_chest_single": 12}},
        },
    },
    "T05": {
        "name": "Tunik",
        "base_cut": "Blok tunik standar platform",
        "required_dimensions": [*_COMMON_DIMS, "sleeve_length", "hip_circumference"],
        "options": {
            "collar": _enum(["round_neck", "mandarin", "none"], "round_neck"),
            "pockets": _enum(["none", "side_double"], "none"),
            "buttons": _BUTTONS,
            "hem_length_delta_cm": _num(-10, 15),
            "sleeve_length_delta_cm": _num(-8, 8),
            "trim": {**_enum(["none", "fringe_short", "fringe_long"], "none"),
                     "requires_material_in": ["katun", "sutra", "tenun", "songket", "ikat"]},
            "motif_placement": _MOTIF,
        },
        "material_rules": {
            "ease_cm": 18, "seam_allowance_cm": 2, "hem_allowance_cm": 5,
            "sleeve_width_ratio": 0.38, "min_fabric_width_cm": 100,
            "option_extra_cm": {"collar": {"mandarin": 6},
                                "pockets": {"side_double": 24},
                                "trim": {"fringe_short": 8, "fringe_long": 15}},
        },
    },
}

for _code, _def in DEFINITIONS.items():
    _def["code"] = _code
    _def["demo_values_notice"] = DEMO_NOTICE
    _def["preview"] = {"asset": f"{_code.lower()}_flat", "renders": ["product", "on_body"]}


def definition(code: str) -> dict:
    return copy.deepcopy(DEFINITIONS[code])


def defaults(defn: dict) -> dict:
    return {name: spec["default"] for name, spec in defn["options"].items()}
