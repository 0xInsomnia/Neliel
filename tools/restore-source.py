from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1]; d=root/'source/body-study-parts';m=json.loads((d/'manifest.json').read_text()); b=b''.join((d/p).read_bytes() for p in m['parts'])
assert len(b)==m['bytes'] and hashlib.sha256(b).hexdigest()==m['sha256'],'Source checksum mismatch'
p=root/'source'/m['filename'];p.write_bytes(b);print(p)
