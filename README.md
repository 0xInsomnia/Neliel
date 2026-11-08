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
