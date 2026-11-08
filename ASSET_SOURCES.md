# Provenienza degli asset

## Avatar

`assets/neliel.glb` deriva dalle edizioni **beta CC0** dei modelli VRoid di pixiv:

| Sorgente | Uso | SHA-256 del VRM |
| --- | --- | --- |
| Vita | Corpo, rig, outfit e frangia | `f2bf78f28a24e2f75f5ca0b6c3b646654c394e4b03592dfaa0d0633ef0972b4d` |
| Victoria Rubin | Texture volto e iridi | `b1372131bdbf233f46320146d565f342a7e4f6f4b8f2aefb301f1a283ec07e1e` |

Copie sorgente recuperabili dal mirror `madjin/vrm-samples`, commit
`e16eb187100149a315ad92c3c9968f1d5baa6c7d`:

- https://github.com/madjin/vrm-samples/blob/e16eb187100149a315ad92c3c9968f1d5baa6c7d/vroid/beta/Vita.vrm
- https://github.com/madjin/vrm-samples/blob/e16eb187100149a315ad92c3c9968f1d5baa6c7d/vroid/beta/Victoria_Rubin.vrm

Entrambi i file incorporano `licenseName: CC0`, uso da parte di `Everyone` e
permesso commerciale. Non sostituire automaticamente queste copie con i preset
più recenti: i termini possono essere diversi. Lo script verifica gli hash esatti.

Fonti ufficiali per le edizioni beta:

- https://vroid.pixiv.help/hc/en-us/articles/360014900113
- https://vroid.pixiv.help/hc/en-us/articles/360014900233
- https://vroid.pixiv.help/hc/en-us/articles/4402614652569-Do-VRoid-Studio-s-sample-models-come-with-conditions-of-use
- CC0: https://creativecommons.org/publicdomain/zero/1.0/

Modifiche Neliel: consolidamento e normalizzazione dei pesi del rig,
conversione in glTF standard, rimozione di elementi, orecchie allungate,
palette e iridi, tatuaggio sulla texture, coda con quattro ossa, fermaglio e
selezione di morph facciali. L'asset è un adattamento, non una mesh originale
interamente modellata a mano e non un prodotto ufficiale pixiv/VRoid.

## Three.js

I tre file in `vendor/three/` sono di Three.js **r170 / 0.170.0**, licenza MIT:

- `build/three.module.min.js`
- `examples/jsm/loaders/GLTFLoader.js`
- `examples/jsm/utils/BufferGeometryUtils.js`

Sono stati modificati solo gli import dei due addon per usare percorsi relativi.
Licenza completa: [`vendor/three/LICENSE`](vendor/three/LICENSE).
Sorgente: https://github.com/mrdoob/three.js/tree/r170

## Strumenti di verifica

`gltf-validator` di Khronos Group è una dipendenza di sviluppo Apache-2.0;
non viene caricato dall'app. Versione fissata in `package-lock.json`.
