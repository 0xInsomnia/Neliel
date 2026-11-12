"""Rebuild revision 15 from the tracked base; replace the output only after validation.

Requires Python/NumPy and `npm ci --ignore-scripts` (Node.js 22+).
Run from any directory: python3 tools/rebuild_refined.py
"""
import os
from pathlib import Path
import subprocess
import tempfile

from refine_mesh import refine
from refine_portrait import build as portrait
from refine_crown import build as crown
from refine_adult_face import build as adult
from refine_head_balance import build as balance
from refine_body import build as body
from refine_subdivide import build as subdivide
from refine_identity import build as identity
from refine_hair import build as hair
from refine_proportions import build as proportions
from refine_figure import build as figure
from refine_face_hair import build as face_hair
from refine_face import build as face
from refine_physique import build as physique


def main():
    root = Path(__file__).resolve().parent.parent
    # Same filesystem as the destination so os.replace is atomic.
    with tempfile.TemporaryDirectory(prefix='.rebuild-', dir=root / 'assets') as tmp:
        stages = [root / 'assets/neliel.glb'] + [Path(tmp) / f'r{i:02}.glb' for i in range(2, 16)]
        for transform, source, target in zip([refine, portrait, crown, adult, balance, body, subdivide, identity, hair, proportions, figure, face_hair, face, physique], stages, stages[1:]):
            transform(source, target)
        subprocess.run(['node', '--input-type=module', '-e', """
import fs from 'node:fs';
import validator from 'gltf-validator';
const bytes = fs.readFileSync(process.argv[1]);
if (bytes.readUInt32LE(8) !== bytes.length) throw new Error('Truncated GLB');
const report = await validator.validateBytes(new Uint8Array(bytes), { maxIssues: 0 });
if (report.issues.numErrors || report.issues.numWarnings) {
  console.error(report.issues);
  process.exit(1);
}
console.log(`Validated revision 15: ${bytes.length} bytes`);
""", str(stages[-1])], cwd=root, check=True)
        os.replace(stages[-1], root / 'assets/neliel-refined.glb')
    print('Rebuilt assets/neliel-refined.glb. Run npm test before committing.')


if __name__ == '__main__':
    main()
