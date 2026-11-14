# Neliel rebuild — Jean base

Branch `feature/neliel-neko-rebuild` starts at repository root commit
`f9570e85c637edfee3c994cccd2de3bdde242e7e` (README only).
The user replaced Neko with the attached Jean blend. No old procedural
character geometry is reused. Other branches must not be changed.

Initial audit in Blender 4.3.2: Body 12,817 vertices and 32 key blocks;
head 2,149 vertices and 51 key blocks; original rig 539 bones;
no stored actions. Some shape keys are already active in the source.
Missing external studio HDR and toon02.bmp; face material conversion warning.
These are inventory results, not proof of successful articulation.

Private reference drawings stay outside the repository.
Body proportions are the current gate; face, hair and outfit are not complete.
Original source retained untouched for recovery. Vendor Three.js is the only
runtime infrastructure recovered from previous work.

## Body study 01
- Full original source data retained in the editable checkpoint, including 539 bones.
- Added one non-destructive body corrective key, retaining all 32 original blocks.
- Widened pelvis and slightly narrowed waist; no claim of matching reference yet.
- Removed clothing obstruction from study visibility, with opaque temporary fitting layers.
- Four real isolated FK probes produced finite coordinates and moved vertices (see JSON).
- Front, profile, rear and three-quarter Blender renders inspected. Main remaining
  issues: torso/waist transition, lateral hip profile, A-pose vs reference stance.
- GLB 5,530,940 bytes: Khronos validation 0 errors, 3 hierarchy warnings
  (skinned nodes parented under rig), 3 unused-UV informational messages.
- Browser viewer has rotation, pinch zoom, view buttons and corrective toggle.
  Runtime browser validation blocked: local Chromium fails with socket permission
  error before page launch. Do not claim Samsung or WebGL validation.
- Final hair, face redesign, original outfit and animations are NOT completed.
- Full editable source stored as lossless binary parts with verified reconstruction.
