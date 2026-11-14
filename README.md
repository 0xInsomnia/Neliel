# Neliel — Jean body study 01

Experimental rebuild from repository initial commit. The historical branch name
is `feature/neliel-neko-rebuild`, but the user selected Jean as the replacement base.
No old procedural avatar geometry is used.

Run `python3 tools/restore-source.py` to restore the complete editable Blender
checkpoint from lossless parts (SHA-256 verified). The parts avoid the connector's
single-request size limit. Open `source/neliel-body-study.blend` in Blender 4.3+.
Original keys, weights, rig and hidden original clothes are retained.

For the browser viewer: `npm run serve`, then open http://localhost:8080.
Touch drag rotates; pinch zooms; buttons select views; the checkbox toggles the
new corrective body morph. This is a static fitting study, not a finished companion.

`npm test` verifies GLB integrity, skeleton, corrective morph and recorded FK
probes. Full constraint-driven pose controls and on-device Samsung performance
are not yet certified. The temporary garment is static and not the final outfit.

The reproducible body-build script expects the user's original attachment at
`source/jean-original.blend`; the original input is not duplicated in this repository.
Private concept drawings are not committed. Jean is a supplied third-party asset;
this checkpoint does not claim original ownership or establish redistribution rights.
