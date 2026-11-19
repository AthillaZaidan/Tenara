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
import math
from dataclasses import dataclass, field

import numpy as np
from PIL import Image

from app.ml.vision import body3d, render
from app.ml.vision.body3d import (
    L_ANKLE,
    L_ELBOW,
    L_HIP,
    L_KNEE,
    L_SHOULDER,
    L_WRIST,
    LM,
    NECK,
    NUM_BETAS,
    R_ANKLE,
    R_ELBOW,
    R_HIP,
    R_KNEE,
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
FRINGE_M = {"fringe_short": 0.06, "fringe_long": 0.12}
NOT_DRAWN: dict[str, set | None] = {}  # every template option is drawn; free style is read by style_shape
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
    """Cloth cut from the listing photo, mirrored 2x2 so repeats have no seam. The middle of the photo
    unless it has a plain backdrop, in which case the largest square of cloth alone (a backdrop in the tile
    would repeat as a pale stripe every 30 cm)."""
    from PIL import ImageOps

    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    cut = render.cloth_square(img)
    if cut is None:
        side = int(min(img.size) * 0.7)
        cut = ((img.width - side) // 2, (img.height - side) // 2, side)
    left, top, side = cut
    tile = img.crop((left, top, left + side, top + side)).resize((size, size))
    out = Image.new("RGB", (2 * size, 2 * size))
    out.paste(tile, (0, 0))
    out.paste(ImageOps.mirror(tile), (size, 0))
    out.paste(ImageOps.flip(tile), (0, size))
    out.paste(ImageOps.flip(ImageOps.mirror(tile)), (size, size))
    return out


@dataclass
class PanelTexture:
    """A piece of the actual fabric photo shown on one part of the garment, at real size."""
    image: Image.Image
    tile_w_m: float  # width of one repeat of `image` on the garment
    tile_h_m: float
    label: str


def photo_scale(photo_width_px: int, zone_widths: list[float], fabric_width_cm: float | None) -> tuple[float, bool]:
    """Centimetres per photo pixel. The widest zone (head panel, body, tumpal) spans the cloth's width;
    without a known width 100 cm is assumed. Also says whether it was assumed."""
    span = max(zone_widths, default=0.9) * photo_width_px
    return (fabric_width_cm or 100.0) / max(span, 1.0), fabric_width_cm is None


def _trim_background(crop: Image.Image, min_std: float = 10.0) -> Image.Image:
    """Cut away edges a box drawn to the photo's edge picked up: plain rows and columns (paper, wall, mount)
    and then edge lines whose brightness stands out from the cloth inside."""
    g = np.asarray(crop.convert("L"), dtype=np.float32)
    if g.shape[0] < 8 or g.shape[1] < 8:
        return crop

    def span(stds: np.ndarray) -> tuple[int, int]:
        busy = np.nonzero(stds >= min_std)[0]
        if len(busy) == 0:
            return 0, len(stds)
        lo, hi = int(busy[0]), int(busy[-1]) + 1
        return (lo, hi) if hi - lo >= len(stds) // 2 else (0, len(stds))

    x0, x1 = span(g.std(axis=0))
    y0, y1 = span(g.std(axis=1))
    g = g[y0:y1, x0:x1]

    def outliers(means: np.ndarray) -> tuple[int, int]:
        """Edge lines much brighter or darker than the cloth inside (a mount's shading, a lit fold), at
        most 15 % from each side: mirrored repeats would double them into stripes."""
        cap = int(0.15 * len(means))
        inner = means[cap:len(means) - cap] if len(means) > 2 * cap + 4 else means
        # outside the range of the cloth's own lines (so a striped cloth keeps its edge stripes)
        bad = (means < np.percentile(inner, 2) - 8) | (means > np.percentile(inner, 98) + 8)
        lo = next((i for i in range(cap) if not bad[i]), cap)
        hi = next((i for i in range(cap) if not bad[len(means) - 1 - i]), cap)
        return lo, len(means) - hi

    a0, a1 = outliers(g.mean(axis=0))
    b0, b1 = outliers(g.mean(axis=1))
    return crop.crop((x0 + a0, y0 + b0, x0 + a1, y0 + b1))


def region_texture(photo: Image.Image, box: list[float], cm_per_px: float, label: str,
                   max_px: int = 384) -> PanelTexture:
    """The boxed part of the photo, paired with its mirror image left-right so repeats meet without a seam
    (top and bottom are not mirrored: figures stay upright)."""
    from PIL import ImageOps

    photo = photo.convert("RGB")
    x0, y0, x1, y1 = (round(box[0] * photo.width), round(box[1] * photo.height),
                      round(box[2] * photo.width), round(box[3] * photo.height))
    crop = _trim_background(photo.crop((x0, y0, max(x1, x0 + 2), max(y1, y0 + 2))))
    w_m, h_m = crop.width * cm_per_px / 100, crop.height * cm_per_px / 100
    crop.thumbnail((max_px, max_px))
    pair = Image.new("RGB", (2 * crop.width, crop.height))
    pair.paste(crop, (0, 0))
    pair.paste(ImageOps.mirror(crop), (crop.width, 0))
    return PanelTexture(image=pair, tile_w_m=max(2 * w_m, 0.03), tile_h_m=max(h_m, 0.03), label=label)


# ---------- 1. shape from measurements ----------

def shape_for(body, height_cm: float, values: dict[str, float], iters: int = 20,
              prior: float = 0.05, step: float = 0.5) -> tuple[np.ndarray, dict[str, float]]:
    """Betas whose T-pose body measures as `values` (cm) at `height_cm`; also all its measurements."""
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
    return betas, body3d.measure(body, betas)  # every measurement of the rebuilt body, asked for or not


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


def _tube(rings: list[np.ndarray], top_first: bool, side_seams: bool = False):
    """Vertices, quad-split faces, UVs, each vertex's distance from the open end (hem or cuff), and the
    indices of the vertices down the front line.

    UVs are surface lengths in metres, so the fabric is neither stretched nor squeezed: u is the arc length
    round each ring from the front line (motifs centre on the front), v the distance down the surface of
    each column from the top ring (a sloping shoulder gets its true length). With `side_seams` the front
    and back halves are separate pieces of cloth, as on a real garment: each is measured from its own
    centre line, so the narrowing to the neck does not twist the back. Scaled per material in _sub; v runs
    downwards so the top of a fabric picture stays at the top of the garment."""
    n = COLUMNS + 1
    grid = np.stack(rings)  # rings x columns x 3
    arc = np.concatenate([np.zeros((len(rings), 1)),
                          np.cumsum(np.linalg.norm(np.diff(grid, axis=1), axis=2), axis=1)], axis=1)
    step = np.linalg.norm(np.diff(grid, axis=0), axis=2)  # between consecutive rings, per column
    from_first = np.concatenate([np.zeros((1, n)), np.cumsum(step, axis=0)], axis=0)
    from_last = from_first[-1:] - from_first
    d_top, d_end = (from_first, from_last) if top_first else (from_last, from_first)
    if side_seams:  # columns 0..half are the front (angle 0-180 degrees), half..COLUMNS the back
        half = COLUMNS // 2
        pieces = [(0, half, half // 2), (half, COLUMNS, half + half // 2)]
    else:
        depth = grid[:, :-1, 2] - grid[:, :-1, 2].mean(axis=1, keepdims=True)
        pieces = [(0, COLUMNS, int(np.argmax(depth.mean(axis=0))))]
    verts, uvs, ends, offsets = [], [], [], []
    for lo, hi, centre in pieces:
        offsets.append(sum(len(v) for v in verts))
        cols = slice(lo, hi + 1)
        verts.append(grid[:, cols].reshape(-1, 3))
        u = arc[:, cols] - arc[:, centre:centre + 1]
        uvs.append(np.stack([u.ravel(), d_top[:, cols].ravel()], axis=1))
        ends.append(d_end[:, cols].ravel())

    def index(i, j):  # vertex of ring i, column j, in the piece that owns the quad starting at column j
        k = next(k for k, (lo, hi, _) in enumerate(pieces) if lo <= j < hi or (j == hi and k == len(pieces) - 1))
        lo, hi, _ = pieces[k]
        return offsets[k] + i * (hi - lo + 1) + (j - lo)

    faces = []
    for i in range(len(rings) - 1):
        for j in range(COLUMNS):
            k = next(k for k, (lo, hi, _) in enumerate(pieces) if lo <= j < hi)
            lo, hi, _ = pieces[k]
            a, b = offsets[k] + i * (hi - lo + 1) + (j - lo), offsets[k] + (i + 1) * (hi - lo + 1) + (j - lo)
            faces += [(a, a + 1, b + 1), (a, b + 1, b)]
    centre = pieces[0][2]
    front_line = np.array([index(i, centre) for i in range(len(rings))])
    return (np.concatenate(verts), np.array(faces, dtype=np.int64), np.concatenate(uvs), np.concatenate(ends),
            front_line)


@dataclass
class _Piece:
    verts: np.ndarray
    faces: np.ndarray
    uv: np.ndarray  # metres: (arc length from the front, distance from the top)
    d_end: np.ndarray  # per vertex: distance from the open end (hem or cuff), metres
    front_line: np.ndarray  # per ring: index of the vertex on the front centre line
    row_y: np.ndarray  # per face: height of the face (torso) or -inf (sleeves)
    angle: np.ndarray  # per face: centre angle
    hem: np.ndarray  # per face: distance from the hem, m


def _face_meta(rings: list[np.ndarray], from_hem: np.ndarray, heights: np.ndarray) -> tuple:
    rows = np.repeat(np.arange(len(rings) - 1), 2 * COLUMNS)
    cols = np.tile(np.repeat(np.arange(COLUMNS), 2), len(rings) - 1)
    mid = (ANGLES[cols] + ANGLES[cols + 1]) / 2
    return heights[rows], mid, from_hem[rows]


def _torso(mesh, body, joints, hem_y, neck_y, chest_y, offset, neck_cm, sleeved: bool,
           waist_y: float | None = None, flare: float = 0.0) -> _Piece:
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
    if flare and waist_y is not None and waist_y > hem_y:  # A-line: wider towards the hem, from the waist
        below = np.clip((waist_y - np.array(heights)) / (waist_y - hem_y), 0, 1)
        radii *= (1 + flare * below)[:, None]
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
    pv, pf, puv, d_end, line = _tube(rings, top_first=False, side_seams=True)
    return _Piece(pv, pf, puv, d_end, line, *_face_meta(rings, heights - hem_y, heights))


def _sleeve(mesh, body, joints, side: str, length_m: float, offset: float, profile: str | None = None
            ) -> _Piece | None:
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
    if profile:
        radii *= _sleeve_profile(profile, np.array(dist))[:, None]
    rings = [_ring(p, u, v, c, r + offset)
             for (p, u, v), c, r in zip(frames, _smooth(centers), radii, strict=True)]
    # close the seam: the top ring continues sideways into the body, under the torso's cloth (along
    # the arm it would rise above the shoulder line)
    inward = np.array([-np.sign(path[0][0] - joints[NECK][0]), 0.0, 0.0])
    rings.insert(0, rings[0] + 0.06 * inward)
    dist.insert(0, dist[0] - 0.06)
    dist = np.array(dist)
    pv, pf, puv, d_end, line = _tube(rings, top_first=True)
    _, angle, hem = _face_meta(rings, dist.max() - dist, dist)
    return _Piece(pv, pf, puv, d_end, line, np.full(len(pf), -np.inf), angle, hem)
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


HEM_BAND_M = 0.12


def _panel_of(piece: _Piece, sleeve: bool, hem_assigned: bool) -> np.ndarray:
    """front / back / hem / sleeves for every face (the hem band counts only when it has its own fabric)."""
    if sleeve:
        return np.full(len(piece.faces), "sleeves", dtype=object)
    panel = np.where(np.sin(piece.angle) >= 0, "front", "back").astype(object)
    if hem_assigned:
        panel[piece.hem < HEM_BAND_M] = "hem"
    return panel


def _buttons(torso: _Piece, state: dict, hem_y: float, neck_y: float):
    import trimesh

    if "buttons" not in state or state.get("closure") not in (None, "buttons_front"):
        return None
    rows = torso.verts[torso.front_line]  # after _clear, so buttons sit on the cloth
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


# ---------- 2b. free style, collars, pockets and fringe ----------

@dataclass
class StyleShape:
    """What the buyer's free style requests change in the 3D garment. Requests no rule recognises are kept
    in `not_drawn` and reported, never silently dropped."""
    ease_add_cm: float = 0.0
    hem: str | None = None  # crop | thigh | knee | calf | ankle
    sleeve_length: str | None = None  # none | short | three_quarter | full
    sleeve_profile: str | None = None  # puff | bell | wide
    slit_m: float = 0.0
    flare: float = 0.0
    belt: bool = False
    high_collar: bool = False
    drawn: list[str] = field(default_factory=list)
    not_drawn: list[str] = field(default_factory=list)


def _rx(pattern: str):
    import re

    return re.compile(pattern)


# (pattern over the Indonesian text and the English text, what it sets)
STYLE_RULES = [
    (_rx(r"oversize|oversized|longgar|loose|boxy|baggy|relaxed"), {"ease_add_cm": 16.0}),
    (_rx(r"\bslim\b|ketat|fitted|pas badan|body ?fit|tight"), {"ease_add_cm": -6.0}),
    (_rx(r"\bcrop|cropped"), {"hem": "crop"}),
    (_rx(r"semata kaki|mata kaki|ankle|\bmaxi\b"), {"hem": "ankle"}),
    (_rx(r"sebetis|betis|\bcalf|\bmidi\b"), {"hem": "calf"}),
    (_rx(r"selutut|lutut|\bknee"), {"hem": "knee"}),
    (_rx(r"sepaha|paha|thigh|mini"), {"hem": "thigh"}),
    (_rx(r"tanpa lengan|sleeveless|sabrina"), {"sleeve_length": "none"}),
    (_rx(r"lengan panjang|long sleeve|full.length sleeve"), {"sleeve_length": "full"}),
    (_rx(r"lengan pendek|short sleeve"), {"sleeve_length": "short"}),
    (_rx(r"3/4|tiga perempat|three.quarter"), {"sleeve_length": "three_quarter"}),
    (_rx(r"balon|balloon|puff|bishop|mengembang di lengan|lengan (?:mengembang|kerut)"), {"sleeve_profile": "puff"}),
    (_rx(r"lonceng|\bbell|terompet|flared sleeve"), {"sleeve_profile": "bell"}),
    (_rx(r"kimono|kelelawar|batwing|lengan lebar|wide sleeve"), {"sleeve_profile": "wide"}),
    (_rx(r"belahan|\bslit"), {"slit_m": 0.22}),
    (_rx(r"a-line|a line|\bflare|mengembang|melebar|\bumbrella|payung"), {"flare": 0.35}),
    (_rx(r"ikat pinggang|sabuk|\bbelt|\bobi\b|tali pinggang"), {"belt": True}),
    (_rx(r"kerah (?:sanghai|shanghai|tinggi|tegak|mandarin)|stand.?collar|mandarin collar|high collar"),
     {"high_collar": True}),
]
# words that mean the request is about a sleeve, so "mengembang" or "flare" in it is not an A-line hem
_SLEEVE_WORDS = _rx(r"lengan|sleeve|manset|cuff")


def style_shape(state: dict) -> StyleShape:
    shape = StyleShape()
    for item in state.get("style") or []:
        words = f"{item.get('text', '')} | {item.get('en', '')}".lower()
        hit = False
        for pattern, change in STYLE_RULES:
            if not pattern.search(words):
                continue
            if "flare" in change and _SLEEVE_WORDS.search(words):
                continue
            for key, value in change.items():
                if key == "ease_add_cm":
                    shape.ease_add_cm = value
                elif key == "hem" and shape.hem is not None:
                    continue  # the first length named in a request wins ("selutut" before "paha")
                else:
                    setattr(shape, key, value)
            hit = True
        (shape.drawn if hit else shape.not_drawn).append(item.get("text", ""))
    return shape


def _sleeve_profile(profile: str, dist: np.ndarray) -> np.ndarray:
    """Multiplier on the sleeve's radius from shoulder (t=0) to cuff (t=1)."""
    t = (dist - dist[0]) / max(dist[-1] - dist[0], 1e-6)
    if profile == "puff":  # full in the middle, gathered back to the arm at the cuff
        return 1 + 1.4 * np.sin(np.pi * np.clip(t, 0, 1) ** 0.7) * (t < 0.96)
    if profile == "bell":
        return 1 + 2.4 * np.clip(t - 0.3, 0, None) ** 1.4
    return 1 + 0.55 * np.clip(t * 2.0, 0, 1)  # wide / kimono: loose from the shoulder down


def _hem_from_style(hem: str, joints, waist_y: float) -> float:
    knee = (joints[L_KNEE][1] + joints[R_KNEE][1]) / 2
    ankle = (joints[L_ANKLE][1] + joints[R_ANKLE][1]) / 2
    hip = (joints[L_HIP][1] + joints[R_HIP][1]) / 2
    return {"crop": waist_y + 0.04, "thigh": (hip + knee) / 2, "knee": knee - 0.02,
            "calf": (knee + ankle) / 2, "ankle": ankle + 0.06}[hem]


def _piece(rings: list[np.ndarray], heights: np.ndarray, from_end: np.ndarray, top_first: bool) -> _Piece:
    pv, pf, puv, d_end, line = _tube(rings, top_first=top_first)
    return _Piece(pv, pf, puv, d_end, line, *_face_meta(rings, from_end, heights))


def _collar(state: dict, high: bool, joints, neck_y: float, neck_cm: float) -> _Piece | None:
    """A stand round the neck (mandarin, or a requested high collar) and, for a classic shirt collar, a
    fall that turns down over it with its points at the front."""
    kind = state.get("collar")
    if kind not in ("mandarin", "classic") and not high:
        return None
    base_y = neck_y + 0.015
    r0 = neck_cm / 100 / (2 * math.pi) + 0.022
    centre = np.array([joints[NECK][0], 0.0, joints[NECK][2]])
    u, v = np.array([1.0, 0.0, 0.0]), np.array([0.0, 0.0, 1.0])
    stand_h = 0.045 if high and kind != "classic" else 0.032

    def ring(y, r):
        return _ring(centre + [0.0, y, 0.0], u, v, np.zeros(2), np.full(COLUMNS + 1, r))

    rings, heights = [], []
    for t in np.linspace(0, 1, 5):  # the stand narrows a little towards its top edge
        rings.append(ring(base_y + t * stand_h, r0 * (1 - 0.06 * t)))
        heights.append(base_y + t * stand_h)
    if kind == "classic":  # the fall: from the top of the stand, out and down over it
        top_r = r0 * 0.94 + 0.004
        for t in np.linspace(0.15, 1, 5):
            rings.append(ring(base_y + stand_h - t * (stand_h + 0.045), top_r + 0.004 + t * 0.05))
            heights.append(base_y + stand_h - t * (stand_h + 0.045))
    heights = np.array(heights)
    return _piece(rings, heights, heights - heights.min(), top_first=True)


def _collar_keep(piece: _Piece, kind: str | None) -> np.ndarray:
    off = _angle_off_front(piece.angle)
    if kind == "classic":  # the fall's points spread apart towards its edge, the stand meets at the front
        lower = piece.row_y < piece.row_y.max() - 0.033
        return off >= np.where(lower, np.radians(4) + np.radians(30) * np.clip(
            (piece.row_y.max() - piece.row_y - 0.033) / 0.06, 0, 1), np.radians(4))
    return off >= np.radians(5)  # a mandarin collar opens a little at the front


def _surface_point(torso: _Piece, angle: float, y: float, centre_xz: np.ndarray):
    """The torso cloth's point at a height and angle, and the horizontal outward direction there."""
    cand = np.where(torso.row_y != -np.inf)[0]
    da = np.abs((torso.angle[cand] - angle + math.pi) % (2 * math.pi) - math.pi)
    i = cand[np.argmin(da + 4 * np.abs(torso.row_y[cand] - y))]
    p = torso.verts[torso.faces[i]].mean(axis=0)
    out = np.array([p[0] - centre_xz[0], 0.0, p[2] - centre_xz[1]])
    return p, out / (np.linalg.norm(out) + 1e-9)


POCKETS = {  # option -> [(angle from the wearer's left, height key, width m, height m)]
    "left_chest_single": [(math.radians(64), "chest", 0.11, 0.13)],
    "double_chest": [(math.radians(64), "chest", 0.11, 0.13), (math.radians(116), "chest", 0.11, 0.13)],
    "side_double": [(math.radians(35), "hip", 0.15, 0.17), (math.radians(145), "hip", 0.15, 0.17)],
    "double_welt": [(math.radians(58), "waist", 0.13, 0.014), (math.radians(122), "waist", 0.13, 0.014)],
}


def _pockets(torso: _Piece, state: dict, ys: dict[str, float], centre_xz: np.ndarray, rgba):
    import trimesh

    boxes = []
    for angle, where, w, h in POCKETS.get(state.get("pockets"), []):
        p, n = _surface_point(torso, angle, ys[where], centre_xz)
        up = np.array([0.0, 1.0, 0.0])
        side = np.cross(up, n)
        box = trimesh.creation.box(extents=[w, h, 0.004])
        frame = np.eye(4)
        frame[:3, 0], frame[:3, 1], frame[:3, 2], frame[:3, 3] = side, up, n, p + 0.006 * n
        box.apply_transform(frame)
        box.visual.vertex_colors = rgba
        boxes.append(box)
    return trimesh.util.concatenate(boxes) if boxes else None


def _fringe(torso: _Piece, keep: np.ndarray, length_m: float, rgba):
    """Strands hanging from the hem every 8 mm (thin double-sided ribbons)."""
    import trimesh

    used = np.unique(torso.faces[keep])
    hem = used[torso.d_end[used] < 1e-6]
    if len(hem) < 3:
        return None
    pts = torso.verts[hem]
    centre = pts.mean(axis=0)
    order = np.argsort(np.arctan2(pts[:, 2] - centre[2], pts[:, 0] - centre[0]))
    pts = pts[order]
    seg = np.linalg.norm(np.diff(np.vstack([pts, pts[:1]]), axis=0), axis=1)
    pos = np.concatenate([[0], np.cumsum(seg)])
    samples = np.arange(0, pos[-1], 0.008)
    ring = np.vstack([pts, pts[:1]])
    top = np.stack([np.interp(samples, pos, ring[:, k]) for k in range(3)], axis=1)
    out = top - [centre[0], top[:, 1].mean(), centre[2]]
    out[:, 1] = 0
    out /= np.linalg.norm(out, axis=1, keepdims=True) + 1e-9
    tangent = np.cross([0.0, 1.0, 0.0], out)
    w = 0.0015 * tangent
    bottom = top + [0.0, -length_m, 0.0] + 0.012 * out
    verts = np.concatenate([top - w, top + w, bottom + w, bottom - w])
    n = len(top)
    a, b, c, d = np.arange(n), np.arange(n) + n, np.arange(n) + 2 * n, np.arange(n) + 3 * n
    faces = np.concatenate([np.stack([a, b, c], 1), np.stack([a, c, d], 1)])
    mesh = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
    mesh.visual.vertex_colors = rgba
    return mesh


def _belt(torso: _Piece, waist_y: float, centre_xz: np.ndarray, rgba):
    """A band of the same cloth round the waist, just outside the garment."""
    import trimesh

    mask = (np.abs(torso.row_y - waist_y) < 0.022)
    if not mask.any():
        return None
    mesh = trimesh.Trimesh(vertices=torso.verts.copy(), faces=torso.faces[mask], process=False)
    mesh.remove_unreferenced_vertices()
    out = mesh.vertices - [centre_xz[0], 0.0, centre_xz[1]]
    out[:, 1] = 0
    out /= np.linalg.norm(out, axis=1, keepdims=True) + 1e-9
    mesh.vertices = mesh.vertices + 0.006 * out
    mesh.visual.vertex_colors = rgba
    return mesh


# ---------- 3. assembling and exporting ----------

def _material(texture: Image.Image | None, rgba):
    from trimesh.visual.material import PBRMaterial

    return PBRMaterial(baseColorTexture=texture, baseColorFactor=rgba, metallicFactor=0.0,
                       roughnessFactor=0.92, doubleSided=True)


def _sub(piece: _Piece, faces_mask: np.ndarray, material, tile_w_m: float = TILE_M, tile_h_m: float = TILE_M,
         anchor: str = "top", centred: bool = False):
    """One material's faces. A cut-out piece of fabric is `centred` on the front line, and anchored at the
    top of the part (its top edge under the neckline or shoulder) or at the `bottom` (its lower edge on
    the hem), as a tailor would place it."""
    import trimesh

    u = (piece.uv[:, 0] + (tile_w_m / 4 if centred else 0.0)) / tile_w_m  # the crop's middle, not its edge
    v = 1.0 - piece.d_end / tile_h_m if anchor == "bottom" else piece.uv[:, 1] / tile_h_m
    mesh = trimesh.Trimesh(vertices=piece.verts, faces=piece.faces[faces_mask], process=False)
    mesh.visual = trimesh.visual.TextureVisuals(uv=np.stack([u, v], axis=1), material=material)
    mesh.remove_unreferenced_vertices()
    return mesh


def build(body, template_code: str, state: dict, ease_cm: float, height_cm: float,
          values: dict[str, float], texture: Image.Image,
          panels: dict[str, PanelTexture] | None = None, default: PanelTexture | None = None) -> Avatar:
    """`panels`: fabric for named garment parts (the motif layout); `default`: fabric for the other parts
    instead of the middle of the photo (used when the layout avoids part of the cloth)."""
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
    style = style_shape(state)
    neck_y = verts[LM["SHOULDER_TOP"]][1]
    waist_y = verts[LM["BACK_BELLY_BUTTON"]][1]
    chest_y = (verts[LM["LEFT_NIPPLE"]][1] + verts[LM["RIGHT_NIPPLE"]][1]) / 2
    hem_y = waist_y - (shape["below_waist_cm"] + float(state.get("hem_length_delta_cm") or 0)) / 100
    if style.hem:
        hem_y = _hem_from_style(style.hem, joints, waist_y)
    ease = max(ease_cm + style.ease_add_cm, 4.0)
    offset = ease / 100 / (2 * math.pi) + 0.006  # ease is a circumference; 6 mm keeps cloth off skin
    sleeve_kind = shape["sleeve"]
    if style.sleeve_length == "none":
        sleeve_kind = None
    elif style.sleeve_length:
        sleeve_kind = {"full": "full", "short": 22, "three_quarter": "three_quarter"}[style.sleeve_length]
    neck_cm = fitted.get("neck_circumference", 38.0)
    pieces = [_torso(mesh, body, joints, hem_y, neck_y, chest_y, offset, neck_cm, sleeve_kind is not None,
                     waist_y=waist_y, flare=style.flare)]
    if sleeve_kind is not None:
        full = fitted["sleeve_length"]
        base = full if sleeve_kind == "full" else 0.75 * full if sleeve_kind == "three_quarter" else sleeve_kind
        length = (base + float(state.get("sleeve_length_delta_cm") or 0)) / 100
        for side in ("left", "right"):
            sleeve = _sleeve(mesh, body, joints, side, length, 0.7 * offset, style.sleeve_profile)
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
    trim_rgba = [int(c * 0.82) for c in plain_rgba[:3]] + [255]
    centre_xz = np.array([joints[NECK][0], joints[NECK][2]])
    textured, plain = _material(texture, [255, 255, 255, 255]), _material(None, plain_rgba)
    scene = trimesh.Scene()
    body_mesh = trimesh.Trimesh(vertices=verts, faces=body.faces, process=False)
    body_mesh.visual.vertex_colors = MANNEQUIN_RGBA
    scene.add_geometry(body_mesh, node_name="body", geom_name="body")
    placement = state.get("motif_placement", "all_over")
    panels = panels or {}
    base = (textured, TILE_M, TILE_M) if default is None else \
        (_material(default.image, [255, 255, 255, 255]), default.tile_w_m, default.tile_h_m)
    own = {p: (_material(t.image, [255, 255, 255, 255]), t.tile_w_m, t.tile_h_m) for p, t in panels.items()}
    collar = _collar(state, style.high_collar, joints, neck_y, neck_cm)
    torso_keep = None
    for i, piece in enumerate(pieces):
        keep = _keep(piece, state, neck_y)
        if i == 0:
            if style.slit_m:  # side slits: open at both side seams, up from the hem
                side = np.minimum(np.abs(piece.angle % (2 * math.pi)), np.abs(piece.angle - math.pi))
                side = np.minimum(side, np.abs(piece.angle - 2 * math.pi))
                keep &= ~((side < np.radians(6)) & (piece.hem < style.slit_m))
            torso_keep = keep
        motif = _textured(piece, placement, chest_y)
        panel = _panel_of(piece, i > 0, "hem" in panels)
        assigned = np.isin(panel, list(panels))
        groups = [("motif", keep & motif & ~assigned, base), ("plain", keep & ~motif & ~assigned, (plain, TILE_M, TILE_M))]
        groups = [(name, mask, cfg, "top", False) for name, mask, cfg in groups]
        groups += [(f"panel_{p}", keep & (panel == p), own[p], "bottom" if p == "hem" else "top", True)
                   for p in panels]
        for name, mask, (mat, tw, th), anchor, centred in groups:
            if mask.any():
                scene.add_geometry(_sub(piece, mask, mat, tw, th, anchor, centred), node_name=f"garment_{i}_{name}",
                                   geom_name=f"garment_{i}_{name}")
    if collar is not None:
        scene.add_geometry(_sub(collar, _collar_keep(collar, state.get("collar")), base[0], base[1], base[2]),
                           node_name="collar", geom_name="collar")
    ys = {"chest": chest_y + 0.03, "waist": waist_y - 0.03, "hip": max(waist_y - 0.10, hem_y + 0.12)}
    extras = {"pockets": _pockets(pieces[0], state, ys, centre_xz, trim_rgba),
              "belt": _belt(pieces[0], waist_y, centre_xz, trim_rgba) if style.belt else None}
    if state.get("trim") in FRINGE_M:
        extras["fringe"] = _fringe(pieces[0], torso_keep, FRINGE_M[state["trim"]], plain_rgba)
    for name, geom in extras.items():
        if geom is not None:
            scene.add_geometry(geom, node_name=name, geom_name=name)
    buttons = _buttons(pieces[0], state, hem_y, neck_y)
    if buttons is not None:
        scene.add_geometry(buttons, node_name="buttons", geom_name="buttons")
    skipped = [k for k, vals in NOT_DRAWN.items() if state.get(k) not in (None, "none")
               and (vals is None or state.get(k) in vals)]
    if skipped:
        warnings.append("not_drawn: " + ", ".join(LABELS[k] for k in skipped)
                        + " belum digambar pada avatar 3D; lihat ilustrasi desain")
    if style.not_drawn:
        warnings.append("style_not_drawn: " + "; ".join(style.not_drawn)
                        + " belum bisa dibentuk pada avatar 3D; lihat avatar AI")
    buf = io.BytesIO()
    buf.write(scene.export(file_type="glb", include_normals=True))
    return Avatar(glb=buf.getvalue(), fitted=fitted, warnings=warnings)


# ---------- 4. a flat front picture of the bare body (for the image model to dress) ----------

FRONT_SIZE = (768, 1024)
FRONT_BG = (237, 235, 230)
FRONT_SKIN = np.array([204, 196, 189], dtype=float)
FRONT_LIGHT = np.array([0.3, 0.4, 1.0]) / np.linalg.norm([0.3, 0.4, 1.0])


def draw_front(verts: np.ndarray, faces: np.ndarray, size: tuple[int, int] = FRONT_SIZE) -> Image.Image:
    """Front view of a mesh, shaded grey on a plain background (painter's algorithm: far faces first).
    No face texture, no hair: only the body's shape, which is what the measurements decide."""
    from PIL import ImageDraw

    tri = verts[faces]
    normal = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    normal /= np.linalg.norm(normal, axis=1, keepdims=True) + 1e-12
    visible = normal[:, 2] > 0
    shade = 0.35 + 0.65 * np.clip(normal @ FRONT_LIGHT, 0, 1)
    width, height = size
    lo, hi = verts[:, 1].min(), verts[:, 1].max()
    scale = height * 0.9 / (hi - lo)  # the body fills 90% of the height, centred
    cx = (verts[:, 0].min() + verts[:, 0].max()) / 2
    xy = np.stack([width / 2 + (tri[:, :, 0] - cx) * scale, height * 0.05 + (hi - tri[:, :, 1]) * scale], axis=-1)
    image = Image.new("RGB", size, FRONT_BG)
    draw = ImageDraw.Draw(image)
    for i in np.argsort(tri[:, :, 2].mean(axis=1)):
        if visible[i]:
            colour = tuple(int(c) for c in np.clip(FRONT_SKIN * shade[i], 0, 255))
            draw.polygon([tuple(p) for p in xy[i]], fill=colour, outline=colour)
    return image


def front_picture(body, height_cm: float, values: dict[str, float]) -> tuple[Image.Image, dict[str, float]]:
    """The buyer's body rebuilt from their measurements, drawn from the front without any garment."""
    betas, fitted = shape_for(body, height_cm, values)
    verts, _ = _posed(body, betas)
    return draw_front(verts, np.asarray(body.faces)), fitted
