# Recovery checkpoint — 9 November 2026, revision 03

Base: published revision 02 (`0f73093`). Recovered the unpublished temple-lock
experiment from the previous session and adapted it to the current asset.

Completed:
- Subtle lower-face elongation, cheek taper and narrower/slanted eyes.
- All four facial morph endpoints transformed consistently with the rest mesh.
- Narrower side fringe, lifted ponytail root, four head-bound temple locks.
- Repeatable two-stage asset generation, preserving original base and textures.
- Studio revision 03 labels; original root demo unchanged.

Validation: 16 automated tests pass; both GLBs have zero errors/warnings.
The refined GLB has 2 information messages and 52 hints (unused objects and
optional buffer view targets). New regression checks head binding and excludes
accidental arm binding. Morph, arm, camera and material tests also pass.
WebGL software rendering now works with recovered Chromium/SwiftShader.
Inspected same-camera front before/after, profile, close rear, smile, surprise,
wink, curious pose and 393x852 mobile layout. A complete rear silhouette and
real-device touch/performance remain to be checked. No claim of Genshin quality.

Remaining, in priority order:
1. Refine crown/fringe junction, ears and long ponytail clumps/textures; remove
   existing visible overlaps. Side locks currently move rigidly with the head.
2. Further face likeness and expression polish against private reference images.
3. Body proportions and actual outfit modelling, then broader animation QA.

Keep private reference images outside this repository. Save coherent changes
frequently. Read this file and inspect git status before resuming; do not recreate
this work. Screenshots from this session are review artifacts, not model assets.
