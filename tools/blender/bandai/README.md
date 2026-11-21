# Clip Bandai Namco sul rig "Jean" (Blender)

`apply_bandai.py` applica le clip del dataset Bandai Namco Research
Motiondataset-1 al rig `Jean` del file Blender del personaggio. Crea una
**Action per clip**, con il nome della clip e il fake user. Le chiavi sono sui
**controlli** del rig; le ossa di deformazione seguono tramite i constraint e
l'IK del rig.

I BVH (licenza CC BY-NC 4.0, uso personale) e i file `.blend` non sono nel
repository.

## Uso

Mettere `apply_bandai.py`, `bvh.py`, `retarget.py`, `hair_physics.py`,
`hand_pose.py`, `face_anim.py`, `foot_lock.py`, `arm_collision.py` e la cartella
`bvh/` accanto al `.blend`, poi:

```sh
blender -b Neliel_rig_fasce_test_02.blend --python apply_bandai.py -- \
    --bvh-dir bvh --out Neliel_bandai_test.blend --verify
```

In alternativa: aprire il `.blend`, caricare lo script nel Text Editor e
premere *Run Script*. Il risultato va in `Neliel_bandai_test.blend`, nella
stessa cartella.

Opzioni:

- `--clips walk_normal,bow_feminine`: applica solo alcune clip (senza, tutte quelle
  presenti in `--bvh-dir`; le 12 clip iniziali per prime).
- `--verify`: stampa lo scarto osso per osso rispetto al retarget.
- `--compress`: salva il file compresso.
- `--no-hair`: salta la fisica dei capelli.
- `--no-fingers`: lascia le dita a riposo.
- `--no-face`: niente battiti di ciglia, sguardo o espressioni (e nessun driver aggiunto).
- `--no-foot-lock`: lascia scivolare i piedi come nella mocap.
- `--no-arm-collision`: lascia entrare mani e avambracci nel petto come nella mocap.

Lo script non scrive mai il file aperto: rifiuta un `--out` uguale al file
sorgente. Imposta la scena a 30 fps, assegna a `Jean` la prima clip e mette il
fake user sulle Action già presenti, che altrimenti verrebbero perse al
salvataggio. Alle Action già presenti (es. "Prova") aggiunge una sola chiave,
con il valore del file originale, per ogni canale che le clip animano e loro no:
senza, passando da una clip a "Prova" quei canali resterebbero nell'ultima posa
della clip.

## Export GLB per il web

`export_glb.py` esporta personaggio e clip da un `.blend` già animato a un GLB
per three.js: vincoli e IK cotti sulle ossa che deformano (campionando ogni
fotogramma), espressioni del viso cotte nei morph target, una animazione glTF per
clip che parte da tempo 0 (= fotogramma 1).

```sh
blender -b Neliel_bandai_test.blend --python export_glb.py -- \
    --out neliel_jean_clips.glb [--clips walk_normal,bow_feminine] [--images WEBP]
```

Le shape key non animate (corpo, capelli) vengono fissate nella mesh: quelle del
corpo sono relative a due chiavi diverse e glTF non lo può rappresentare. Niente
modificatori (suddivisione, contorno). Dettagli, verifiche e integrazione
nell'app in `docs/HANDOFF_BANDAI.md`.

## Clip e file BVH

I BVH vengono dal repository pubblico
`BandaiNamcoResearchInc/Bandai-Namco-Research-Motiondataset`, cartella
`dataset/Bandai-Namco-Research-Motiondataset-1/data` (licenza CC BY-NC 4.0, solo
uso personale: non vanno nel repository). I file si rinominano col nome della
clip: `dataset-1_walk-back_feminine_001.bvh` diventa `walk-back_feminine.bvh`,
la seconda ripresa `_002` diventa `_2` (`walk_normal_2.bvh`).

Clip applicate finora (49): le 12 iniziali; spostamenti `run`, `dash`,
`walk-back`, `walk-left`, `walk-right` in stile `normal` e `feminine`, più
`walk_normal_2` e `walk_feminine_2`; emozioni `walk`, `bow`, `bye`, `byebye`,
`guide` negli stili `happy`, `sad`, `angry`, `proud`, `not-confident`.

Gli stili emotivi (`EMOTION_STYLES`) calibrano busto, collo e testa sulla postura
neutra della stessa attrice (media della sua `walk_normal`, `neutral_posture` in
`retarget.py`) invece che sul fotogramma 0, perché la postura dello stile c'è già
all'inizio della clip (busto in avanti di 13° in `walk_angry`, testa china di 24°
in `walk_not-confident`). Se il riferimento è di un'altra attrice (scheletro
diverso) lo script lo segnala e usa il fotogramma 0.

## Controlli animati

| Controllo | Contenuto |
| --- | --- |
| `Torso` | posizione e rotazione del bacino, spostamento nello spazio |
| `tweak_spine` … `tweak_spine.004` | curva del busto (le ossa `DEF-spine` … `chestUpper` li copiano) |
| `neckLower`, `neckUpper`, `head` | rotazione divisa per 1 − influenza, perché il rig ne copia 1/3 da `NeckControl` |
| `l/rCollar`, `l/rToe` | rotazione diretta |
| `HandIK.L/R`, `ElbowIK.L/R` | polso, orientamento della mano, pole del gomito |
| `FootIK.L/R`, `KneeIK.L/R` | piede e pole del ginocchio |
| `l/rForearmBend`, `l/rForearmTwist` | pronazione: 10% e 60% della torsione del polso, come lo switch `Hand_control=0` del rig |
| `Root`, `Hips`, `Chest`, `NeckControl`, `ToeIK.L/R` | una chiave a riposo, liberi per le modifiche |
| `Bip31`, `Bip40`–`Bip42` (coda), `Bip29/36/37`, `Bip30/38/39` (ciocche) | fisica dei capelli calcolata e salvata come chiavi |
| `l/rThumb1`, `l/rIndex1`, `l/rMid1`, `l/rRing1`, `l/rPinky1`, `l/rCarpal4` | posa delle dita (`hand_pose.py`): le altre falangi e i carpi copiano questi controlli |
| `両目` | sguardo (`face_anim.py`) |
| `Root["Viso_ciglia"]`, `["Viso_occhi_felici"]`, `["Viso_sorriso"]`, `["Viso_bocca"]`, `["Viso_occhi_stanchi"]`, `["Viso_sguardo_torvo"]`, `["Viso_bocca_chiusa"]` | viso (`face_anim.py`), tramite driver sulle shape key |

I pole sono messi dal lato in cui si piega l'arto nella mocap; con l'arto quasi
dritto seguono l'orientamento del segmento superiore.

## Piedi bloccati a terra

`foot_lock.py` segue tallone e avampiede di ogni piede. Un punto è in appoggio
quando è entro 1 cm dalla sua quota minima e quasi fermo (con isteresi). Durante
l'appoggio il punto a terra resta fermo: il tallone finché è giù, poi
l'avampiede, che parte da dove era mostrato nel fotogramma prima. Anche la
direzione del piede resta quella del primo contatto. Il blocco sposta e ruota
in orizzontale piede e dita nel risultato del retarget, quindi `FootIK`, il pole
del ginocchio e le verifiche usano la posizione bloccata. Dopo l'appoggio la
correzione si azzera in 5 fotogrammi. Una correzione che richiederebbe una gamba
più lunga del rig (o di quanto già chiede la mocap) viene ridotta.

## Mani fuori dal petto

L'attrice ha un petto molto più piccolo di Neliel: quando porta una mano al
petto, incrocia le braccia o tiene le mani davanti a sé, la mano di Neliel entra
nel seno; correndo, l'avambraccio passa nella vita, più larga. `arm_collision.py`,
dopo aver messo le chiavi dei controlli, valuta ogni fotogramma e misura i
vertici di avambraccio, mano e dita contro la pelle del busto: punto più vicino
delle facce e loro normale, tenendo in più l'altezza della fascia dove la copre
(la fascia stessa non è usata: i suoi bordi aperti davano falsi contatti). Dove
sono dentro, sposta il controllo `HandIK` dello spostamento minimo che li porta
tutti fuori più 3,6 mm (minimi quadrati, al massimo 1,25 volte il punto più
profondo per passata e 16 cm in tutto); il gomito segue con l'IK. Oltre 3,6 cm
di profondità, se lo spostamento punta verso il corpo o l'avambraccio è lungo il
fianco, la mano viene spinta in fuori dall'asse della schiena (lì la superficie
più vicina passa da davanti a dietro da un fotogramma all'altro). Con il braccio
quasi teso la mano si sposta attorno alla spalla, non oltre la sua portata. La
correzione si estende ai fotogrammi vicini e viene smussata, quindi la mano si
appoggia invece di saltare; il calcolo si ripete fino a 6 volte, finché resta
meno di 1,8 mm dentro. La rotazione della mano non cambia.

## Dita

La mocap non registra le dita. `hand_pose.py` dà una mano rilassata (dita
piegate in modo crescente dall'indice al mignolo, pollice e palmo appena
chiusi) e la apre quando la mano sale verso il petto o il braccio si allunga
lontano dal corpo (saluti, indicazioni). L'asse di piegatura di ogni dito è
calcolato dalla geometria di riposo, perpendicolare al dito e alla normale del
palmo; il passaggio fra le due pose è filtrato su 0,15 s. In corsa e scatto le
mani restano chiuse un po' di più e non si aprono. Angoli e soglie sono in cima
al file.

## Viso

La testa anime (`head`) è modellata dalle shape key MMD, non dalle ossa del viso
Daz (che non pesano su nessuna mesh visibile). In Blender 4.3 una Action
dell'armatura non può animare le shape key, quindi lo script aggiunge al rig, nella
copia, quattro proprietà su `Root` (chiavi nella Action di ogni clip) e sei driver:

| Proprietà | Shape key |
| --- | --- |
| `Viso_ciglia` | `ウィンク２`, `ｳｨﾝｸ２右` (occhi chiusi neutri), ridotti da `Viso_occhi_felici` |
| `Viso_occhi_felici` | `ウィンク`, `ウィンク右` (occhi chiusi ad arco) |
| `Viso_sorriso` | `口角上げ`, dal valore del file (0,38) a 1 |
| `Viso_bocca` | `あ` |
| `Viso_occhi_stanchi` | `Eye_Tired`, ridotto da `Viso_ciglia` |
| `Viso_sguardo_torvo` | `じと目`, ridotto da `Viso_ciglia` |
| `Viso_bocca_chiusa` | `ん`, ridotto da `Viso_bocca` |

Con le proprietà a 0 il viso è identico al file originale. Quelle nove shape key
non si muovono più a mano, ma dalle proprietà su `Root`; il loro valore originale
è salvato sul datablock delle shape key (`neliel_base:<nome>`).

Animazione: battiti di ciglia ogni 1,8–4,5 s (più uno quando la testa gira di
scatto), piccoli movimenti degli occhi (±3°/±2°) e occhi che anticipano la testa
nelle rotazioni, espressioni per clip (`EXPRESSIONS`) che seguono il gesto
(mano che si apre, o la profondità dell'inchino); gli stili emotivi (`STYLES`)
hanno la loro espressione (felice: sorriso; triste: occhi stanchi e bocca chiusa;
arrabbiata: sguardo torvo; fiera: sorriso leggero; insicura: occhi bassi), un
proprio ritmo dei battiti e, per triste e insicura, lo sguardo un po' più basso.
Le sopracciglia sono quasi sempre coperte dalla frangia, quindi non sono usate.
Sono un'interpretazione: la mocap non contiene il viso.

## Fisica dei capelli

`hair_physics.py` simula ogni osso dei capelli come una leva dalla sua testa al
fondo della ciocca che muove (le ossa MMD sono più corte della mesh, allungata
dalle shape key). Per ogni sotto-passo (4 per fotogramma):

- inerzia, con smorzamento sul moto relativo alla testa: camminare a velocità
  costante non trascina indietro i capelli, accelerazioni e giri sì;
- molla verso la forma di riposo portata dall'osso genitore;
- gravità relativa al riposo: a testa dritta resta la forma modellata,
  nell'inchino la coda cade;
- collisioni con la superficie deformata di `Body` (braccia comprese, e `head`
  per la coda): distanza dal piano tangente dei 4 vertici più vicini, mediata;
  raggio mai maggiore dello spazio a riposo. Le collisioni si controllano sul
  punto medio e sul fondo di ogni leva e su 14 vertici della mesh dei capelli per
  osso, sparsi su larghezza e lunghezza e calcolati con i pesi reali della mesh
  (ogni vertice segue due ossa vicine). Per questi vertici restano 1,2 cm dalla
  pelle, che coprono anche la fascia (circa 5 mm sopra la pelle; la fascia non è
  un ostacolo perché il suo bordo aperto rendeva la distanza discontinua).
  Un vertice che l'osso non riesce a portare fuori ruotando di meno di 0,6 rad
  viene lasciato alle ossa superiori. Un contatto sposta i capelli senza dar
  loro velocità (la coda non rimbalza via quando il braccio la colpisce), al
  massimo 0,05 rad per sotto-passo.

La simulazione si assesta per 2 s, con più smorzamento, sul primo fotogramma,
perché una clip può partire lontano dalla posa di riposo. Ogni osso della coda
non si piega oltre 65° rispetto alla sua forma di riposo: nella corsa o in una
camminata saltellante la coda non vola sopra la testa e non si ripiega, mentre
nell'inchino cade comunque, piegandosi su più ossa. Le ciocche laterali sono
rigide, escono dal corpo al massimo di 5 mm per sotto-passo, non si piegano
oltre 70°, e anche le loro ossa superiori controllano dove finisce la punta:
una ciocca che tocca il petto (testa china) si sposta tutta invece di
ripiegarsi in punta. Le rotazioni calcolate vengono infine smussate nel tempo
(gaussiana di 1 fotogramma) per togliere il tremolio dei contatti. I parametri
sono in `CHAINS` e nelle costanti in cima al file.

## Retarget

`bvh.py` e `retarget.py` vengono dalla versione senza Blender (export GLB). In
`retarget.py` è stato aggiunto il genitore logico `ThighTwist → ThighBend`: nel
rig `lThighTwist` dipende dall'osso IK `ThighBend.L.001`, quindi prima
ginocchio e tibia restavano rigidi con il bacino (fino a 9,5 cm di scarto).

Postura: bacino, schiena, collo e testa (`KEEP_REST` in `retarget.py`) tengono
la posa di riposo del personaggio al fotogramma di calibrazione e ricevono solo
il movimento successivo. Allinearli ai segmenti della mocap ruotava il bacino
indietro (7–10°), il torace in avanti (14–20°) e la testa indietro (20–35°):
seno e glutei sembravano cadere e la coda entrava nella schiena. Inoltre la
clip viene girata attorno alla verticale perché al fotogramma 0 il bacino guardi
avanti: nelle clip `feminine` l'attrice parte girata di 30–50° e prima gli arti
restavano girati rispetto al busto.

Piedi: ogni piede è calibrato in un fotogramma in cui la mocap lo ha appoggiato
(avampiede a terra e, se mai succede, anche il tallone), piatto come a riposo e
girato come il piede dell'attrice. Prima la calibrazione al fotogramma 0
copiava l'angolo di un piede sollevato (`walk_normal` parte a metà passo): un
piede restava col tallone giù, l'altro sulle punte, e il bacino saliva e
scendeva in modo asimmetrico (zoppia). Un piede che non poggia mai il tallone
(stile `feminine`) tiene l'inclinazione rispetto a un piede piatto della stessa
attrice; se nella mocap l'avampiede è a terra, il piede viene ruotato attorno
alla caviglia finché tocca il pavimento (`ball_contact`).

## Limiti noti

- Catene IK di 3 ossa con l'osso centrale corto (`Elbow`, `Knee`): gomito e
  ginocchio possono scostarsi fino a circa 2 cm.
- L'IK orienta braccio e coscia secondo il piano di piegatura: la torsione può
  differire dal retarget (fino a circa 58° sul braccio e 28° sulla coscia),
  mentre posizioni e direzioni restano entro pochi gradi.
- Dita ricostruite dalla posizione della mano, non registrate: niente pugni o
  dita che indicano; le mani giunte si compenetrano. Viso interpretato (niente
  labiale reale).
- Piedi: dove l'attrice tiene la gamba completamente tesa, o nei passi laterali e
  all'indietro, il piede non può restare fermo senza abbassare il bacino: in 15
  clip su 49 scivola ancora di 5–23 mm (peggiori `walk_proud`,
  `walk-right_feminine`, `walk_feminine_2`).
- `dash_normal` dura solo 20 fotogrammi (così nel dataset).
- `なごみ`, `はぅ`, `照れ` (rossore) mostrano una texture mancante nel render
  Workbench: non sono usate.
- Fisica dei capelli approssimata: nessuna collisione tra capelli o con i
  vestiti (la fascia è coperta solo dalla distanza dalla pelle). Misura sulla mesh
  intera dei capelli contro pelle del busto e braccia: 14 clip su 49 hanno
  ancora vertici dentro di oltre 5 mm in almeno il 10% dei fotogrammi (prima
  42), soprattutto dove una ciocca resta presa fra braccio e petto
  (`bye_not-confident` 64%, `bye_happy` 52%, `call_normal` 45%) o la mano entra
  nella coda (`bow_feminine`).
- Nell'inchino la coda cade solo in parte: la base (`Bip40`) è più rigida
  perché, rialzandosi, la coda torni dietro la schiena invece di restare sulla
  spalla.
