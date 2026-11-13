# Technical model audit — 13 November 2026

Compared main bdd92c3 (revision 06) and nelielclaude ff4c9a5 (revision 15).

| Check | main r06 | nelielclaude r15 |
|---|---|---|
| GLB bytes | 2,923,312 | 5,227,560 |
| Triangles | 43,700 | 75,376 |
| glTF errors / warnings | 0 / 0 | 0 / 0 |
| Existing tests | 16 pass | 16 pass |
| Body | stock topology with limited shaping | subdivided skin and updated joint pivots |
| Face | simpler eye and mouth surfaces | additional facial surface detail |
| Hair | narrow ponytail | wider ponytail with excessive spread at ends |
| Outfit | provisional boots and panels | same provisional outfit plus study texture |

Decision: branch from ff4c9a5. Retain body topology, facial layers, UVs,
rig corrections and four morph targets. Revisit head/body balance using a
common spatial map instead of swapping incompatible geometry and pivots.
No files from main or nelielclaude are overwritten.

Both assets imported successfully into Blender. CPU Cycles front, profile,
rear and portrait views inspected. This does not certify WebGL/toon or
real phone operation. Chromium startup failed (socket operation denied).
The existing tests exercise arm movement, hair bones and four morphs;
they do not certify absence of self-intersection in arbitrary poses.
