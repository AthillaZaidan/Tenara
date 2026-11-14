"""3D try-on preview: the buyer's body, rebuilt from their confirmed measurements, wearing the design.

    1. shape    Gauss-Newton on the SMPL-X shape (betas) so that body3d.measure() returns the buyer's
                confirmed measurements and height. It works the same for estimated and hand-entered
                sets, and only the numbers are used: no photo is needed to view the result.
    2. garment  A loft over the body standing with arms lowered: at each height the cross-section of
                the trunk is taken as a convex hull (what a tape measure follows), pushed outward by
                the template's ease, and the rings are joined into a tube; sleeves are lofted the same
                way along the arm bones. Lengths come from the template and the design's deltas.
                There is no cloth simulation: it shows proportions, ease and fabric scale, not drape.
    3. export   One GLB: the body as a plain grey mannequin, the garment textured with the listing
                photo at a real-world scale (TILE_M of fabric per repeat).

SMPL-X is non-commercial research and education only (see body3d); the mesh made here is derived from it.
"""
from __future__ import annotations

import io
import itertools
import math
from dataclasses import dataclass, field

import numpy as np
from PIL import Image

from app.ml.vision import body3d
from app.ml.vision.body3d import (
    L_ELBOW,
    L_SHOULDER,
    L_WRIST,
    LM,
    NECK,
    NUM_BETAS,
    R_ELBOW,
    R_SHOULDER,
    R_WRIST,
)
from app.ml.vision.render import BUTTON_COLORS

METHOD = "smplx_measurement_loft_v1"
ARM_DROP = 1.15  # shoulder rotation from the T-pose, rad: arms hang about 25 degrees from the body
COLUMNS = 72  # points per ring; 5 degrees each
STEP_M = 0.02  # ring spacing
TILE_M = 0.60  # one texture repeat: a 2x2 mirrored tile, each quarter about 30 cm of fabric
MISMATCH_CM = 3.0
SLEEVE_START_M = 0.07  # below the shoulder ball, whose cut is far wider than the arm
# trunk faces (by SMPL-X part = joint index) that the torso rings wrap; thighs too, so a long hem
# goes round both legs like a skirt instead of splitting into trouser legs
TRUNK_PARTS = [0, 1, 2, 3, 4, 5, 6, 9, 13, 14]
ARM_PARTS = {"left": [16, 18, 20], "right": [17, 19, 21]}
MANNEQUIN_RGBA = [196, 190, 184, 255]
# DEMO values, like the template definitions: garment length below the base of the neck (on top of
# the back length) and the sleeve, per template. None = sleeveless; "full" = to the wrist.
SHAPES = {
    "T01": {"below_waist_cm": 20, "sleeve": 22},
    "T02": {"below_waist_cm": 16, "sleeve": "full"},
    "T03": {"below_waist_cm": 12, "sleeve": None},
    "T04": {"below_waist_cm": 42, "sleeve": "full"},
    "T05": {"below_waist_cm": 55, "sleeve": "full"},
}
NOT_DRAWN = {"collar": {"classic", "mandarin"}, "pockets": None, "trim": None}
LABELS = {"chest_circumference": "lingkar dada", "waist_circumference": "lingkar pinggang",
          "hip_circumference": "lingkar pinggul", "shoulder_width": "lebar bahu", "back_length": "panjang punggung",
          "sleeve_length": "panjang lengan", "neck_circumference": "lingkar leher",
          "collar": "kerah", "pockets": "saku", "trim": "rumbai"}


@dataclass
class Avatar:
    glb: bytes
    fitted: dict[str, float]  # measurements of the rebuilt body, cm
    warnings: list[str] = field(default_factory=list)


def fabric_texture(data: bytes, size: int = 256) -> Image.Image:
    """The middle of the listing photo (its edges are often background), mirrored 2x2 so repeats have
    no seams."""
    from PIL import ImageOps

    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    side = int(min(img.size) * 0.7)
    left, top = (img.width - side) // 2, (img.height - side) // 2
    tile = img.crop((left, top, left + side, top + side)).resize((size, size))
    out = Image.new("RGB", (2 * size, 2 * size))
    out.paste(tile, (0, 0))
    out.paste(ImageOps.mirror(tile), (size, 0))
    out.paste(ImageOps.flip(tile), (0, size))
    out.paste(ImageOps.flip(ImageOps.mirror(tile)), (size, size))
    return out


# ---------- 1. shape from measurements ----------

def shape_for(body, height_cm: float, values: dict[str, float], iters: int = 20,
              prior: float = 0.05, step: float = 0.5) -> tuple[np.ndarray, dict[str, float]]:
    """Betas whose T-pose body measures as `values` (cm) at `height_cm`; also its measurements."""
    keys = [k for k, v in values.items() if v is not None] + ["height"]
    target = np.array([float(values[k]) for k in keys[:-1]] + [float(height_cm)])
    weight = np.array([1.0] * (len(keys) - 1) + [3.0])  # height sets the scale of everything else

    def f(b):
        m = body3d.measure(body, b)
        return np.array([m[k] for k in keys])

    betas = np.zeros(NUM_BETAS)
    current = f(betas)
    for _ in range(iters):
        jac = np.empty((len(keys), NUM_BETAS))
        for i in range(NUM_BETAS):
            d = np.zeros(NUM_BETAS)
            d[i] = step
            jac[:, i] = (f(betas + d) - current) / step
        jw, r = jac * weight[:, None], (current - target) * weight
        delta = -np.linalg.solve(jw.T @ jw + prior * np.eye(NUM_BETAS), jw.T @ r + prior * betas)
        for scale in (1.0, 0.5, 0.25):  # damped: keep a step only if it helps
            trial = np.clip(betas + scale * delta, -4.0, 4.0)
            got = f(trial)
            if np.sum(((got - target) * weight) ** 2) < np.sum(r ** 2):
                betas, current = trial, got
                break
        else:
            break
    return betas, dict(zip(keys, (round(float(x), 1) for x in current), strict=True))


def _posed(body, betas: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    torch = body.torch
    pose = torch.zeros(1, 63)
    pose[0, (L_SHOULDER - 1) * 3 + 2] = -ARM_DROP
    pose[0, (R_SHOULDER - 1) * 3 + 2] = ARM_DROP
    with torch.no_grad():
        out = body.model(betas=torch.tensor(betas, dtype=torch.float32)[None], body_pose=pose)
    return out.vertices[0].numpy().astype(np.float64), out.joints[0].numpy().astype(np.float64)


# ---------- 2. garment loft ----------

ANGLES = np.arange(COLUMNS + 1) * 2 * math.pi / COLUMNS  # last column repeats the first (texture seam)
FRONT = math.pi / 2  # torso rings: angle 0 = the wearer's left (+x), 90 degrees = front (+z)


def _ray_radii(hull: np.ndarray, center: np.ndarray, angles: np.ndarray) -> np.ndarray:
    """Distance from `center` to the convex polygon's edge along each angle."""
    a, b = hull, np.roll(hull, -1, axis=0)
    e = b - a
    d = np.stack([np.cos(angles), np.sin(angles)], axis=1)
    ac = a - center
    den = d[:, None, 0] * e[None, :, 1] - d[:, None, 1] * e[None, :, 0]
    with np.errstate(divide="ignore", invalid="ignore"):
        t = (ac[None, :, 0] * e[None, :, 1] - ac[None, :, 1] * e[None, :, 0]) / den
        s = (ac[None, :, 0] * d[:, None, 1] - ac[None, :, 1] * d[:, None, 0]) / den
    ok = (s >= -1e-9) & (s <= 1 + 1e-9) & (t > 0)
    return np.where(ok, t, np.inf).min(axis=1)


def _section(mesh, face_part, point, normal, u, v, parts) -> tuple[np.ndarray, np.ndarray] | None:
    """Convex cross-section (2D, in the u/v basis) of the faces of `parts` cut by a plane, and its centre."""
    import trimesh

    segs, fidx = trimesh.intersections.mesh_plane(mesh, normal, point, return_faces=True)
    pts = segs[np.isin(face_part[fidx], parts)].reshape(-1, 3)
    if len(pts) < 3:
        return None
    hull = body3d.convex_hull(np.stack([(pts - point) @ u, (pts - point) @ v], axis=1))
    if len(hull) < 3:
        return None
    return hull, _centroid(hull)


def _centroid(poly: np.ndarray) -> np.ndarray:
    """Area centroid: unlike the mean of the hull's corners it does not move with where the corners fall."""
    x, y = poly[:, 0], poly[:, 1]
    xn, yn = np.roll(x, -1), np.roll(y, -1)
    cross = x * yn - xn * y
    area = cross.sum() / 2
    if abs(area) < 1e-12:
        return poly.mean(axis=0)
    return np.array([((x + xn) * cross).sum(), ((y + yn) * cross).sum()]) / (6 * area)


def _radii(hull, center) -> np.ndarray:
    r = _ray_radii(hull, center, ANGLES)
    return np.where(np.isfinite(r), r, np.nan)


def _drape(radii: np.ndarray, start: int, step: int, taper: float, flare: float = np.inf) -> np.ndarray:
    """Cloth hangs instead of following hollows: going from `start` in direction `step`, each ring
    is at least `taper` times the one before it (and at most `flare` times), then smoothed."""
    r = radii.copy()
    r = np.where(np.isnan(r), np.nanmax(r, axis=1, keepdims=True), r)
    i = start + step
    while 0 <= i < len(r):
        r[i] = np.minimum(np.maximum(r[i], taper * r[i - step]), flare * r[i - step])
        i += step
    return _smooth(r)


def _smooth(rows: np.ndarray, passes: int = 2) -> np.ndarray:
    rows = np.array(rows, dtype=float)
    for _ in range(passes):
        if len(rows) >= 3:
            rows[1:-1] = (rows[:-2] + 2 * rows[1:-1] + rows[2:]) / 4
    return rows


def _ring(point, u, v, center, radii) -> np.ndarray:
    xy = center + radii[:, None] * np.stack([np.cos(ANGLES), np.sin(ANGLES)], axis=1)
    return point + xy[:, :1] * u + xy[:, 1:] * v


def _tube(rings: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Vertices, quad-split faces and UVs of rings stacked in order; UVs are metres / TILE_M."""
    verts = np.concatenate(rings)
    n = COLUMNS + 1
    girth = float(np.mean([np.linalg.norm(np.diff(r, axis=0), axis=1).sum() for r in rings]))
    along = np.concatenate([[0.0], np.cumsum([np.linalg.norm(b.mean(0) - a.mean(0))
                                              for a, b in itertools.pairwise(rings)])])
    uv = np.stack([np.tile(ANGLES / (2 * math.pi) * girth, len(rings)), np.repeat(along, n)], axis=1) / TILE_M
    faces = []
    for i in range(len(rings) - 1):
        for j in range(COLUMNS):
            a, b = i * n + j, (i + 1) * n + j
            faces += [(a, a + 1, b + 1), (a, b + 1, b)]
    return verts, np.array(faces, dtype=np.int64), uv


@dataclass
class _Piece:
    verts: np.ndarray
    faces: np.ndarray
    uv: np.ndarray
    row_y: np.ndarray  # per face: height of the face (torso) or -inf (sleeves)
    angle: np.ndarray  # per face: centre angle
    hem: np.ndarray  # per face: distance from the hem, m


def _face_meta(rings: list[np.ndarray], from_hem: np.ndarray, heights: np.ndarray) -> tuple:
    rows = np.repeat(np.arange(len(rings) - 1), 2 * COLUMNS)
    cols = np.tile(np.repeat(np.arange(COLUMNS), 2), len(rings) - 1)
    mid = (ANGLES[cols] + ANGLES[cols + 1]) / 2
    return heights[rows], mid, from_hem[rows]


def _torso(mesh, body, joints, hem_y, neck_y, chest_y, offset, neck_cm, sleeved: bool) -> _Piece:
    up, u, v = np.array([0.0, 1.0, 0.0]), np.array([1.0, 0.0, 0.0]), np.array([0.0, 0.0, 1.0])
    top_y = (joints[L_SHOULDER][1] + joints[R_SHOULDER][1]) / 2 - 0.02
    points, centers, radii = [], [], []
    for y in np.arange(hem_y, top_y, STEP_M):
        point = np.array([joints[NECK][0], y, joints[NECK][2]])
        # above the armpit the cloth also covers the shoulder balls (a sleeve starts below them)
        parts = TRUNK_PARTS + ([L_SHOULDER, R_SHOULDER] if sleeved and y > top_y - 0.06 else [])
        sec = _section(mesh, body.face_part, point, up, u, v, parts)
        if sec is not None:
            points.append(point)
            centers.append(sec[1])
            radii.append(_radii(*sec))
    heights = [p[1] for p in points]
    chest = int(np.argmin(np.abs(np.array(heights) - chest_y)))
    radii = _drape(np.array(radii), chest, -1, taper=0.99) + offset  # below the chest the cloth hangs
    rings = [_ring(p, u, v, c, r) for p, c, r in zip(points, _smooth(centers), radii, strict=True)]
    # shoulders: slope from the last trunk ring up to a ring round the base of the neck, rounded at
    # the outside as the height rises fast at first
    neck_y += 0.015
    neck_r = neck_cm / 100 / (2 * math.pi) + 0.02
    neck_c = np.array([joints[NECK][0], neck_y, joints[NECK][2]])
    neck_ring = neck_c + neck_r * (np.cos(ANGLES)[:, None] * u + np.sin(ANGLES)[:, None] * v)
    last, y0 = rings[-1], heights[-1]
    for k in range(1, 7):
        t = k / 6
        rise, narrow = math.sin(t * math.pi / 2), t
        ring = (1 - narrow) * last + narrow * neck_ring
        ring[:, 1] = (1 - rise) * y0 + rise * neck_y
        rings.append(ring)
        heights.append((1 - rise) * y0 + rise * neck_y)
    heights = np.array(heights)
    pv, pf, puv = _tube(rings)
    return _Piece(pv, pf, puv, *_face_meta(rings, heights - hem_y, heights))


def _sleeve(mesh, body, joints, side: str, length_m: float, offset: float) -> _Piece | None:
    sh, el, wr = ((L_SHOULDER, L_ELBOW, L_WRIST) if side == "left" else (R_SHOULDER, R_ELBOW, R_WRIST))
    path = [joints[sh], joints[el], joints[wr]]
    seg = [np.linalg.norm(path[1] - path[0]), np.linalg.norm(path[2] - path[1])]
    dirs = [(path[1] - path[0]) / seg[0], (path[2] - path[1]) / seg[1]]
    length_m = min(length_m, sum(seg))
    frames, centers, radii, dist = [], [], [], []
    for s in np.arange(SLEEVE_START_M, length_m + 1e-9, STEP_M):
        point = path[0] + s * dirs[0] if s <= seg[0] else path[1] + (s - seg[0]) * dirs[1]
        w = float(np.clip((s - seg[0] + 0.05) / 0.10, 0, 1))  # turn the rings gradually round the elbow
        direction = (1 - w) * dirs[0] + w * dirs[1]
        direction /= np.linalg.norm(direction)
        u = np.cross(direction, [0.0, 0.0, 1.0])
        u /= np.linalg.norm(u)
        v = np.cross(direction, u)
        sec = _section(mesh, body.face_part, point, direction, u, v, ARM_PARTS[side])
        if sec is None:
            continue
        frames.append((point, u, v))
        centers.append(sec[1])
        radii.append(_radii(*sec))
        dist.append(s)
    if len(frames) < 2:
        return None
    # the cut through the shoulder ball is much wider than the arm: shape from the upper arm, letting
    # the sleeve narrow slowly towards the cuff and widen only a little towards the shoulder
    k = int(np.argmin(np.abs(np.array(dist) - 0.12)))
    radii = np.array(radii)
    radii[k:] = _drape(radii[k:], 0, 1, taper=0.97, flare=1.02)
    radii[:k + 1] = _drape(radii[:k + 1], k, -1, taper=0.9, flare=1.04)
    rings = [_ring(p, u, v, c, r + offset)
             for (p, u, v), c, r in zip(frames, _smooth(centers), radii, strict=True)]
    # close the seam: the top ring continues sideways into the body, under the torso's cloth (along
    # the arm it would rise above the shoulder line)
    inward = np.array([-np.sign(path[0][0] - joints[NECK][0]), 0.0, 0.0])
    rings.insert(0, rings[0] + 0.06 * inward)
    dist.insert(0, dist[0] - 0.06)
    dist = np.array(dist)
    pv, pf, puv = _tube(rings)
    _, angle, hem = _face_meta(rings, dist.max() - dist, dist)
    return _Piece(pv, pf, puv, np.full(len(pf), -np.inf), angle, hem)
def _clear(piece: _Piece, body_verts: np.ndarray, normals: np.ndarray, gap: float) -> None:
    """Push garment points that ended up inside the body back out, `gap` above the skin."""
    from scipy.spatial import cKDTree

    _, idx = cKDTree(body_verts).query(piece.verts)
    depth = np.einsum("ij,ij->i", piece.verts - body_verts[idx], normals[idx])
    inside = depth < gap
    piece.verts[inside] += (gap - depth[inside])[:, None] * normals[idx[inside]]


def _angle_off_front(angle: np.ndarray) -> np.ndarray:
    return np.abs((angle - FRONT + math.pi) % (2 * math.pi) - math.pi)


def _keep(piece: _Piece, state: dict, neck_y: float) -> np.ndarray:
    """Faces left after cutting the neckline and front opening."""
    off = _angle_off_front(piece.angle)
    keep = np.ones(len(piece.faces), dtype=bool)
    if state.get("collar") in ("v_neck", "shawl") or state.get("closure") == "open_front":
        depth = 0.16 if state.get("collar") != "shawl" else 0.24
        frac = np.clip((piece.row_y - (neck_y - depth)) / depth, 0, 1)
        keep &= off >= np.radians(32) * frac  # sleeves: row_y is -inf, so frac is 0 and all stay
    if state.get("closure") == "open_front":
        keep &= (off >= np.radians(5)) | (piece.row_y == -np.inf)
    return keep


def _textured(piece: _Piece, placement: str, chest_y: float) -> np.ndarray:
    """Faces that show the woven motif; the rest take the fabric's plain average colour."""
    torso = piece.row_y != -np.inf
    if placement == "hem_border":
        return piece.hem < np.where(torso, 0.10, 0.05)
    if placement == "center_front":
        return torso & (_angle_off_front(piece.angle) < np.radians(25))
    if placement == "left_chest":  # the wearer's left is +x, i.e. angles just below the front
        return torso & (piece.angle > np.radians(50)) & (piece.angle < np.radians(82)) \
            & (np.abs(piece.row_y - chest_y) < 0.08)
    return np.ones(len(piece.faces), dtype=bool)


def _buttons(torso: _Piece, state: dict, hem_y: float, neck_y: float):
    import trimesh

    if "buttons" not in state or state.get("closure") not in (None, "buttons_front"):
        return None
    front_col = round(FRONT / (2 * math.pi) * COLUMNS)
    n = COLUMNS + 1
    rows = torso.verts.reshape(-1, n, 3)[:, front_col]
    color = list(BUTTON_COLORS.get(state["buttons"], (200, 200, 200))) + [255]
    spheres = []
    top = neck_y - (0.18 if state.get("collar") == "v_neck" else 0.06)
    for y in np.arange(top, hem_y + 0.06, -0.09):
        p = rows[np.argmin(np.abs(rows[:, 1] - y))] + [0.0, 0.0, 0.004]
        s = trimesh.creation.icosphere(subdivisions=2, radius=0.0065)
        s.apply_translation(p)
        s.visual.vertex_colors = color
        spheres.append(s)
    return trimesh.util.concatenate(spheres) if spheres else None


# ---------- 3. assembling and exporting ----------

def _material(texture: Image.Image | None, rgba):
    from trimesh.visual.material import PBRMaterial

    return PBRMaterial(baseColorTexture=texture, baseColorFactor=rgba, metallicFactor=0.0,
                       roughnessFactor=0.92, doubleSided=True)


def _sub(piece: _Piece, faces_mask: np.ndarray, material):
    import trimesh

    mesh = trimesh.Trimesh(vertices=piece.verts, faces=piece.faces[faces_mask], process=False)
    mesh.visual = trimesh.visual.TextureVisuals(uv=piece.uv, material=material)
    mesh.remove_unreferenced_vertices()
    return mesh


def build(body, template_code: str, state: dict, ease_cm: float, height_cm: float,
          values: dict[str, float], texture: Image.Image) -> Avatar:
    import trimesh

    betas, fitted = shape_for(body, height_cm, values)
    warnings = []
    for key, target in values.items():
        if target is not None and abs(fitted[key] - float(target)) > MISMATCH_CM:
            warnings.append(f"avatar_mismatch:{key}: avatar hanya bisa mendekati {LABELS.get(key, key)} Anda "
                            f"({float(target):.1f} cm; avatar {fitted[key]:.1f} cm). Ukuran yang dikirim ke "
                            "penjahit tetap angka Anda.")
    verts, joints = _posed(body, betas)
    mesh = trimesh.Trimesh(vertices=verts, faces=body.faces, process=False)
    shape = SHAPES[template_code]
    neck_y = verts[LM["SHOULDER_TOP"]][1]
    waist_y = verts[LM["BACK_BELLY_BUTTON"]][1]
    chest_y = (verts[LM["LEFT_NIPPLE"]][1] + verts[LM["RIGHT_NIPPLE"]][1]) / 2
    hem_y = waist_y - (shape["below_waist_cm"] + float(state.get("hem_length_delta_cm") or 0)) / 100
    offset = ease_cm / 100 / (2 * math.pi) + 0.006  # ease is a circumference; 6 mm keeps cloth off skin
    pieces = [_torso(mesh, body, joints, hem_y, neck_y, chest_y, offset, fitted.get("neck_circumference", 38.0),
                     shape["sleeve"] is not None)]
    if shape["sleeve"] is not None:
        base = fitted["sleeve_length"] if shape["sleeve"] == "full" else shape["sleeve"]
        length = (base + float(state.get("sleeve_length_delta_cm") or 0)) / 100
        for side in ("left", "right"):
            sleeve = _sleeve(mesh, body, joints, side, length, 0.7 * offset)
            if sleeve is not None:
                pieces.append(sleeve)
    # torso cloth clears the trunk only (the arms hang next to it); sleeves clear only their arm, so
    # the tucked-in top ring stays under the torso cloth
    normals = np.asarray(mesh.vertex_normals)
    arm = np.isin(body.vertex_part, [p for side in ARM_PARTS.values() for p in side] + list(range(25, 55)))
    shoulder_y = (joints[L_SHOULDER][1] + joints[R_SHOULDER][1]) / 2
    caps = np.isin(body.vertex_part, [L_SHOULDER, R_SHOULDER]) & (verts[:, 1] > shoulder_y - 0.06)
    trunk = (~arm & np.isin(body.vertex_part, TRUNK_PARTS + [NECK])) | caps
    _clear(pieces[0], verts[trunk], normals[trunk], 0.006)
    for piece, side in zip(pieces[1:], ARM_PARTS.values(), strict=False):
        own = np.isin(body.vertex_part, side)
        _clear(piece, verts[own], normals[own], 0.004)
    plain_rgba = [*np.asarray(texture.convert("RGB")).reshape(-1, 3).mean(axis=0).astype(int).tolist(), 255]
    textured, plain = _material(texture, [255, 255, 255, 255]), _material(None, plain_rgba)
    scene = trimesh.Scene()
    body_mesh = trimesh.Trimesh(vertices=verts, faces=body.faces, process=False)
    body_mesh.visual.vertex_colors = MANNEQUIN_RGBA
    scene.add_geometry(body_mesh, node_name="body", geom_name="body")
    placement = state.get("motif_placement", "all_over")
    for i, piece in enumerate(pieces):
        keep = _keep(piece, state, neck_y)
        motif = _textured(piece, placement, chest_y)
        for name, mask, mat in (("motif", keep & motif, textured), ("plain", keep & ~motif, plain)):
            if mask.any():
                scene.add_geometry(_sub(piece, mask, mat), node_name=f"garment_{i}_{name}",
                                   geom_name=f"garment_{i}_{name}")
    buttons = _buttons(pieces[0], state, hem_y, neck_y)
    if buttons is not None:
        scene.add_geometry(buttons, node_name="buttons", geom_name="buttons")
    skipped = [k for k, vals in NOT_DRAWN.items() if state.get(k) not in (None, "none")
               and (vals is None or state.get(k) in vals)]
    if skipped:
        warnings.append("not_drawn: " + ", ".join(LABELS[k] for k in skipped)
                        + " belum digambar pada avatar 3D; lihat ilustrasi desain")
    buf = io.BytesIO()
    buf.write(scene.export(file_type="glb", include_normals=True))
    return Avatar(glb=buf.getvalue(), fitted=fitted, warnings=warnings)
