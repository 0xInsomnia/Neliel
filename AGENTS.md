# Neliel: development and recovery

- Work exclusively in `0xInsomnia/Neliel`.
- Target: an articulated anime character with high quality modelling, cel shading and animation. Do not copy proprietary game assets.
- Reference images and personal details are private and must not be committed.
- Prioritize actual mesh and outfit quality. Shader changes alone do not meet the character goal. Do not replace the character with geometric primitives.
- Use free tools; preserve touch controls, rig and facial morphs.
- Save small, coherent checkpoints to GitHub during work, not only at the end. Record actual checks and remaining limitations in `docs/PROGRESS.md` before pausing. Never describe a local commit as remotely saved until push succeeds.
- Read README.md, docs/MESH_REFINEMENT.md and docs/PROGRESS.md before resuming. Verify the current branch and remote before editing; do not recreate recovered work.
- Validate modified GLBs and run `npm test`. Inspect rendered front, profile and rear views when graphics are available; automated geometry checks are not proof of visual quality.
