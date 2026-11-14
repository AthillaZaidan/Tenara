"""Motif layout: which part of the actual fabric goes on which part of the garment.

Interpreters and the web speak in region ids of the listing's fabric map ("m1", "z2"). The design
revision stores a snapshot of each region used (id, kind, label, box), so the tailor sees exactly what
the buyer saw even if the map is corrected later.

    stored value: {"panels": {"front" | "back" | "sleeves" | "hem": snapshot}, "avoid": [snapshot, ...]}
    id form:      {"panels": {"front": "m1", ...}, "avoid": ["z1", ...]}
"""
from app.models import FabricMap

PANELS = {"front": "badan depan", "back": "badan belakang", "sleeves": "lengan", "hem": "pinggiran bawah"}
UNUSABLE = {"rumbai"}  # fringe threads cannot be cut into a panel
MAX_AVOID = 10


def usable(fmap: FabricMap | None) -> list[dict]:
    if fmap is None or fmap.status not in ("estimated", "confirmed"):
        return []
    return [r for r in fmap.regions if r["label"] not in UNUSABLE]


def snapshot(region: dict) -> dict:
    return {"region": region["id"], "kind": region["kind"], "label": region["label"], "box": list(region["box"])}


def to_ids(layout: dict | None) -> dict:
    layout = layout or {}
    return {"panels": {p: s["region"] for p, s in (layout.get("panels") or {}).items()},
            "avoid": [s["region"] for s in layout.get("avoid") or []]}


def from_ids(value, fmap: FabricMap | None, current: dict | None) -> dict:
    """Snapshots for an id-form (or already stored) layout; ValueError names what is unknown."""
    if not isinstance(value, dict):
        raise ValueError("motif_layout harus berupa objek {panels, avoid}")  # noqa: TRY004 (callers report ValueError)
    regions = {r["id"]: r for r in usable(fmap)}
    known = {s["region"]: s for s in [*(current or {}).get("panels", {}).values(), *(current or {}).get("avoid", [])]}

    def resolve(ref) -> dict:
        if isinstance(ref, dict):
            return ref  # already a snapshot; checked by templates.validate_value
        if ref in regions:
            return snapshot(regions[ref])
        if ref in known:  # kept from the current design even if the map changed since
            return known[ref]
        names = ", ".join(r["label"] for r in regions.values()) or "belum ada peta kain"
        raise ValueError(f"Bagian kain '{ref}' tidak ada pada peta kain ini; yang ada: {names}")

    panels = {p: resolve(ref) for p, ref in (value.get("panels") or {}).items() if ref is not None}
    avoid = [resolve(ref) for ref in value.get("avoid") or []]
    return {"panels": panels, "avoid": avoid}


def check(spec: dict, value) -> dict:
    """Server-side check of a stored layout against the template's panels."""
    if not isinstance(value, dict) or set(value) - {"panels", "avoid"}:
        raise ValueError("motif_layout harus berupa objek {panels, avoid}")
    panels, avoid = value.get("panels") or {}, value.get("avoid") or []
    if not isinstance(panels, dict) or not isinstance(avoid, list):
        raise ValueError("motif_layout harus berupa objek {panels, avoid}")  # noqa: TRY004 (callers report ValueError)
    for panel in panels:
        if panel not in spec["panels"]:
            raise ValueError(f"Bagian baju '{panel}' tidak ada pada template ini; pilihan: "
                             + ", ".join(PANELS[p] for p in spec["panels"]))
    if len(avoid) > MAX_AVOID:
        raise ValueError(f"Paling banyak {MAX_AVOID} bagian kain yang dihindari")
    out_panels = {p: _snap(s) for p, s in panels.items()}
    out_avoid = [_snap(s) for s in avoid]
    used = {s["region"] for s in out_panels.values()}
    clash = [s["label"] for s in out_avoid if s["region"] in used]
    if clash:
        raise ValueError(f"'{', '.join(clash)}' diminta dipakai sekaligus dihindari; pilih salah satu")
    return {"panels": out_panels, "avoid": out_avoid}


def _snap(s) -> dict:
    try:
        region, kind, label = str(s["region"]), s["kind"], str(s["label"])
        x0, y0, x1, y1 = (float(v) for v in s["box"])
    except (TypeError, KeyError, ValueError):
        raise ValueError("Bagian kain pada motif_layout tidak lengkap (region, kind, label, box)") from None
    if kind not in ("zone", "motif") or not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        raise ValueError("Bagian kain pada motif_layout tidak valid")
    return {"region": region, "kind": kind, "label": label[:40], "box": [x0, y0, x1, y1]}


def describe(layout: dict | None) -> str:
    """One line for people: 'badan depan: manusia; pinggiran bawah: burung; tidak dipakai: kepala kain'."""
    layout = layout or {}
    parts = [f"{PANELS.get(p, p)}: {s['label']}" for p, s in (layout.get("panels") or {}).items()]
    if layout.get("avoid"):
        parts.append("tidak dipakai: " + ", ".join(s["label"] for s in layout["avoid"]))
    return "; ".join(parts) or "otomatis"
