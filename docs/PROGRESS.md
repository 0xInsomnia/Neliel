# Recovery checkpoint — 9 November 2026, revision 04

Base: revision 03, commit `89582a9`. Do not recreate earlier face work.

Completed in this checkpoint:
- Reduced the excessive ponytail arch above the head by up to 6.3 cm.
- Gradually narrowed the upper arch; preserved the lower lengths and ends.
- Added guarded, reproducible tools/refine_crown.py, accepting revision 03 only.
- Studio labels now identify revision 04; root demo remains the original base.

Validation:
- 16 tests passed; both GLBs have zero errors and zero warnings.
- Accessor comparison confirms only ponytail POSITION/NORMAL changed.
- Nodes, skins, weights, face, morphs, UV and colors are unchanged.
- Chromium with SwiftShader: compared front before/after, inspected profile
  and full rear silhouette with the camera pulled back.
- Real-device touch/performance and dynamic hair collisions are not certified.

Remaining, in priority order:
1. Sculpt a convincing ponytail attachment and resolve crown/fringe overlaps.
   Side locks remain rigid with the head; hair surfaces are still too uniform.
2. Further face/ear likeness and expression polish against private references.
3. Body proportions and actual outfit modelling, then broader animation QA.

Rebuild instructions: docs/MESH_REFINEMENT.md, revision 04 section.
Keep private reference images and personal details outside the repository.
Save small coherent checkpoints and verify remote success before claiming it.
