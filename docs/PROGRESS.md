# Mani fuori dal petto e capelli fuori dal corpo — 21 novembre 2026

Segnalato: nell'inchino femminile e nell'indicazione braccia e capelli
entravano nel seno. Il controllo precedente sui capelli guardava solo due punti
per osso e diceva "coda mai dentro il corpo": era sbagliato. Misurando la mesh
intera, i capelli entravano di oltre 5 mm in almeno il 10% dei fotogrammi in 42
clip su 49, e mani e avambracci in 13 clip (fino ad almeno 7 cm).

Nuovo `tools/blender/bandai/arm_collision.py`: dopo le chiavi, ogni fotogramma
viene valutato e `HandIK` spostato fuori dal busto (pelle più altezza della
fascia dove la copre), con la correzione smussata nel tempo. `hair_physics.py`:
collisioni su 14 vertici per osso calcolati con i pesi reali della mesh, 4
vertici del corpo mediati per la normale, contatti senza rimbalzo, 1,2 cm dalla
pelle, rotazioni smussate di 1 fotogramma. Due tentativi scartati: la fascia
come ostacolo (bordo aperto: distanze sbagliate, mani spostate fino a 10 cm
senza motivo) e l'interpolazione del corpo fra fotogrammi (nessun
miglioramento).

Verifiche sul file rigenerato (49 clip, `--verify`): mani e avambracci dentro il
busto di oltre 5 mm in almeno il 10% dei fotogrammi in 2 clip (prima 13: restano
gli scatti); capelli in 14 clip (prima 42); tremolio delle punte (95° percentile
dell'accelerazione) simile o minore nella maggior parte delle clip, salito al
massimo a 16 mm/fotogramma² (`respond_normal`). "Prova" invariata dopo aver
suonato una clip (scarto massimo 3,5e-5), 50 Action con 381 canali ciascuna,
30 fps. Primi piani prima/dopo di `bow_feminine` (fotogrammi 60, 100, 143, 187)
e `guide_feminine` (33, 139) controllati: la mano si appoggia sul seno, le
ciocche non attraversano più la fascia. Render Workbench di tutte le 49 clip
rifatto (4157 fotogrammi, nessun errore; poster di metà clip controllati, nello
scatto la coda vola di lato). Limiti rimasti nel README della cartella.

---

# Render di controllo di tutte le 49 clip — 20 novembre 2026

Render Workbench (solo texture, non i materiali finali), vista di tre quarti,
15 fps (un fotogramma su due), camera che segue il bacino, dal file prodotto
dopo la correzione dei capelli. 49 clip su 49 senza errori, 4157 fotogrammi;
poster di metà clip controllati: personaggio sempre inquadrato. Video e
galleria restano fuori dal repository (dati Bandai CC BY-NC, solo uso
personale). Restano valide le limitazioni elencate sotto.

---

# Capelli corretti per le nuove clip — 20 novembre 2026

Problemi visti nei render delle 37 nuove clip: in `walk_happy` la coda volava
sopra la testa nei primi fotogrammi (assestamento troppo breve, la clip parte
lontano dal riposo), in corsa e scatto si piegava fino a 140–160°, e nelle clip
tristi le ciocche laterali entravano nel petto (fino al 64% dei fotogrammi).

`hair_physics.py`: assestamento di 2 s con più smorzamento, limite di 65° per
osso della coda e più smorzamento, ciocche più sensibili alla gravità e con le
ossa superiori che tengono fuori dal corpo anche la punta.

Verifiche su 49 clip: piega massima della coda da 161° a 65°, delle ciocche da
70° a 48°; capelli dentro il corpo solo in `dash_feminine` (1%, 4,5 mm) e
`dash_normal` (1 fotogramma, 11 mm) contro 4 clip prima; 42 clip su 49 con
variazioni fra fotogrammi entro 20° (le altre: corsa, scatto, movimenti rapidi,
fino a 30°). Render prima/dopo di `walk_happy` e `dash_feminine` controllati.

---

# 37 nuove clip Bandai: spostamenti ed emozioni — 20 novembre 2026

Scaricate dal repository pubblico Bandai Namco (dataset 1) 37 clip: corsa,
scatto, camminata all'indietro e laterale (`normal`, `feminine`), seconde
riprese delle camminate, e `walk`/`bow`/`bye`/`byebye`/`guide` negli stili
`happy`, `sad`, `angry`, `proud`, `not-confident`. Le 12 iniziali coincidono con
i file del repository. In tutto 49 Action.

Nuovo in `tools/blender/bandai`: per gli stili emotivi il busto è calibrato
sulla postura neutra della stessa attrice (`neutral_posture`), perché lo stile
è già nella postura iniziale; tre nuovi canali del viso (`Eye_Tired`, `じと目`,
`ん`) ed espressioni per stile; mani chiuse in corsa. Le 12 clip già approvate
non cambiano (stesse chiavi del corpo).

Verifiche: busto/testa entro 0,7°, mani/piedi entro 0,2° dal retarget; tutte le
Action hanno gli stessi 381 canali (nessuna posa residua cambiando clip);
"Prova" invariata; viso a riposo identico pixel per pixel. Piedi: 34 clip su 49
entro 4 mm, le altre 5–23 mm (gamba tesa, passi laterali). Capelli e render nei
fogli di controllo e nei video.

---

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
