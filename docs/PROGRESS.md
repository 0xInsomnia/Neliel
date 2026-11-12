# Update — 12 November 2026, revision 13 eyes

The user rejected reshaping the stock eyes ("vanno ridisegnati, forma
totalmente diversa"). `tools/draw_eyes.py` now replaces the stock sclera,
iris, catchlight, contour and lash primitives with one vertex-coloured
primitive built from curves (almond opening, round clipped iris, winged
upper lash, thin lower lash) lying just in front of the skin, with its own
smile / surprised / blink / wink targets. `refine_face_hair.py` also lowers
the lids by baking 32% of blink and levels the eye openings. The earlier
squash in `refine_figure.py` is reduced to 6%.
Checked close up, dressed: front, three-quarter, smile, surprised, wink.
Not checked: blink in motion, real phone. The unused stock eye textures are
still embedded in the file.

# Checkpoint — 12 November 2026, revision 13 (branch `nelielclaude`)

Head shape after the user's step-by-step corrections (all in
`refine_proportions.py` / `refine_figure.py`): whole head 9% narrower, skull
cap a further 8%, crown 15% lower, lower face 12% shorter from the chin,
softer chin tip, 3.5% wider at ear height. Each was confirmed by moving on
to the next request; treat them as approved.

`tools/refine_face_hair.py`, new last stage:
- ears: protruding part 30% smaller;
- ponytail 25% longer below the shoulders, purple scrunchie at the tie
  (vertex-coloured, same primitive, so `Coda` stays one skinned mesh);
- four face-framing locks and three thin fringe strands in the existing thin
  style, added to `Ciocche laterali`;
- face texture: coloured fuller lips, shadow under the nose, darker eyelids;
- triangle clip moved 11 mm back onto the fringe.
Labels: Revisione 13 / 0.8.0 EXP.

Checks: 16 tests pass; zero glTF errors/warnings. Inspected dressed at phone
size: portrait front and three-quarter; full figure profile and rear.
Not inspected: expressions (lips are painted on the base texture and the
mouth morphs were not re-checked), poses, Costume studio, real phone.

Still open: side braid; fringe and cap are still the smooth helmet; small
lash pieces at the temples; ears' colour; shoulder tattoo; real outfit.

# Correction — 12 November 2026, revision 12 head shape

The user rejected the head of the first revision 12 build ("testa deforme, a
zucca"). Cause: the jaw-only narrowing of revision 11 under an unchanged
skull and hair cap. `refine_proportions.py` now narrows the whole head by 9%
(face, ears, hair together) and lowers the crown above the eyes by 15%
instead; the approved jaw shape is kept. Do not narrow the jaw alone again.
Checked at phone size: portrait front, three-quarter, full figure dressed.
Known and not fixed: the triangle clip floats about 1.5 cm in front of the
fringe; small dark lash pieces show at the temples.

# Checkpoint — 12 November 2026, revision 12 (branch `nelielclaude`)

The user supplied a character sheet (standing front figure, expressions,
outfit variants) and asked for the proportions plus first finishing touches.

- `tools/refine_figure.py`, new last stage: hips +11% wide, fuller rear,
  thighs +15% and calves +4% around the leg axes; eye opening 18% lower with
  a slight upward tilt of the outer corner (lashes, brows and blink follow).
  This reverses part of the earlier hip narrowing, on the user's request.
- `refine_identity.py`: skin tone darkened from (226,170,138) to (212,150,116).
- `build_study_texture.py`: `skin_details` paints navel, abdomen lines, hip
  crease, collarbones, sternum notch, knee shadows and warm knees/shoulders,
  placed from joints. These exist only in Costume studio; the provisional
  outfit texture still covers the torso.
Labels: Revisione 12 / 0.7.0 EXP.

Checks: 16 tests pass; zero glTF errors/warnings. Inspected in Costume
studio: body front, profile, rear; face front, three-quarter, profile.
Not inspected: provisional outfit, expressions, poses, real phone.

Still open, in the order agreed with the user: hair as in the reference
(side braid, scrunchie, longer tail, long face-framing locks, fringe strands
across the eyes — thin strands, not wide locks); mouth and nose; shoulder
tattoo; real outfit; poses and expressions from the sheet.

# Earlier checkpoint — revision 11 (branch `nelielclaude`)

A wide-lock ponytail rebuild was tried and rejected by the user ("erano
meglio prima"); it was reverted. Keep the revision 10 hair; only add missing
locks in the same thin style, after asking which ones.

`tools/refine_proportions.py`, new last stage: proportions matched to a
commercial cel-shaded character the user supplied as a study reference
(measurements only; no data from that file is used and it is not in the
repository). Shoulders back in by 21 mm (arm joint 136 -> 115 mm from the
midline, undoing the revision 07 shift), arms 8% longer between shoulder and
wrist, lower face up to 15% narrower around the cheek line. The user asked
for this ("copia il modello e vediamo cosa esce"); it supersedes the earlier
note about not touching the face, but only for this change.
`refine_body.apply_map` now holds the shared space-map machinery; revision 10
rebuilds byte-identical after the refactor. Labels: Revisione 11 / 0.6.0 EXP.

Checks: 16 tests pass; zero glTF errors/warnings. Inspected in Costume
studio: body front, profile, rear; face front, three-quarter, profile.
Not inspected: provisional outfit, expressions, poses, real phone.

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
