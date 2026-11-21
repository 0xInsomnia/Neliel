# Consegna: animazioni Bandai sul rig "Jean" e prova di export GLB

Nota per chi continua il lavoro (persona o AI). Stato al 21 novembre 2026.
Prima di modificare il repository leggere `AGENTS.md`, `README.md`,
`docs/MESH_REFINEMENT.md` e `docs/PROGRESS.md`.

## In breve

- Il file `Neliel_bandai_test.blend` (Blender 4.3, copia del file del
  proprietario `Neliel_rig_fasce_test_02.blend`) contiene **49 clip di motion
  capture Bandai Namco** applicate al rig `Jean`, una Action per clip, più
  l'Action originale "Prova" invariata. 30 fps.
- Ogni clip comprende: corpo (retarget sui controlli IK del rig), piedi bloccati
  a terra, mani fuori da seno e vita, dita ricostruite, viso (battiti di ciglia,
  sguardo, espressioni per stile), fisica dei capelli cotta in chiavi.
- `neliel_jean_clips.glb` è l'export glTF dello stesso personaggio con le 50
  Action (49 clip + "Prova") come 50 animazioni, pronto per three.js: movimento
  cotto sulle ossa che deformano la mesh, espressioni del viso come animazioni dei
  morph target. 40 MB con texture WebP (66 MB con le PNG originali, opzione
  `--images AUTO`). Verificato in three.js (dettagli sotto).
- **L'app web del repository oggi NON usa questo modello**: carica
  `assets/neliel-refined.glb`, uno scheletro diverso (VRoid, `J_Bip_*`). Vedi
  "Integrazione nell'app web".

## File

Nel repository (`0xInsomnia/Neliel`, branch `ccr-83a807c9-30ya38`, PR #4 verso
`main`), cartella `tools/blender/bandai/`:

| file | ruolo |
| --- | --- |
| `apply_bandai.py` | script principale: BVH -> Action sul rig `Jean` (uso nel README della cartella) |
| `bvh.py`, `retarget.py` | lettura BVH e retarget sulle ossa del rig |
| `foot_lock.py` | piedi fermi durante l'appoggio |
| `arm_collision.py` | mani e avambracci fuori dal busto (sposta `HandIK`) |
| `hand_pose.py` | pose delle dita |
| `face_anim.py` | viso: proprietà `Viso_*` su `Root` + driver sulle shape key della testa |
| `hair_physics.py` | fisica dei capelli (ossa `Bip29`–`Bip42`) cotta in chiavi |
| `export_glb.py` | export GLB con animazioni ed espressioni cotte |
| `README.md` | descrizione completa del metodo e **limiti noti** |

Fuori dal repository (non vanno committati: `.blend` esclusi dal `.gitignore`,
BVH con licenza non commerciale, riferimenti privati):

| file | contenuto |
| --- | --- |
| `Neliel_bandai_test.blend` | rig con le 49 Action (+ "Prova") |
| `neliel_jean_clips.glb` | export glTF di personaggio e clip |
| `bvh/` | i 49 BVH usati (Bandai Namco Research Motiondataset-1, CC BY-NC 4.0) + licenza |
| `Neliel_49_clip.mp4` | anteprima Workbench di tutte le clip in sequenza |

Rigenerare (Blender 4.3, file sorgente del proprietario accanto agli script):

```sh
blender -b Neliel_rig_fasce_test_02.blend --python apply_bandai.py -- \
    --bvh-dir bvh --out Neliel_bandai_test.blend --verify --compress
blender -b Neliel_bandai_test.blend --python export_glb.py -- \
    --out neliel_jean_clips.glb            # --images WEBP per texture più leggere
```

`apply_bandai.py` richiede circa 25 minuti per 49 clip e non sovrascrive mai il
file sorgente.

## Le clip

Nomi = nomi delle Action e delle animazioni glTF: `<movimento>_<stile>[_2]`.

- Originali (12): `walk`, `bow`, `bye`, `byebye`, `guide` in `normal` e
  `feminine`; `call_normal`, `respond_normal`.
- Spostamenti (12): `walk_*_2` (seconda ripresa), `walk-back`, `walk-left`,
  `walk-right`, `run`, `dash`, in `normal` e `feminine`.
- Emozioni (25): `walk`, `bow`, `bye`, `byebye`, `guide` in `happy`, `sad`,
  `angry`, `proud`, `not-confident`.

Le camminate e le corse spostano il personaggio nello spazio (root motion sul
bacino): per un'animazione sul posto va tolta la traslazione orizzontale.

## Rig e controlli (in Blender)

- Armatura `Jean` (scala oggetto 1,2). Busto: `Torso`, `Hips`, `Chest`,
  `tweak_spine*`; collo `NeckControl`; braccia IK a 3 ossa con `HandIK.L/R` e pole
  `ElbowIK.L/R`; gambe IK con `FootIK.L/R`, `ToeIK.*`, pole `KneeIK.*`; occhi `両目`;
  capelli MMD `Bip29`–`Bip42`. Proprietà su `Root`: `Hand_control`,
  `Spine_control`, `Head_control` e le 7 `Viso_*` del viso.
- Le Action mettono chiavi su 381 canali (gli stessi in tutte le 50 Action).
- Il viso funziona con driver semplici (nessuno script Python richiesto):
  `Viso_*` -> shape key MMD della mesh `head` (`ウィンク`, `ウィンク右`, `ウィンク２`,
  `ｳｨﾝｸ２右`, `口角上げ`, `あ`, `Eye_Tired`, `じと目`, `ん`).

## Export GLB: cosa fa e cosa è stato verificato

`export_glb.py`, sul file con le clip (le modifiche restano nella sessione, il
`.blend` non viene salvato):

1. cuoce i valori delle shape key comandate da driver (viso e due mesh del top)
   in Action di shape key, una per clip, e toglie i driver;
2. per le mesh con shape key non animate (corpo, capelli…) salva nella mesh la
   forma mostrata in Blender e toglie le shape key: le shape key del corpo sono
   relative a due chiavi diverse ("Basis" e il riferimento "fix.001"), cosa che
   glTF non può esprimere (esportate così gonfiavano gambe, fianchi e spalle);
3. mette ogni clip su una traccia NLA con il suo nome (armatura + viso) ed esporta
   con l'esportatore glTF di Blender: modalità `NLA_TRACKS`, campionamento di ogni
   fotogramma (vincoli e IK cotti), solo ossa che deformano (491), inizio a tempo
   0, oggetti visibili e renderizzabili, **senza modificatori** (niente
   suddivisione né contorno solidify: le shape key restano).

Verifiche fatte su `walk_normal`, `bow_feminine`, `guide_feminine` e, nel GLB
completo, anche su `dash_feminine`, `walk_not-confident`, `byebye_happy`:

- posizioni di mani, piedi, avambraccio, testa, petto e ciocche in three.js
  (`AnimationMixer`) uguali a Blender: scarto 0,0 mm in tutti i fotogrammi
  controllati;
- valori dei morph del viso uguali a Blender (es. `ウィンク` 0,408 e `口角上げ`
  0,788 al fotogramma 60 dell'inchino);
- `gltf-validator`: 0 errori, 3 avvisi `NODE_SKINNED_MESH_NON_ROOT` (mesh
  skinnate figlie dell'armatura: three.js le gestisce);
- render three.js (WebGL software) della posa di riposo, `bow_feminine`
  fotogramma 100, `guide_feminine` fotogramma 33 e `byebye_happy` fotogramma 40:
  corrispondono ai render di Blender; texture PNG e WebP indistinguibili a
  questa scala.

Attenzione: il tempo glTF 0 corrisponde al fotogramma 1 di Blender
(`tempo = (fotogramma - 1) / 30`).

Non verificato: tutte le 49 clip una per una nel browser, i materiali (in glTF
diventano PBR standard: il cel shading va rifatto lato web, come fa già l'app con
i propri materiali), prestazioni su telefono.

## Integrazione nell'app web

L'app (`index.html`, `cel-studio/`, `src/avatar.js`, `src/cel-main.js`) carica
`assets/neliel-refined.glb`: 155 giunti con nomi VRoid (`J_Bip_C_Hips`,
`J_Bip_C_Chest`, `J_Sec_*_Bust*`, ossa `HairJoint-*`), nessuna animazione. Le
clip di questa consegna sono sul rig `Jean` (nomi DAZ/MMD: `lShldrBend`,
`chestUpper`, `Bip40`…) e non si applicano direttamente a quel modello.

Due strade:

- **A. Usare `neliel_jean_clips.glb` come modello dell'app.** Mantiene tutto il
  lavoro (capelli, piedi, mani, viso). Da adattare: caricamento e materiali anime
  in `src/avatar.js`, controlli touch e morph del viso (nomi giapponesi MMD invece
  di quelli attuali), peso del file (vedi sotto). `AGENTS.md` chiede di preservare
  controlli touch, rig e morph facciali: va concordato col proprietario.
- **B. Rifare il retarget sul modello attuale (VRoid).** L'app resta com'è;
  `bvh.py`/`retarget.py` vengono dalla versione GLB del progetto, ma fisica dei
  capelli, piedi bloccati e correzioni di mani/seno andrebbero rifatte per quello
  scheletro.

Peso del GLB completo: animazioni 25 MB (circa 3 MB ogni 1000 fotogrammi), mesh
2 MB, texture 27 MB in PNG oppure 0,8 MB in WebP. Per il web conviene
comprimere (es. `gltf-transform`: resample, quantize, texture WebP/KTX2) e
magari caricare le clip separatamente.

## Limiti noti (dettagli e numeri nel README della cartella)

- Capelli: in 14 clip su 49 qualche vertice entra nel corpo per più di 5 mm in
  almeno il 10% dei fotogrammi (ciocca presa fra braccio e petto, mano nella coda
  in `bow_feminine`); nessuna collisione tra capelli o con i vestiti.
- Piedi: in 15 clip il piede scivola ancora di 5–23 mm (gamba tesa, passi
  laterali o all'indietro).
- Corsa e scatto: la coda si muove molto e in fretta.
- Dita ricostruite (le mani giunte si compenetrano); viso interpretato, niente
  labiale.
- Mani e busto: in tutte le clip entro 5 mm (massimo 6 mm in un fotogramma di
  `dash_feminine`); il test riguarda il busto, non cosce o bacino.

## Licenza e privacy

- BVH e animazioni derivate: Bandai Namco Research Motiondataset-1, CC BY-NC 4.0
  (solo uso non commerciale, con attribuzione). Non pubblicarli nel repository.
- Immagini di riferimento e dati personali del proprietario sono privati e non
  vanno committati.
