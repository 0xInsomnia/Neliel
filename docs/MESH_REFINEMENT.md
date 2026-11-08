# Mesh refinement 01

## Stato recuperato e integrazione

Il checkpoint `1959322` conteneva già `tools/refine_mesh.py` e
`assets/neliel-refined.glb`, ma nessuna pagina caricava questo asset.
Lo studio cel ora usa la revisione per default; `?model=original` seleziona
la base. Le due varianti usano lo stesso codice di materiali, rig e camera.
Non vengono caricati contemporaneamente due avatar sul telefono.

## Cambiamenti geometrici del checkpoint

- Occhi meno aperti verticalmente, lieve inclinazione e mandibola più larga.
- Frangia asimmetrica spostata lateralmente e sollevata da un lato.
- Coda più lunga, più larga verso le punte e con curvatura laterale.

Non è un nuovo modello da zero né una realizzazione finale del concept.
Il corpo e l'outfit restano quelli della base, con gli stessi limiti visivi.

## Verifica del 9 novembre 2026

`npm ci --ignore-scripts` e `npm test`: 15 test passati. Il validatore Khronos
controlla ora entrambi gli asset: ciascuno ha zero errori, zero warning,
2 messaggi informativi e 46 suggerimenti.

I test usano il GLTFLoader reale e verificano geometria finita, deformazione
del braccio, ossa della coda e movimento effettivo per smile/surprised/blink/wink.
Controllo aggiuntivo degli asset: nodi, skin, UV, pesi, materiali e texture
identici alla base. Questi controlli non certificano la qualità estetica.

Ricostruzione con Python e NumPy:

```sh
python3 tools/refine_mesh.py assets/neliel.glb /tmp/neliel-refined-check.glb
```

La ricostruzione in questo ambiente differisce dal checkpoint per arrotondamenti
floating point nei capelli: massimo circa 1.2e-7 sulle posizioni e 2.3e-5
sulle normali. JSON identico. Non promettere identità SHA-256 fra ambienti.
Il checkpoint originale viene conservato.

La verifica WebGL interattiva resta da completare: in questa sessione il download
del browser di test non ha restituito un archivio utilizzabile. La verifica
touch su S24 e le prestazioni mobili restano da provare.

## Ripresa

Aprire prima il confronto nello studio, verificare anche profilo e retro,
poi proseguire con modellazione di capelli e outfit. Conservare morph facciali,
pesi del rig e test della camera. Usare strumenti gratuiti e salvare passi piccoli
esclusivamente nel repository 0xInsomnia/Neliel.
