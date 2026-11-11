# Checkpoint — 11 November 2026, revision 11 (branch `nelielclaude`)

`tools/refine_ponytail.py`, new last stage of the rebuild: the ponytail is
rebuilt from 16 broad, flattened locks (7 outer, 6 inner, 3 short ones over
the arch) generated from curves, replacing the 31 thin tubes (16,740 -> 7,360
triangles). Shading is painted into vertex colours (light ridge, darker edges
and underside). Node `Coda`, material and the four `Ponytail_*` bones are
unchanged. The construction follows what was observed in a commercial
cel-shaded reference the user supplied for study (hair as one sculpted mass
of wide locks); no geometry, texture or rig was taken from that file, and it
is not in the repository. Labels: Revisione 11 / 0.6.0 EXP. File 3.78 MB.

Checks: 16 tests pass; zero glTF errors/warnings. Inspected dressed, without
contours: profile, three-quarter rear, rear. Not inspected: contours on the
new tail, bone sway up close, hair toggle, real phone.

Still open: fringe and side locks are the old thin construction and no
longer match the tail; no side braid; lock tips are straight; ears more
orange than the face; outfit, shoulder tattoo, joint detail not started.

# Earlier checkpoint — revision 10 (branch `nelielclaude`)

Face state confirmed by the user: short, wide lower face with the pointed
chin of commit `77c6afa`. A chin-rounding attempt was rejected and reverted;
do not round or lengthen the chin without asking.

`tools/refine_hair.py`, new last stage of the rebuild: removes the two
antenna strands on the crown (152 triangles), fans the ponytail out (up to
+75% width at the tips, more depth, soft wave), blends ear texels of the face
texture toward the skin tone, and compacts the file by dropping unreferenced
accessors and buffer views (4.52 -> 4.02 MB). Labels: Revisione 10 / 0.5.0 EXP.

Checks: 16 tests pass; zero glTF errors/warnings. Inspected with contours:
face front, three-quarter, profile; body front, profile, rear (Costume studio).
Limits: ears still render more orange than the face, so the texture blend did
not address the cause (not yet found); ponytail strands are thin and spiky
rather than full locks, and its bones were not moved to follow the wider
shape; no braid; fringe unchanged; provisional outfit and expressions not
re-inspected; real-phone performance not measured.

---

# Checkpoint — 11 November 2026, revision 09 (branch `nelielclaude`)

User gave free choice of next step. `tools/refine_identity.py`, new last
stage of the rebuild: amber skin tone (target lit sRGB 226,170,138). The body
texture is retinted only on skin pixels and re-embedded as PNG; the face
material gets a `baseColorFactor` computed to reach the same tone. Lower face shortened and cheeks widened (see correction below), on all
facial layers and morph endpoints. `src/materials.js`: the face now uses the same two tones
as the body with a wide terminator biased toward light, so neck and face match.
Studio labels read Revisione 09 / 0.4.9 EXP.

Correction on user feedback: lengthening the chin was wrong. The reference
face is short and wide (eye line to chin about 0.55-0.6 of the face width)
while the model was near 0.7. The stage now raises the chin by 9 mm and
widens the cheeks by 4.5% instead. Do not lengthen the lower face again.

Checks: 16 tests pass; zero glTF errors/warnings. Inspected with contours:
face front, three-quarter and profile; body front, profile, rear in Costume
studio. The provisional outfit was captured but not reviewed after this pass.
Limits: ears are more orange than the face; face still slightly pinker than
the body; hard shadow under the jaw in three-quarter view; expressions not
re-inspected after the chin change; GLB is 4.5 MB because superseded skin
arrays and the old body texture are still stored (needs compaction);
ahoge, hair, outfit and tattoo placement unchanged.

---

# Checkpoint — 11 November 2026, revision 08 (branch `nelielclaude`)

`tools/refine_subdivide.py`, new last stage of `tools/rebuild_refined.py`:
one level of Loop subdivision on the skin primitive only (7,732 -> 30,928
triangles, 16,986 vertices). Positions are smoothed on a topology welded
across UV seams; borders stay fixed; UVs interpolated, skin weights blended to
four influences, normals recomputed on the welded surface. The old skin
arrays remain in the file as unused data. GLB is now 4.06 MB (was 2.93 MB).
Studio labels read Revisione 08 / 0.4.8 EXP.

Checks: 16 tests pass; zero glTF errors/warnings. Inspected with contours on,
front, profile and rear, in Costume studio and with the provisional outfit.
Result: smoother silhouette and cleaner shadow terminator on torso and limbs.
Limits: the swimsuit's lower edge became ragged; two small light dots appear
on the bust of the provisional outfit; no extra sculpted detail yet (elbows,
knees, hands); performance on a real phone not measured with the larger mesh.

---

# Checkpoint — 11 November 2026, revision 07 (branch `nelielclaude`)

Work on this revision lives on branch `nelielclaude`, started from `bdd92c3`.
`main` is untouched. Goal agreed with the user: remove the childlike read of
the figure, starting from the body.

Diagnosis from the r06 bind pose: shoulder joints only 0.22 m apart against a
0.23 m wide head, thin thighs and no waist/hip contrast.

Completed: `tools/refine_body.py`, added as the last stage of
`tools/rebuild_refined.py`. One smooth space map moves every mesh layer, every
morph endpoint and every joint (node translations and inverse bind matrices):
shoulders +22 mm per side, narrower waist, wider hips, fuller bust, thicker
thighs and calves, head scaled to 93% about the neck, legs 10% longer
between ankle and hip (about +8 cm of height). Normals are transformed with
the map's Jacobian rather than recomputed. Topology, UVs and weights unchanged.

The studio no longer applies the run-time sideways stretch (`root.scale.x`
1.08) to this revision: `loadAvatar` takes `{ widen }`, and the base 0.3 keeps
1.08. The trunk width is baked into the mesh, so the face is 8% narrower.
`controlCamera` takes optional framing; the studio raises both views for r07.

Correction: the first push of this revision (`db6a0e2`) shifted the head
sideways together with the shoulders, widening the face. The user spotted it;
pixel measurement confirmed head width +10%. Fixed in the following commit.

Checks: 16 tests pass; both GLBs zero glTF errors/warnings. Inspected with the
real toon shader in Chromium with software WebGL (SwiftShader): front,
profile, rear, close-up, poses Curiosa and Dinamica, smile and wave, compared
with r06. Not checked: real-phone performance and touch.

Proportion study mode (requested by the user, who could not judge the body
under the provisional outfit): the studio's Outfit button now cycles Notte →
Ametista → Costume studio. The third state hides the skirt, sleeve and boot
geometry and swaps the body texture for `assets/body-study.png`, built by
`tools/build_study_texture.py`: painted garments replaced by a flat skin tone
and a plain two-piece swimsuit placed from each texel's rest position and the
rig joints. Regenerate it after any body revision. Arm thickening reduced from
8% to 3% after seeing the bare arms. Inspected front, profile, three-quarter
rear and rear at 1.65x pixel ratio. Small light specks remain on the side of
the swimsuit top; the thigh tattoo is absent in this mode.

Second body pass, after the user confirmed the figure lacked curves: hips
+27% width at the pelvis, fuller rear, thighs +33% radius tapering to the
knee, waist slightly narrower, bust projected forward rather than widened.
Inspected in Costume studio: front, profile, rear. The dressed outfit was not
re-inspected after this pass. Style target restated by the user: Genshin-like
3D cel shading, for both the look and ease of modelling (rendering reference
only; no proprietary assets).

Third body pass on user feedback (hips too wide, bust could be larger, body
hard to read): pelvis widening reduced from 27% to 13%, thigh growth from 33%
to 24%, bust enlarged and projected further. New `skin` material profile in
`src/materials.js`: two-tone cel shading from the key light with a crisp
terminator and warm tinted shadow, and the body now takes part in the optional
contours. Inspected in Costume studio with contours on: front, profile, rear.
Limits: the shadow terminator is jagged on shoulders and back because the body
mesh is coarse (about 4,600 skin vertices); the swimsuit top has an irregular
edge at the side; dressed outfit not re-inspected with the new skin shading.

Fourth body pass on user feedback: pelvis widening 13% -> 7%, thigh growth
24% -> 19%, bust larger again. Inspected in Costume studio with contours:
front, profile, rear.

Known limits: face geometry is unchanged apart from width and still reads
young (large eyes, short lower face). Skin is still pale, hair and outfit
unchanged, tattoo still on thigh.

Next: adult face proportions, then skin tone and tattoo placement, then hair
volume and outfit. Private references stay out of the repository.

---

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
