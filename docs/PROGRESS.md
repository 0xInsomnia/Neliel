# Piedi bloccati a terra — 20 novembre 2026

Nuovo `tools/blender/bandai/foot_lock.py`: durante l'appoggio il tallone (poi
l'avampiede) resta fermo e la direzione del piede non ruota; correzione
orizzontale di piede e dita nel retarget, l'IK piega la gamba.

Verifiche con le stesse soglie del blocco (punto entro 1 cm dalla quota minima,
sotto 0,25 m/s): scivolamento per appoggio da 10–41 mm a 0 mm (tallone) e
2–4 mm (avampiede) nelle camminate, 0–3 mm in 8 clip su 12. Nessuno scatto in
più a coscia e tibia (stessi massimi fra fotogrammi). Capelli, viso e "Prova"
invariati. Restano 6–14 mm dove la gamba dell'attrice è completamente tesa
(`byebye_normal`, `guide_normal`, `call_normal`, `bye_normal`): servirebbe
abbassare il bacino.

---

# Viso per le clip Bandai — 20 novembre 2026

La testa visibile (`head`) usa shape key MMD; le ossa del viso Daz non pesano su
mesh visibili. Nuovo `tools/blender/bandai/face_anim.py`: quattro proprietà su
`Root` (`Viso_ciglia`, `Viso_occhi_felici`, `Viso_sorriso`, `Viso_bocca`) con
chiavi nella Action di ogni clip e driver su sei shape key; sguardo con l'osso
`両目`. Battiti di ciglia (circa 18 al minuto), piccoli movimenti degli occhi,
espressioni per clip legate al gesto.

Verifiche (bpy 4.3.0; un passaggio con 5.3.0): con le proprietà a 0 il viso è
identico all'originale pixel per pixel; "Prova" invariata; corpo e capelli
identici alla versione precedente; primi piani e video del viso controllati.
Limiti: espressioni interpretate, nessun labiale; `照れ`/`なごみ`/`はぅ` esclusi
per texture mancante.

---

# Dita per le clip Bandai — 19 novembre 2026

La mocap non contiene le dita: le mani restavano piatte. Nuovo
`tools/blender/bandai/hand_pose.py`: chiavi sui controlli delle dita del rig
(ossa base di ogni dito e `Carpal4`; le altre falangi ne copiano la rotazione).
Mano rilassata di base, aperta quando la mano sale verso il petto (altezza fra
bacino e spalla 0,35–0,7) o il braccio si allunga oltre 0,85 lunghezze dal
bacino; filtro di 0,15 s.

Verifiche: primi piani delle mani in tutte le clip; le dita si chiudono verso il
palmo, mano aperta nei saluti, rilassata in camminata. Corpo identico alla
versione precedente, "Prova" invariata (84 chiavi a riposo in più per le dita),
capelli invariati. Limite: posa ricostruita, non registrata; mani giunte
nell'inchino si compenetrano.

---

# Camminata senza zoppia — 19 novembre 2026

Segnalazione dell'utente: in `walk_normal` il personaggio sembrava zoppicare.
Misura: piegamento delle ginocchia identico alla mocap, ma bacino 3 cm più alto
sull'appoggio destro e 2,5 cm più basso sul sinistro. Causa: piedi calibrati al
fotogramma 0, in cui il piede sinistro è sollevato a metà passo; da appoggiato
restava col tallone giù di 8° (caviglia a 49 mm) e il destro sulle punte
(73 mm). Anche altre clip avevano piedi inclinati di 6–19°.

`retarget.py` ora calibra ogni piede nel fotogramma di appoggio (`planted_frame`)
e porta a terra l'avampiede quando lo è nella mocap (`ball_contact`).

Verifiche: bacino in appoggio sinistro/destro 890/891 mm in `walk_normal`
(894/895 in `walk_feminine`); prima il piede sinistro non toccava mai terra.
Piedi appoggiati piatti entro 2° nelle clip in piedi; nelle clip `feminine` il
piede sinistro poggia sull'avampiede (tallone alzato 15–21°) e tocca terra.
Busto, mani e piedi coincidono col retarget; capelli invariati (coda 0%
compenetrazione). Video di profilo prima/dopo e vista 3/4 delle camminate.

---

# Postura e fisica dei capelli per le clip Bandai — 19 novembre 2026

Segnalazione dell'utente: nella camminata seno e glutei sembravano cadere, e i
capelli entravano nel corpo. Causa misurata: già al fotogramma 0 il retarget
ruotava il bacino indietro di 7–10°, il torace in avanti di 14–20° e la testa
indietro di 20–35°, allineando le ossa alla colonna della mocap. In più le clip
`feminine` partono con l'attrice girata di 30–50°: il busto veniva raddrizzato
ma gli arti no.

Correzioni in `tools/blender/bandai`:

- `retarget.py`: bacino, schiena, collo e testa tengono la posa di riposo al
  fotogramma 0 (`KEEP_REST`) e ricevono solo il movimento successivo; la clip
  viene girata perché il bacino guardi avanti al fotogramma 0. Torsione massima
  di coscia scesa da 62° a 28°, del braccio da 108° a 58°.
- `hair_physics.py`: fisica calcolata e salvata come chiavi sulle catene MMD
  (coda `Bip31`–`Bip42`, ciocche `Bip29/36/37`, `Bip30/38/39`). Leve fino al
  fondo reale della mesh (allungata da shape key), inerzia con smorzamento
  relativo, gravità vera con la forma di riposo come equilibrio, collisioni con
  `Body` e `head`.
- `apply_bandai.py`: alle Action già presenti ("Prova") una chiave col valore
  originale per i 259 canali animati solo dalle clip, così cambiando Action non
  restano pose residue.

Verifiche (bpy 4.3.0; un passaggio anche con 5.3.0):

- Busto, collo, testa, mani e piedi entro 0,7° dal retarget; gomiti e
  ginocchia entro 1,9 cm.
- Punti centrali dei capelli dentro il corpo, rigidi → con fisica: coda da
  0–57% dei fotogrammi (fino a 69 mm) a 0% in tutte le 12 clip; ciocche da
  5–97% a 0%, tranne `walk_feminine` 13% (fino a 22 mm, contro la spalla).
- Oscillazione della coda al massimo 67°, salti fino a 12° tra fotogrammi.
- "Prova" dopo aver riprodotto una clip: pose identiche all'originale (scarto
  massimo 5e-5).
- Render Workbench di tutte le clip (fronte, profilo, retro) e video di 4 clip.

Limiti: collisioni solo sull'asse delle ciocche (bordi larghi della coda
possono ancora sfiorare il corpo), nessuna collisione tra capelli o con i
vestiti; nell'inchino la coda cade solo in parte (base irrigidita perché torni
dietro la schiena). Da verificare nel Blender dell'utente con lo shading EEVEE.

---

# Clip Bandai Namco sul rig Blender "Jean" — 19 novembre 2026

Nuovo `tools/blender/bandai/apply_bandai.py` (dettagli e uso nel README della
cartella). Applica le 12 clip BVH come Action del rig `Jean`, una per clip,
con chiavi sui controlli: `Torso`, `tweak_spine*`, collo e testa, clavicole,
`HandIK`/`ElbowIK`, `FootIK`/`KneeIK`, dita dei piedi, torsione degli
avambracci. Salva solo in una copia, a 30 fps; la Action "Prova" dell'utente
riceve il fake user. Il `.blend` e i BVH (CC BY-NC) restano fuori dal repository.

Esame del rig, in sola lettura: busto comandato da Copy Transforms dei
`tweak_spine`, braccia e gambe con IK sempre attivo (catene di 3 ossa), nessuno
switch IK/FK per gli arti. Corretto `retarget.py`: `ThighTwist` non seguiva la
coscia mappata, quindi ginocchio e tibia restavano rigidi col bacino (fino a
9,5 cm di scarto).

Verifiche eseguite con bpy 4.3.0 (versione del file) e 5.3.0 (Action con slot):

- Valutazione di ogni fotogramma di tutte le clip contro il retarget: busto,
  collo, testa, clavicole, mani, piedi entro 0,4° e 0,1 mm. Gomiti, ginocchia,
  avambracci entro 1,9 cm; braccio e coscia hanno direzione entro pochi gradi
  ma torsione diversa dal retarget (fino a 108°/62°), decisa dal piano di
  piegatura dell'IK.
- Torsione del polso rispetto all'avambraccio: da 45–103° a 0–30° dopo le
  chiavi di pronazione (10% e 60%, come lo switch `Hand_control=0` del rig).
- Nessun salto oltre 27° tra fotogrammi consecutivi; scivolamento dei piedi
  appoggiati 1–3,5 cm.
- Render Workbench (Mesa, senza GPU) di 4 fotogrammi per clip da fronte,
  profilo e retro. Non certifica lo shading EEVEE/toon del file.
- Checksum del `.blend` originale invariato; `npm test`: 16 test passati.

Limiti: capelli senza fisica che attraversano braccia e busto; in particolare
la coda attraversa la schiena e spunta sulla pancia in `walk_normal` e
`bow_normal`, perché la postura della mocap è più eretta del riposo. Dita ferme,
mani che si sovrappongono al corpo nell'inchino, piedi non bloccati a terra,
gomito/ginocchio fino a 2 cm fuori posto per l'osso centrale corto delle
catene IK. Da verificare in Blender 4.3 dell'utente con il suo shading.

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
