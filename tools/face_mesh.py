"""Mesh helpers for the face stage (revision 14).

Everything here works on plain NumPy arrays so the same routines serve the
base shape and every morph target: UV islands, open borders, a frontal depth
map of the skin, hole filling and one level of Loop subdivision expressed as
a reusable linear operator.
"""
import numpy as np


def uv_islands(triangles, count):
    """Label each triangle with the UV island (connected by shared vertices) it is in."""
    parent = np.arange(count)

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for triangle in triangles:
        root = find(triangle[0])
        for vertex in triangle[1:]:
            parent[find(vertex)] = root
    return np.array([find(t[0]) for t in triangles])


def weld(points, decimals=5):
    """Map vertices that share a position (UV seams) to one welded index."""
    _, index = np.unique(np.round(points, decimals), axis=0, return_inverse=True)
    return index.reshape(-1)


def border_loops(points, triangles):
    """Open borders as ordered loops of vertex indices (one representative per welded point)."""
    welded = weld(points)
    representative = np.zeros(welded.max() + 1, dtype=int)
    representative[welded] = np.arange(len(points))
    corners = welded[triangles]
    directed = np.concatenate([corners[:, [0, 1]], corners[:, [1, 2]], corners[:, [2, 0]]])
    key = np.sort(directed, axis=1)
    _, inverse, uses = np.unique(key, axis=0, return_inverse=True, return_counts=True)
    open_edges = directed[uses[inverse.reshape(-1)] == 1]
    following = {int(a): int(b) for a, b in open_edges}
    loops = []
    while following:
        start, loop = next(iter(following)), []
        current = start
        while current in following:
            loop.append(current)
            current = following.pop(current)
        loops.append(representative[np.array(loop)])
    return loops


def frontal_depth(points, triangles, bounds, resolution):
    """Front-most z of the surface seen from the front, on a regular (x, y) grid.

    bounds = (x0, x1, y0, y1) in metres, resolution in samples per metre.
    Returns depth (inf where nothing is hit) with row 0 at y0.
    """
    x0, x1, y0, y1 = bounds
    width, height = int(round((x1 - x0) * resolution)), int(round((y1 - y0) * resolution))
    depth = np.full((height, width), np.inf)
    px = (points[:, 0] - x0) * resolution
    py = (points[:, 1] - y0) * resolution
    for triangle in triangles:
        x, y, z = px[triangle], py[triangle], points[triangle, 2]
        low = np.maximum(np.floor([x.min(), y.min()]).astype(int), 0)
        high = np.minimum(np.ceil([x.max(), y.max()]).astype(int), [width - 1, height - 1])
        if (high < low).any():
            continue
        det = (y[1] - y[2]) * (x[0] - x[2]) + (x[2] - x[1]) * (y[0] - y[2])
        if abs(det) < 1e-12:
            continue
        gx, gy = np.meshgrid(np.arange(low[0], high[0] + 1) + .5, np.arange(low[1], high[1] + 1) + .5)
        a = ((y[1] - y[2]) * (gx - x[2]) + (x[2] - x[1]) * (gy - y[2])) / det
        b = ((y[2] - y[0]) * (gx - x[2]) + (x[0] - x[2]) * (gy - y[2])) / det
        c = 1 - a - b
        inside = (a >= -1e-9) & (b >= -1e-9) & (c >= -1e-9)
        value = a * z[0] + b * z[1] + c * z[2]
        region = depth[low[1]:high[1] + 1, low[0]:high[0] + 1]
        closer = inside & (value < region)
        region[closer] = value[closer]
    return depth


class DepthMap:
    """Bilinear lookup into a frontal depth map; holes are filled from neighbours."""

    def __init__(self, points, triangles, bounds, resolution):
        self.bounds, self.resolution = bounds, resolution
        depth = frontal_depth(points, triangles, bounds, resolution)
        self.covered = np.isfinite(depth)
        filled = depth.copy()
        missing = ~self.covered
        for _ in range(64):                      # grow the surface outward a little
            if not missing.any():
                break
            total = np.zeros_like(filled)
            weight = np.zeros_like(filled)
            for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                shifted = np.roll(np.where(missing, 0, filled), (dy, dx), axis=(0, 1))
                known = np.roll(~missing, (dy, dx), axis=(0, 1))
                total += shifted * known
                weight += known
            grow = missing & (weight > 0)
            filled[grow] = total[grow] / weight[grow]
            missing = missing & ~grow
        filled[missing] = 0
        self.depth = filled

    def __call__(self, x, y):
        x0, _, y0, _ = self.bounds
        u = np.clip((np.asarray(x) - x0) * self.resolution - .5, 0, self.depth.shape[1] - 1.001)
        v = np.clip((np.asarray(y) - y0) * self.resolution - .5, 0, self.depth.shape[0] - 1.001)
        i, j = np.floor(u).astype(int), np.floor(v).astype(int)
        fu, fv = u - i, v - j
        d = self.depth
        return ((1 - fu) * (1 - fv) * d[j, i] + fu * (1 - fv) * d[j, i + 1]
                + (1 - fu) * fv * d[j + 1, i] + fu * fv * d[j + 1, i + 1])

    def half_width(self, y):
        """Largest |x| the surface reaches on each row nearest to y."""
        x0, _, y0, _ = self.bounds
        rows = np.clip(((np.asarray(y) - y0) * self.resolution).astype(int), 0, self.covered.shape[0] - 1)
        columns = (np.arange(self.covered.shape[1]) + .5) / self.resolution + x0
        reach = np.where(self.covered, np.abs(columns)[None], 0).max(1)
        return reach[rows]


def fill_loop(points, loop, lift):
    """Fan triangles closing an open loop around a new centre vertex.

    Returns (centre position, triangles using index -1 for the centre). The
    fan is wound to face the front (-z) and the centre is lifted by `lift`
    toward the viewer so the closed lid reads as a soft dome, not a dent.
    """
    ring = points[loop]
    centre = ring.mean(0) + [0, 0, -lift]
    following = np.roll(loop, -1)
    normal = np.cross(points[following] - points[loop], centre - points[loop]).sum(0)
    if normal[2] > 0:
        loop, following = following, loop
    return centre, np.stack([loop, following, np.full(len(loop), -1)], 1)


class Loop:
    """One level of Loop subdivision as a linear operator.

    The topology is taken from the base shape once; `positions` can then be
    applied to the base and to every morphed shape, so morph targets stay
    exactly consistent. Positions follow the welded surface (both sides of a
    UV seam move together); open borders stay in place so neighbouring meshes
    still meet. `linear` interpolates any per-vertex attribute at edge
    midpoints (UVs, weights).
    """

    def __init__(self, points, triangles):
        self.count = len(points)
        self.weld = weld(points)
        self.welded_count = self.weld.max() + 1
        corner = np.array([[0, 1, 2], [1, 2, 0], [2, 0, 1]])        # edge a-b, opposite c
        wtri = self.weld[triangles]
        wa, wb, wc = (wtri[:, corner[:, k]].reshape(-1) for k in range(3))
        key = np.stack([np.minimum(wa, wb), np.maximum(wa, wb)], 1)
        self.edges, edge_of, faces = np.unique(key, axis=0, return_inverse=True, return_counts=True)
        edge_of = edge_of.reshape(-1)
        self.manifold = faces == 2
        self.opposite = (edge_of, wc)
        self.border = np.zeros(self.welded_count, dtype=bool)
        self.border[self.edges[~self.manifold].reshape(-1)] = True
        valence = np.zeros(self.welded_count)
        for end in (0, 1):
            np.add.at(valence, self.edges[:, end], 1)
        n = np.maximum(valence, 3)
        self.beta = (.625 - (.375 + .25 * np.cos(2 * np.pi / n)) ** 2) / n
        self.valence = n

        va, vb = (triangles[:, corner[:, k]].reshape(-1) for k in range(2))
        attribute_key = np.stack([np.minimum(va, vb), np.maximum(va, vb)], 1)
        self.attribute_edges, attribute_of = np.unique(attribute_key, axis=0, return_inverse=True)
        attribute_of = attribute_of.reshape(-1)
        self.welded_edge = np.zeros(len(self.attribute_edges), dtype=int)
        self.welded_edge[attribute_of] = edge_of
        middle = self.count + attribute_of.reshape(-1, 3)             # per triangle: ab, bc, ca
        t0, t1, t2 = triangles.T
        ab, bc, ca = middle.T
        self.triangles = np.concatenate([
            np.stack([t0, ab, ca], 1), np.stack([t1, bc, ab], 1),
            np.stack([t2, ca, bc], 1), np.stack([ab, bc, ca], 1)])
        self.new_weld = np.concatenate([self.weld, self.welded_count + self.welded_edge])

    def positions(self, points):
        welded = np.zeros((self.welded_count, 3))
        welded[self.weld] = points
        opposite = np.zeros((len(self.edges), 3))
        np.add.at(opposite, self.opposite[0], welded[self.opposite[1]])
        middle = welded[self.edges].mean(1)
        odd = np.where(self.manifold[:, None], .75 * middle + .125 * opposite, middle)
        around = np.zeros((self.welded_count, 3))
        for end, other in ((0, 1), (1, 0)):
            np.add.at(around, self.edges[:, end], welded[self.edges[:, other]])
        even = (1 - (self.valence * self.beta)[:, None]) * welded + self.beta[:, None] * around
        even[self.border] = welded[self.border]
        return np.concatenate([even[self.weld], odd[self.welded_edge]])

    def linear(self, values):
        a, b = self.attribute_edges.T
        return np.concatenate([values, (values[a] + values[b]) / 2])

    def pairs(self):
        return self.attribute_edges.T

    def normals(self, points):
        """Smooth normals shared across UV seams, for subdivided positions."""
        corner = points[self.triangles]
        face = np.cross(corner[:, 1] - corner[:, 0], corner[:, 2] - corner[:, 0])
        summed = np.zeros((self.new_weld.max() + 1, 3))
        for k in range(3):
            np.add.at(summed, self.new_weld[self.triangles[:, k]], face)
        normal = summed[self.new_weld]
        length = np.linalg.norm(normal, axis=1)
        normal[length > 1e-12] /= length[length > 1e-12, None]
        normal[length <= 1e-12] = [0, 0, -1]
        return normal
