#!/usr/bin/env python3
"""Utility sperimentale da eseguire con Blender: ricollega le texture ed esporta un GLB."""
import argparse
from pathlib import Path
import re
import sys

import bpy


def arguments():
    cli = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--textures", required=True, help="Directory delle texture estratte da Neko.zip")
    parser.add_argument("--output", required=True, help="Percorso GLB in uscita")
    parser.add_argument("--remove-accessories", action="store_true", help="Elimina gli oggetti accessori")
    return parser.parse_args(cli)


def texture_kind(name):
    m = re.search(r"tex_([a-z]+)", name, re.IGNORECASE)
    return m.group(1).lower() if m else None


def main():
    args = arguments()
    texdir = Path(args.textures).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    if not texdir.is_dir():
        raise SystemExit("Directory texture inesistente: " + str(texdir))
    output.parent.mkdir(parents=True, exist_ok=True)

    files = [p for p in texdir.rglob("*") if p.is_file() and p.suffix.lower() in (".png", ".jpg", ".jpeg")]
    groups = {}
    for path in files:
        key = texture_kind(path.name)
        if key:
            groups.setdefault(key, []).append(path)

    repaired, missing = 0, []
    for image in bpy.data.images:
        if image.source not in ("FILE", "SEQUENCE"):
            continue
        kind = texture_kind(image.name) or texture_kind(image.filepath)
        candidates = groups.get(kind, [])
        if candidates:
            # Preferisce le texture denominate *_neko quando sono presenti.
            candidates.sort(key=lambda p: (("_neko" not in p.name.lower()), len(str(p))))
            image.filepath = str(candidates[0])
            try:
                image.reload()
                repaired += 1
            except RuntimeError:
                missing.append(image.name)
        else:
            missing.append(image.name)

    roles = ("body", "face", "fuku_swimwear", "glasses", "hair", "halo")
    for obj in list(bpy.data.objects):
        previous = obj.name.lower()
        if args.remove_accessories and any(x in previous for x in ("glasses", "halo")):
            bpy.data.objects.remove(obj, do_unlink=True)
            continue
        if obj.type == "ARMATURE":
            obj.name = "Neliel_Rig"
            obj.data.name = "Neliel_Armature"
        elif obj.type == "MESH":
            role = next((x for x in roles if x in previous), "part")
            obj.name = "Neliel_" + role
            obj.data.name = "Neliel_Mesh_" + role

    # Manteniamo i nomi delle ossa: cambiarli senza aggiornare pesi e animazioni romperebbe il rig.
    for i, material in enumerate(bpy.data.materials):
        material.name = "Neliel_Material_%02d" % i
    for i, image in enumerate(bpy.data.images):
        image.name = "Neliel_Image_%02d" % i

    mesh_count = sum(o.type == "MESH" for o in bpy.data.objects)
    rig_count = sum(o.type == "ARMATURE" for o in bpy.data.objects)
    if mesh_count == 0 or rig_count == 0:
        raise SystemExit("La scena non contiene una mesh e una armatura valide.")

    bpy.ops.export_scene.gltf(
        filepath=str(output),
        export_format="GLB",
        use_selection=False,
        export_skins=True,
        export_armature_object_remove=True,
        export_morph=True,
        export_animations=True,
    )
    print("GLB esportato:", output)
    print("Mesh:", mesh_count, "Armature:", rig_count, "Texture ricollegate:", repaired)
    if missing:
        print("ATTENZIONE: immagini non trovate/verificabili:", ", ".join(missing))
    print("Export sperimentale: controllare il risultato in un visualizzatore glTF.")


if __name__ == "__main__":
    main()
