# Neliel — cel-shading study, 8 novembre 2026

## Risultato e percorso

Lo studio sperimentale si apre in `cel-studio/`. Il prototipo 0.3 rimane alla radice,
con materiali originali. Entrambi usano lo stesso GLB; non è stato sostituito né
spacciato per una nuova mesh originale. Il commit di partenza recuperabile è
`dfd87db` (e la 0.2 è conservata nella storia Git).

## Analisi della base

- GLB glTF 2.0 di 2.864.516 byte, 5 mesh, 16 primitive, 42.116 triangoli.
- 164 nodi, 4 skin: tre fanno riferimento a 155 joint, la coda a 4 joint.
- Corpo/volto organici derivati dai VRoid beta documentati in ASSET_SOURCES.md.
- Morph smile, surprised, blink, wink; animazioni procedurali sulle ossa.
- Zero clip di animazione incorporate. Non ci sono locomozione, IK dei piedi,
  collisioni dei capelli, stanza o interazioni con oggetti.
- Il materiale `Pelle e tessuto` condivide un atlante: non permette ancora una
  separazione pulita della risposta della pelle e del tessuto.
- La base è utile per il runtime ma non soddisfa la fedeltà artistica richiesta.
  Non è stata validata una nuova mesh di qualità Genshin-like in questa sessione.

## Implementazione

`src/materials.js` applica MeshToonMaterial senza perdere mappe, alpha, morph e
skinning. Ramp dedicata e più graduale per il viso; bande più nette per abito e
capelli. Occhi, ciglia, sopracciglia e bocca mantengono la texture dipinta tramite
MeshBasicMaterial. Riflesso stilizzato sui capelli e rim light tenue sono aggiunti
tramite hook al fragment shader r170. Non è un sistema SDF di ombra facciale.

Contorni opzionali con inverted hull di 0,65 mm, colore prugna, geometria e skeleton
condivisi; esclusi viso, occhi e materiali trasparenti. Sono disattivati di default:
aumentano le draw call e devono essere verificati su GPU e nelle pose estreme.
La coda nascosta nasconde anche il suo contorno.

`src/cel-main.js` mantiene il runtime esistente con illuminazione meno intensa e
pausa dell'animazione. `src/avatar.js` accetta un preparatore materiali opzionale:
la pagina precedente continua a usare i materiali originali. Nessuna dipendenza
runtime aggiunta; Three.js r170 rimane locale. `tools/serve.mjs` rende il server di
sviluppo compatibile con gli argomenti della preview.

## Verifiche realmente eseguite

- `npm test`: 11 test passati (rig, skinning, controlli camera e materiali).
- Khronos Validator: 0 errori, 0 warning; 2 info e 46 suggerimenti già presenti.
- Preservazione texture/alpha, riuso dei materiali, scheletro dei contorni,
  visibilità della coda, punti di inserimento shader della versione inclusa.
- Sintassi dei moduli JavaScript.
- Apertura dell'anteprima nel browser: la UI e il messaggio di errore sono visibili.
  Il browser non crea WebGL (`GL_RENDERER = Disabled`, `BindToCurrentSequence failed`),
  anche sul prototipo originale. Non è un test positivo del rendering.

**Non verificati:** compilazione/link GPU degli shader, resa visiva, FPS, touch su
Android reale, artefatti dei contorni e delle ombre nelle espressioni. I test sugli
hook degli shader non sostituiscono la compilazione WebGL. Non dichiarare questa
versione un risultato artistico definitivo o una demo graficamente certificata.

## Ordine del prossimo lavoro

1. Aprire lo studio su WebGL2 funzionante, confrontare figura intera e primo piano,
   ruotare fronte/profilo/retro, provare espressioni, coda e contorni; misurare S24.
2. Modellazione autoriale del volto e UV dedicate: mandibola, occhi, palpebre,
   naso, bocca; correzione di tutti i morph insieme alla nuova topologia.
3. Acconciatura a ciocche larga/lunga fedele al concept, outfit nero/viola e
   geometria separata per pelle, tessuto e metallo. Evitare ulteriori recolor
   generici come sostituto della modellazione. Conservare il tatuaggio sulla coscia.
4. Texture dipinte e maschera facciale orientata alla luce; calibrazione toon
   sul modello definitivo, invece di tentare di correggere la forma con shader.
5. Clip idle/walk autoriali o con licenza verificata, AnimationMixer e stati con
   crossfade, contatto dei piedi, poi joystick e stanza.

Nessun nuovo asset esterno è stato aggiunto. Le immagini di riferimento non sono
redistribuite. Non è stato usato alcun asset di Genshin Impact.
