# Recovery checkpoint — 9 November 2026, revision 02

Recovered main at `92a3251`; prior revision 01 preserved in Git history.

Completed this pass:
- Added a repeatable CPU orthographic texture/silhouette inspector.
- Confirmed white eyelash/eyeline masks and assigned dark linear color factors.
- Subtly reduced crown volume and extended only lower front temple locks.
- Integrated revision 02 labels in cel-studio; original demo is unchanged.
- Compared front, profile and rear CPU views; reduced an excessive initial
  hair deformation before saving the final model.

Validation: 15 automated tests pass; both GLBs have zero errors/warnings.
Topology, UVs, rig, weights and embedded textures remain intact.
Browser inspection reached the studio but WebGL context creation is disabled
in this environment. CPU inspection does not validate toon shaders, animation,
mobile performance, touch on a real device or hair/shoulder collisions.

Remaining: actual sculpted hair clumps and detailed ponytail, face proportions,
outfit remodelling, animated visual QA. Current model is still substantially
below the intended reference quality. Do not call it complete.

Resume from this checkpoint, run tests, inspect the current asset and save
small coherent milestones exclusively to 0xInsomnia/Neliel. Private references
must stay outside the repository.
