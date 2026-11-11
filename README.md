## Revisione del modello 08 — 11 novembre 2026 (branch `nelielclaude`)

La pelle del corpo è stata infittita con un livello di suddivisione Loop
(da 7.732 a 30.928 triangoli) tramite `tools/refine_subdivide.py`: profilo più
morbido e ombre cel più pulite. Il GLB passa da 2,9 a 4,1 MB.
16 test passati, zero errori/warning glTF. Dettagli in [docs/PROGRESS.md](docs/PROGRESS.md).

## Revisione del modello 07 — 11 novembre 2026 (branch `nelielclaude`)

Proporzioni del corpo più adulte: spalle più larghe, vita più stretta, fianchi,
busto e cosce più pieni, testa al 93% e gambe più lunghe del 10%.
`tools/refine_body.py` sposta insieme mesh, morph e ossa del rig. Lo studio
non allarga più la figura dell'8% in orizzontale: il volto risulta più stretto.

Il pulsante **Outfit** dello studio ha un terzo stato, **Costume studio**: nasconde
l'outfit provvisorio e mostra un costume a due pezzi per valutare le proporzioni.
La texture `assets/body-study.png` si rigenera con `tools/build_study_texture.py`.

Verifica: 16 test passati, zero errori/warning glTF, viste fronte, profilo,
retro, primo piano, pose e saluto con lo shader toon in WebGL software.
La forma di occhi e mento, la pelle, i capelli e l'outfit sono invariati.
Dettagli: [docs/PROGRESS.md](docs/PROGRESS.md).

## Ripristino integrità revisione 06 — 9 novembre 2026

Il commit `50e3ff2` aveva pubblicato un GLB troncato a 16.384 byte:
i controlli descritti sotto non attestavano quindi la copia remota.
Il modello è stato ricostruito dagli script salvati: **2.923.312 byte**,
16 test passati e zero errori/warning glTF. Viste CPU fronte/profilo/retro
controllate; questa verifica non certifica il rendering toon o il touch reale.

Per rigenerare tutte le revisioni dalla base, validando prima di sostituire:

```sh
npm ci --ignore-scripts
python3 tools/rebuild_refined.py
npm test
```

Il caricamento nei test segnala esplicitamente una lunghezza GLB incompleta.
La ricostruzione usa file temporanei e sostituzione atomica dell'asset.

## Revisione del modello 06 — 9 novembre 2026

Ridotta la dominanza della testa rispetto alle spalle: larghezza -8,5% nella
zona superiore, profondità -5,5%, sommità abbassata fino a 20 mm. Il raccordo
al collo è graduale; la lunghezza della parte inferiore del volto è conservata.
La trasformazione interessa tutte le superfici sovrapposte e i morph facciali.

Verifica: 16 test passati, zero errori/warning glTF. Confronto CPU fronte,
profilo e retro in bind pose. **Il browser disponibile ha WebGL disabilitato:**
questa revisione non è stata verificata con rendering toon interattivo.
Restano da completare corpo, outfit, acconciatura e somiglianza del volto.

## Revisione del modello 05 — 9 novembre 2026

Primo affinamento verso le proporzioni adulte delle immagini originali:
apertura degli occhi ridotta, guance leggermente meno tonde e parte inferiore
del volto allungata fino a 6 mm. Le immagini iniziali restano il riferimento
per identità, anatomia, capelli e outfit; Genshin è un riferimento di rendering.

16 test passati; entrambi i GLB con zero errori e zero warning. Controllati
fronte prima/dopo, profilo, retro ravvicinato ed espressioni con WebGL software.
È un ritocco incrementale, non il volto definitivo: restano proporzioni della
testa, naso/bocca, orecchie, capelli, corpo e outfit da rifinire.

## Revisione del modello 04 — 9 novembre 2026

Ridotto l'arco superiore della coda: altezza massima abbassata di circa 6,3 cm
nello spazio del modello, con restringimento graduale nella parte alta.
Viso, espressioni, outfit, rig, pesi e punte inferiori sono invariati.
È una correzione della silhouette, non la conclusione del lavoro sui capelli.

Verifica: 16 test passati, entrambi i GLB con zero errori e zero warning.
Ispezionate fronte, profilo e figura intera posteriore con WebGL software.
Restano da rifinire il raccordo della coda, le sovrapposizioni e le superfici
molto uniformi; corpo e outfit sono ancora da modellare.

## Revisione del modello 03 — 9 novembre 2026

Lo [studio cel shading](https://0xinsomnia.github.io/Neliel/cel-studio/) carica
la revisione 03: parte inferiore del volto leggermente allungata, guance meno
larghe e occhi lievemente più affusolati. Quattro ciocche laterali nuove seguono
la testa; la frangia è meno larga e la radice della coda è sollevata.

Verifica: **16 test passati**, GLB con **0 errori e 0 warning**. Questa revisione
è stata anche eseguita in Chromium con WebGL software: controllati fronte,
profilo, retro ravvicinato, sorriso, sorpresa, occhiolino, posa e layout mobile.
Il controllo software non certifica prestazioni o touch su telefono reale.

Il modello resta uno studio: capelli posteriori, ciocche dipinte, attaccatura,
orecchie, outfit e proporzioni complessive richiedono ancora lavoro.

## Revisione del modello 02 — 9 novembre 2026

Lo [studio cel shading](https://0xinsomnia.github.io/Neliel/cel-studio/) carica
la revisione 02: ciglia e contorno occhi scuri, sopracciglia viola desaturate,
ciocche laterali leggermente allungate e volume superiore dei capelli ridotto.
È un passo incrementale: volto, acconciatura e outfit non sono ancora fedeli al concept.

Verifica: 15 test passati e GLB con 0 errori/0 warning. Confrontate viste frontale,
laterale e posteriore con ispezione CPU delle texture in posa di riposo.
Questo controllo non riproduce lo shader toon né certifica le animazioni;
WebGL rimane disabilitato nel browser di verifica disponibile.

## Revisione del modello 01 — 9 novembre 2026

Lo [studio cel shading](https://0xinsomnia.github.io/Neliel/cel-studio/) ora
carica `assets/neliel-refined.glb`, recuperato dal checkpoint `1959322`.
Il link **Confronta con la base 0.3** apre lo stesso studio con il modello
precedente (`?model=original`). Il confronto ricarica la pagina e ripristina
posa e camera; viene caricato un solo avatar per contenere la memoria mobile.

La revisione modifica la geometria di occhi/mandibola, frangia e coda lunga.
Non è il modello definitivo: outfit, anatomia e acconciatura restano da rifinire.
La pagina principale conserva la base 0.3.

Verifica: **15 test passati**, entrambi i GLB con **0 errori e 0 warning**.
Sono verificati anche i quattro morph facciali, rig, UV e pesi di skinning.
Dettagli e limiti: [docs/MESH_REFINEMENT.md](docs/MESH_REFINEMENT.md).

---

## Studio cel shading sperimentale

Nuovo studio separato: https://0xinsomnia.github.io/Neliel/cel-studio/

Materiali toon, viso con ramp morbida, occhi dipinti, riflessi sui capelli,
contorni opzionali e pausa animazione. **La mesh è ancora la base 0.3, non un
modello fedele definitivo.** 11 test automatici passati; verifica visiva GPU
bloccata da WebGL disabilitato nel browser della sessione.

Analisi, verifiche e limiti: [docs/CEL_STUDIO.md](docs/CEL_STUDIO.md).
La demo originale sotto rimane disponibile senza il nuovo rendering.

---

# Neliel · Character Lab 0.3

Studio 3D del personaggio Neliel, con mesh deformabile e comandi touch.

**Apri l'app:** https://0xinsomnia.github.io/Neliel/

## Stato reale

La 0.3 sostituisce il personaggio a primitive della 0.2 con un asset glTF 2.0
articolato: corpo e volto, frangia, coda lunga con quattro ossa e fermaglio.
È una base derivata da modelli VRoid beta CC0, modificata con palette nera/viola,
iridi viola, orecchie appuntite e tatuaggio geometrico nella texture della coscia.
Non è ancora una riproduzione fedele delle immagini di riferimento.

Implementato nel codice:

- Rotazione camera con trascinamento, pinch zoom e doppio tap per ripristinare.
- Zoom tramite pulsanti o rotellina; tastiera: frecce, `+`, `-`, `Home`.
- Figura intera e primo piano, tre pose, saluto e respirazione leggera.
- Quattro espressioni tramite morph target e battito delle palpebre.
- Capelli lunghi/corti e due varianti cromatiche dell'outfit (non due abiti diversi).
- Layout responsive, supporto a movimento ridotto, messaggi di errore e ricaricamento.
- Rendering sospeso quando la scheda è nascosta.

Ancora da fare:

- Rifinire viso, proporzioni, acconciatura e abito per avvicinarsi ai concept.
- Migliorare movimento e collisioni dei capelli: ora l'oscillazione è procedurale.
- Verificare visivamente deformazioni, saluto e gesti su telefono reale (S24).
- Stanza esplorabile, camminata, interazioni con oggetti, chat, voce e memoria AI.

I comandi di questa versione muovono la **camera**, non fanno camminare il personaggio.
Questo mantiene il comportamento del Character Lab 0.2.

## Verifica del rilascio

L'8 novembre 2026 sono passati:

- Khronos glTF Validator: **0 errori, 0 warning** sull'intero asset, senza troncare il report.
  Restano 2 messaggi informativi e 46 suggerimenti, relativi a oggetti inutilizzati
  e `bufferView.target` facoltativi.
- Sei test automatici sulla logica camera: drag, pinch, doppio tap, cancellazione,
  perdita della cattura, zoom limitato e tastiera, anche con proporzioni diverse.
- Due test di caricamento geometrico con il GLTFLoader dell'app: vertici deformati
  finiti, movimento del braccio che agisce sulla mesh e collegamento delle ossa dei capelli.
- Controlli dei nodi del rig, delle espressioni, dei materiali e delle texture incorporate.
- Controllo sintattico dei moduli JavaScript.
- Ricostruzione del GLB dallo script: hash SHA-256 identico al file pubblicato.

Questi test simulano gli eventi dei controlli; non sostituiscono una prova touch reale.
Il browser di verifica di questa sessione non ha potuto creare un contesto WebGL.
La resa grafica finale e le prestazioni mobili non sono quindi certificate da questi test.

## Avvio e test

È un sito statico, senza backend e senza build obbligatoria. Servire la cartella
tramite HTTP; aprire `index.html` con `file://` non è supportato dai moduli ES.

```sh
python3 -m http.server 8080
# apri http://localhost:8080

# Solo per i test (Node.js 22 o successivo):
npm ci --ignore-scripts
npm test
```

Il browser carica Three.js r170 e GLTFLoader dalla cartella `vendor/`, senza CDN.
Serve un browser con WebGL2 attivo. GitHub Pages pubblica la cartella principale
del branch `main`; non caricare `dist/`, cartelle temporanee o dipendenze di sviluppo.

## Architettura e ripresa del lavoro

| Percorso | Responsabilità |
| --- | --- |
| `assets/neliel.glb` | Mesh, rig, morph target e texture incorporati (~2,9 MB) |
| `src/avatar.js` | Caricamento, pose, espressioni e animazioni procedurali |
| `src/camera.js` | Input touch/mouse/tastiera e inquadratura |
| `src/main.js` | Scena, illuminazione, rendering e collegamento dei comandi |
| `src/lab.css` | Layout desktop/mobile |
| `tools/build_avatar.py` | Generazione riproducibile dell'asset dai due VRM sorgente |
| `tools/validate-avatar.js` | Validazione completa glTF e contratto del rig |
| `tests/camera.test.js` | Regressioni della logica dei comandi |
| `tests/avatar.test.js` | Caricamento reale di mesh e rig senza rendering |

Le animazioni sono nel codice, non clip di animazione preconfezionate nel GLB.
Per sostituire il modello, aggiornare insieme i nomi delle ossa e dei morph target
in `avatar.js` e nel validatore. Conservare i test dei controlli touch.

Per riprendere da un'altra chat: leggere questo README, eseguire `npm test`,
verificare la versione online e lavorare **solo in `0xInsomnia/Neliel`**.
Il prossimo passo è la revisione visiva su WebGL funzionante prima di ulteriori
cambiamenti di modellazione. Salvare avanzamenti piccoli su GitHub.

## Ricostruzione del modello e crediti

Vedere [ASSET_SOURCES.md](ASSET_SOURCES.md) per provenienza, versioni e licenze.
Lo script richiede Python 3, NumPy e Pillow; controlla SHA-256 e licenza dei VRM
prima di procedere.

```sh
python3 tools/build_avatar.py Vita.vrm Victoria_Rubin.vrm assets/neliel.glb
npm test
```

Le immagini di riferimento dell'utente non sono redistribuite nel repository.
