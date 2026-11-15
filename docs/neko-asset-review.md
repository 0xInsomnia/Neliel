# Neko nello studio 3D di Neliel

L'archivio `Neko.zip` contiene un progetto Blender 3.0 con 6 mesh, 46.803
vertici sorgente, 70.674 triangoli e un rig ValveBiped di 85 ossa. Il viso
contiene 60 shape key, compresa la base. Il file richiama Shiroko di Blue Archive
nei nomi del rig, dei materiali e nei percorsi delle immagini. La provenienza
esatta e la licenza non sono confermate dall'archivio.

## Prova locale

Estrarre l'archivio e lanciare dal repository. Export verificato con Blender 4.3.2.

```bash
blender --background --disable-autoexec /percorso/Neko/source/Neko/source/Neko.blend \
  --python-exit-code 1 --python tools/convert-neko-blend.py -- \
  --textures /percorso/Neko/source/Neko/textures \
  --output assets/neko-local.glb
npm run dev
```

Aprire [la modalità di prova](http://localhost:8080/cel-studio/?model=neko).
L'asset di prova è caricato da una copia locale. La modalità mappa le ossa,
le shape key e i materiali di Neko sui comandi dello studio. Il comando capelli è nascosto
perché l'acconciatura è una mesh unica.

## Esito

- GLB da 18.417.096 byte con 6 mesh, 85 ossa, 59 morph, 8 texture incorporate
  e zero clip. I movimenti dello studio sono procedurali.
- Il primo export segnalava sei mesh skinnate sotto il nodo dell'armatura.
  L'opzione di Blender che esporta le mesh alla radice risolve tutti e sei
  i warning. Il GLB finale ha zero errori e zero warning nel validatore Khronos.
- Le immagini `tex_Raidingsuit` e `tex_Uniform_Sub` mancano nell'archivio.
  Gli otto materiali esportati hanno tutti una texture di base incorporata.
- Con il loader di Three.js dell'app, sorriso, sorpresa e occhiolino muovono
  rispettivamente 1.220, 880 e 615 vertici del viso nella prova. Il saluto
  deforma la mesh del braccio.
- Verificato in Chromium con WebGL software. Controllati fronte, profilo e
  retro, primo piano, espressioni, saluto e caricamento della revisione 06.
- `npm test` supera i 16 test esistenti. Le prestazioni e i gesti sul
  Samsung S24 restano da misurare su dispositivo.

Neko funziona come base tecnica. Le proporzioni del viso e del corpo, le
orecchie, i capelli e il costume vanno adattati al design di Neliel. Le texture
arrivano a 4096 px e il GLB pesa circa 6,3 volte quello della revisione 06.
