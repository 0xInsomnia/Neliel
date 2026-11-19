# Clip Bandai Namco sul rig "Jean" (Blender)

`apply_bandai.py` applica le clip del dataset Bandai Namco Research
Motiondataset-1 al rig `Jean` del file Blender del personaggio. Crea una
**Action per clip**, con il nome della clip e il fake user. Le chiavi sono sui
**controlli** del rig; le ossa di deformazione seguono tramite i constraint e
l'IK del rig.

I BVH (licenza CC BY-NC 4.0, uso personale) e i file `.blend` non sono nel
repository.

## Uso

Mettere `apply_bandai.py`, `bvh.py`, `retarget.py` e la cartella `bvh/` accanto
al `.blend`, poi:

```sh
blender -b Neliel_rig_fasce_test_02.blend --python apply_bandai.py -- \
    --bvh-dir bvh --out Neliel_bandai_test.blend --verify
```

In alternativa: aprire il `.blend`, caricare lo script nel Text Editor e
premere *Run Script*. Il risultato va in `Neliel_bandai_test.blend`, nella
stessa cartella.

Opzioni:

- `--clips walk_normal,bow_feminine`: applica solo alcune clip.
- `--verify`: stampa lo scarto osso per osso rispetto al retarget.
- `--compress`: salva il file compresso.

Lo script non scrive mai il file aperto: rifiuta un `--out` uguale al file
sorgente. Imposta la scena a 30 fps, assegna a `Jean` la prima clip e mette il
fake user sulle Action già presenti, che altrimenti verrebbero perse al
salvataggio.

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

I pole sono messi dal lato in cui si piega l'arto nella mocap; con l'arto quasi
dritto seguono l'orientamento del segmento superiore.

## Retarget

`bvh.py` e `retarget.py` vengono dalla versione senza Blender (export GLB). In
`retarget.py` è stato aggiunto il genitore logico `ThighTwist → ThighBend`: nel
rig `lThighTwist` dipende dall'osso IK `ThighBend.L.001`, quindi prima
ginocchio e tibia restavano rigidi con il bacino (fino a 9,5 cm di scarto).

## Limiti noti

- Catene IK di 3 ossa con l'osso centrale corto (`Elbow`, `Knee`): gomito e
  ginocchio possono scostarsi fino a circa 2 cm.
- L'IK orienta braccio e coscia secondo il piano di piegatura: la torsione può
  differire molto dal retarget (fino a circa 100° sul braccio nelle clip
  `feminine`), mentre posizioni e direzioni restano entro pochi gradi.
- Dita, capelli e viso non sono animati; i piedi non sono bloccati a terra
  durante l'appoggio.
