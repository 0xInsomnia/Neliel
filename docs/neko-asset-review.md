# Verifica tecnica del modello Neko

**Branch di prova isolato; `main` non viene modificato.**

## Asset esaminato

Archivio fornito in chat: `Neko.zip`. Progetto: `Neko/source/Neko/source/Neko.blend`, Blender 3.0 (file compresso Zstandard).

Risultati dell'ispezione del file binario:
- 6 mesh: corpo, viso, abbigliamento, capelli, occhiali, accessorio circolare;
- **46.803 vertici** e **70.674 triangoli** totali;
- **1 armatura con 85 ossa**, comprese gambe, mani, dita, occhi, orecchie e ciocche di capelli;
- **6 modificatori Armature** e gruppi di deformazione nelle mesh;
- **60 shape key sul viso** (ammiccamento, occhi, bocca e fonemi);
- 12 materiali e 11 datablock immagine; texture PNG disponibili nell'archivio;
- **0 azioni di animazione** incorporate (`bAction` non presente).

## Esito

**Base tecnica riutilizzabile per un prototipo, ma non ancora integrata nell'app.** Non è un asset originale già corrispondente alle immagini di Neliel. Vanno modificati proporzioni/viso, capelli, abbigliamento e accessori.

Problemi da risolvere:
1. Alcune texture usano percorsi esterni Windows non validi e nomi non corrispondenti a quelli dello ZIP; ricollegarle prima dell'export.
2. Alcune immagini referenziate non sono disponibili nello ZIP: verificare in Blender i materiali coinvolti.
3. Servono animazioni e prova reale delle deformazioni e delle shape key.
4. Convertire in `.glb` per l'app Web e verificare prestazioni e shader su Samsung/Android.
5. Testare visualmente l'export dentro l'app, poi regolare cel shading e compatibilita dei morph target.

## Strumenti

`tools/convert-neko-blend.py` prepara un export GLB da eseguire **dentro Blender**. La conversione non e stata eseguita in questo ambiente (Blender non installato) e il risultato va validato prima dell'integrazione.

Esempio dopo aver estratto `Neko.zip`:

```bash
blender --background path/to/Neko.blend --python tools/convert-neko-blend.py -- --textures path/to/Neko/source/Neko/textures --output build/neliel-neko-test.glb
```

Il file .blend e le texture originali sono ancora nell'allegato della chat, **non sono stati caricati su GitHub**. In questo branch sono inclusi soltanto analisi e script di conversione, per non dare l'impressione che il modello sia gia importato e funzionante.
