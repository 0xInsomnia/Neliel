"""Reproducible sculpt study, retaining original UVs, topology, rig and morphs.
Usage: python3 tools/refine_mesh.py assets/neliel.glb assets/neliel-refined.glb
Requires NumPy. The original asset is never overwritten.
"""
import json, struct, sys
from pathlib import Path
import numpy as np

def smooth(a,b,v):
 t=np.clip((v-a)/(b-a),0,1);return t*t*(3-2*t)

def sculpt(p,kind):
 q=p.copy();x,y,z=p.T;ax=np.abs(x)
 if kind=='Viso':
  eye=np.exp(-((ax-.045)/.040)**4-((y-1.527)/.047)**4)*smooth(.01,.055,-z)
  q[:,1]+=eye*(-.18*(y-1.527)+.006*(ax-.042)/.035)
  q[:,0]-=np.sign(x)*np.maximum(ax-.095,0)*.58
  jaw=np.exp(-((y-1.465)/.025)**2)*smooth(.01,.055,-z)
  q[:,0]*=1+.055*jaw
 elif kind=='Frangia':
  front=smooth(.015,.085,-z);lower=1-smooth(1.57,1.67,y)
  q[:,0]+=.016*front*lower
  q[:,1]+=.024*front*lower*smooth(-.01,.09,x)
 elif kind=='Coda a ciocche':
  t=np.clip((1.58-y)/.84,0,1)
  q[:,1]-=.24*t**1.25
  q[:,0]+=.035*np.sin(t*7.0+x*12)*t
  q[:,0]*=1+.13*t
  q[:,2]+=.025*np.sin(t*5)*t
 return q

class Asset:
 def __init__(self,path):
  b=Path(path).read_bytes();n=struct.unpack_from('<I',b,12)[0]
  self.d=json.loads(b[20:20+n]);self.b=bytearray(b[28+n:])
 def array(self,i):
  a=self.d['accessors'][i];v=self.d['bufferViews'][a['bufferView']]
  types={5126:'<f4',5123:'<u2',5121:'u1',5125:'<u4'};width={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}[a['type']]
  dt=np.dtype(types[a['componentType']])
  return np.ndarray((a['count'],width),dt,buffer=self.b,offset=v.get('byteOffset',0)+a.get('byteOffset',0),strides=(v.get('byteStride',dt.itemsize*width),dt.itemsize))
 def set(self,i,values):
  self.array(i)[:]=values;a=self.d['accessors'][i]
  if 'min'in a:a['min']=values.min(0).tolist();a['max']=values.max(0).tolist()
 def write(self,path):
  s=json.dumps(self.d,separators=(',',':')).encode();s+=b' '*(-len(s)%4)
  Path(path).write_bytes(struct.pack('<4sII',b'glTF',2,28+len(s)+len(self.b))+struct.pack('<I4s',len(s),b'JSON')+s+struct.pack('<I4s',len(self.b),b'BIN\0')+self.b)

def normals(points,triangles):
 n=np.zeros_like(points);t=points[triangles];v=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0])
 for j in range(3):np.add.at(n,triangles[:,j],v)
 length=np.linalg.norm(n,axis=1);n[length>1e-10]/=length[length>1e-10,None]
 return n

def refine(source,target):
 if Path(source).resolve()==Path(target).resolve():raise ValueError('Keep the original asset')
 a=Asset(source)
 for mesh in a.d['meshes']:
  kind=mesh['name']
  if kind not in ['Viso','Frangia','Coda a ciocche']:continue
  p=mesh['primitives'][0];pos_id=p['attributes']['POSITION'];base=a.array(pos_id).copy();result=sculpt(base,kind)
  triangles=np.concatenate([a.array(p['indices']).reshape(-1,3)for p in mesh['primitives']])
  n=normals(result,triangles);oldn=a.array(p['attributes']['NORMAL']).copy()
  unused=np.linalg.norm(n,axis=1)<.1;n[unused]=oldn[unused]
  for t in p.get('targets',[]):
   posed=sculpt(base+a.array(t['POSITION']).copy(),kind)
   a.set(t['POSITION'],posed-result)
   if 'NORMAL'in t:
    nn=normals(posed,triangles);nn[unused]=n[unused];a.set(t['NORMAL'],nn-n)
  a.set(pos_id,result);a.set(p['attributes']['NORMAL'],n)
 a.d['asset']['generator']='Neliel mesh study 01 / tools/refine_mesh.py'
 a.write(target)

if __name__=='__main__':refine(*sys.argv[1:])
