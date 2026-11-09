# Integrity recovery — 9 November 2026

The previously published revision 06 in `50e3ff2` was truncated to 16,384
bytes. Its four refined-model tests failed in GitHub Actions. Earlier local
validation claims below did NOT establish integrity of the remote binary.

Reconstructed r02 → r06 using the committed base and existing scripts.
Recovered file: 2,923,312 bytes.
SHA-256: b687c3697a98e655908fec7c4cec3ed1eab33a80920953f470262e0e3ab14c82
Git blob: 5a52bcc5035b31c52d8413cc91132cd4637f39d8

Checks: all 16 tests pass; both GLBs zero glTF errors/warnings. Inspected
CPU front/profile/rear views (bind pose, not interactive toon rendering).
Regression probe: a 16 KB copy now fails with an explicit GLB length error.
New `python3 tools/rebuild_refined.py` rebuilds all stages in temporary files,
validates the output and atomically replaces the shipped asset only on success.
Requires NumPy and npm dependencies installed. Run `npm test` afterwards.

Next: verify remote blob matches the hash above and GitHub Actions succeeds.
Then verify r06 in WebGL and continue hair attachment, strands, body/outfit.
This recovery restores revision 06; it is not a new aesthetic revision.
Private original references remain authoritative and must never be committed.

---

# Recovery checkpoint — 9 November 2026, revision 06

Base: remote revision 05, b4a1035. Original private references remain authoritative.
User wants a visibly adult anime character, with Genshin as rendering reference.

Completed: tools/refine_head_balance.py and regenerated neliel-refined.glb.
Common map across every mesh layer and morph endpoint: upper head X -8.5%,
Z -5.5%, crown height up to -20 mm. Smooth neck transition; lower-face length
retained. Production studio labels updated to revision 06 / 0.4.6 EXP.

Validation: 16 tests pass; both GLBs zero errors/warnings. Additional checks
preserve skeleton, skins, weights, UVs, materials and lower-body positions;
already-r06 inputs rejected. CPU before/after front/profile/rear inspected.
Managed browser explicitly reports WebGL disabled. NO interactive toon visual
verification in this session; do not describe CPU views as screenshots of app.

Next: verify r06 in WebGL, including expressions, head turns and hair motion;
then sculpt hair attachment/ponytail strands, nose/mouth/ears, body and outfit.
Do not keep shrinking the eyes to compensate for an unfinished body.
Current ponytail remains uniform; outfit still differs substantially from concept.
Use original references, not the previous screenshots as identity targets.
Save small coherent checkpoints only in 0xInsomnia/Neliel. References stay private.
