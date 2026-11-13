"""Body-only r15 -> r16b. Metres; +Y up, -Z forward.
Requires NumPy and SciPy. Keep r15 source distinct from output.
Written dimensions are design targets; section hulls estimate tape girths,
not anatomical certification. Head height excludes hair. No texture changes.
"""
from pathlib import Path
import sys,json
import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.spatial import ConvexHull
from refine_mesh import Asset,smooth
from refine_body import apply_map
from refine_physique import renew_normals

GENERATOR='Neliel body reference 16b / tools/refine_body_reference.py'
# Preserve foot placement; shorten the overlong abdomen, balance skull height.
HEIGHT_IN=np.array([-.1,0,.139,.550,.931,1.046,1.230,1.380,1.459,1.501,1.546733,1.734421,2.1])
HEIGHT_OUT=np.array([-.1,0,.139,.565,.950,1.030,1.150,1.330,1.410,1.455,1.499333,1.730,2.179])
vertical=PchipInterpolator(HEIGHT_IN,HEIGHT_OUT)
# Smooth widths/depths together: hips 109->95, waist 49->60, bust 85->94.
radial=PchipInterpolator([0,.55,.76,.86,.95,1.05,1.15,1.23,1.30,1.38,1.43,1.50,2.1],
                         [1,1,.98,.92,.872,.94,1.08,1.222,1.16,1.108,1.03,1,1])

def warp(points,head_bound):
 p=np.asarray(points,dtype=float);q=p.copy();x,y,z=p.T;ax=abs(x)
 body=(1-smooth(.18,.27,ax))*(1-smooth(1.42,1.49,y))*(~head_bound)
 k=1+(radial(y)-1)*body
 q[:,0]*=k;q[:,2]=-.015+(z+.015)*k
 q[:,1]=vertical(y)
 # Hanging hair follows head translation below the neck, rather than torso fit.
 q[:,1]=np.where(head_bound & (y<1.50),y+float(vertical(1.5752285)-1.5752285),q[:,1])
 head=smooth(1.46,1.55,y)*(1-smooth(.13,.24,ax))
 q[:,0]*=1+.10*head;q[:,2]=.007+(q[:,2]-.007)*(1+.07*head)
 # Shoulder girdle: move arms with deltoids, avoiding a stretched arm thickness.
 shoulder=smooth(1.30,1.43,y)*(1-smooth(1.47,1.53,y))*smooth(.06,.14,ax)*(~head_bound)
 q[:,0]+=.010*np.sign(x)*shoulder
 return q

def skin(asset):
 return next(p for m in asset.d['meshes'] for p in m['primitives'] if asset.d['materials'][p['material']]['name']=='Pelle e tessuto')

def section(asset,height):
 pr=skin(asset);p=asset.array(pr['attributes']['POSITION']);t=p[asset.array(pr['indices']).reshape(-1,3)];parts=[]
 for i,j in [(0,1),(1,2),(2,0)]:
  a,b=t[:,i],t[:,j];cross=(a[:,1]<height)!=(b[:,1]<height);a,b=a[cross],b[cross]
  parts.append((a+(b-a)*((height-a[:,1])/(b[:,1]-a[:,1]))[:,None])[:,[0,2]])
 q=np.concatenate(parts);q=q[abs(q[:,0])<.23];hull=ConvexHull(q)
 return {'height_m':height,'width_cm':float(np.ptp(q[:,0])*100),'depth_cm':float(np.ptp(q[:,1])*100),'hull_girth_cm':float(hull.area*100)}

def report(asset,new=False):
 return {name:section(asset,float(vertical(y)) if new else y) for name,y in [('hips',.95),('waist',1.23),('bust',1.38)]}

def build(source,target):
 if Path(source).resolve()==Path(target).resolve():raise ValueError('Preserve source')
 a=Asset(source)
 if a.d['asset'].get('generator')!='Neliel physique 15 / tools/refine_physique.py':raise ValueError('Expected r15; do not apply cumulatively')
 before=report(a);apply_map(a,warp);renew_normals(a)
 for n in a.d['nodes']:
  if 'translation' in n:n['translation']=[0 if abs(v)<1e-12 else v for v in n['translation']]
 a.d['asset']['generator']=GENERATOR;a.write(target)
 print(json.dumps({'before':before,'after':report(a,True)},indent=2))
if __name__=='__main__':build(*sys.argv[1:])
