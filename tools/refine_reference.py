"""Revision 16: balanced head, loose sculpted hair and consistent skin.
Reproducible r15 -> r16 model-only stage; retains facial targets and rig.
"""
import io, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter
from refine_mesh import Asset, smooth, normals
from refine_body import apply_map, world_positions
from refine_subdivide import append, FLOAT, USHORT
from refine_identity import image_of, skin_mask
from refine_hair import compact

GENERATOR = 'Neliel reference model 16 / tools/refine_reference.py'

def balance(p, flags=None):
    q=p.copy(); x,y,z=p.T
    w=smooth(1.42,1.54,y)*(1-smooth(.12,.25,np.abs(x)))
    q[:,0]*=1+.12*w
    q[:,1]+=.26*(y-1.73)*w
    q[:,2]*=1+.10*w
    # Rounded ear tips, blended into the existing ear root.
    ear=smooth(.073,.086,np.abs(x))*(1-smooth(.098,.12,np.abs(x)))
    ear*=np.exp(-((y-1.626)/.035)**4)*smooth(-.035,-.005,z)
    q[:,0]-=np.sign(x)*.004*ear
    q[:,1]-=.005*ear*smooth(1.625,1.65,y)
    return q

def embed(a,image,picture):
    buf=io.BytesIO();picture.save(buf,format='PNG');data=buf.getvalue()
    a.b+=b'\0'*(-len(a.b)%4)
    a.d['bufferViews'].append({'buffer':0,'byteOffset':len(a.b),'byteLength':len(data)})
    a.b+=data;a.b+=b'\0'*(-len(a.b)%4)
    image['bufferView']=len(a.d['bufferViews'])-1;image['mimeType']='image/png'
    a.d['buffers'][0]['byteLength']=len(a.b)

def skin(a):
    for m in a.d['materials']:
        if m['name'] not in ('Viso','Pelle e tessuto'):continue
        image,pic=image_of(a,m);pix=np.array(pic.convert('RGBA'));rgb=pix[:,:,:3].astype(float)
        mask=skin_mask(rgb)
        if not mask.any():raise ValueError('Missing skin texels')
        median=np.median(rgb[mask],axis=0)
        tint=np.clip(rgb/median*np.array([249,201,214]),0,255)
        soft=np.asarray(Image.fromarray((mask*255).astype('uint8')).filter(ImageFilter.GaussianBlur(.7)))/255
        pix[:,:,:3]=np.rint(rgb*(1-soft[:,:,None])+tint*soft[:,:,None]).astype('uint8')
        embed(a,image,Image.fromarray(pix));m['pbrMetallicRoughness']['baseColorFactor']=[1,1,1,1]

def tube(path,width,color,depth=.30,rings=55,sides=10):
    t=np.linspace(0,1,rings);centers=np.array([path(v) for v in t]);pts=[];colors=[];tri=[]
    for i,v in enumerate(t):
        tangent=centers[min(i+1,rings-1)]-centers[max(0,i-1)]
        tangent/=np.linalg.norm(tangent)
        axis=[0,1,0] if abs(tangent[2])>.95 else [0,0,1]
        across=np.cross(tangent,axis);across/=np.linalg.norm(across)
        normal=np.cross(tangent,across)
        radius=width(v) if callable(width) else width
        for j in range(sides):
            angle=j*2*np.pi/sides
            pts.append(centers[i]+radius*(np.cos(angle)*across+depth*np.sin(angle)*normal))
            colors.append(np.r_[np.array(color)*(.86+.14*np.sin(angle)**2),1])
            if i:
                prev=(i-1)*sides;cur=i*sides;k=(j+1)%sides
                tri.extend([[prev+j,prev+k,cur+j],[prev+k,cur+k,cur+j]])
    for j in range(1,sides-1):
        tri.extend([[0,j+1,j],[(rings-1)*sides,(rings-1)*sides+j,(rings-1)*sides+j+1]])
    return np.array(pts),np.array(colors),np.array(tri)

def merge(parts):
    points=[];colors=[];tri=[];offset=0
    for p,c,t in parts:points.extend(p);colors.extend(c);tri.extend(t+offset);offset+=len(p)
    return np.array(points),np.array(colors),np.array(tri)

def primitive(a,parts,material,skin_index,head_only=False):
    p,c,tr=merge(parts);sk=a.d['skins'][skin_index];nodes=a.d['nodes']
    if head_only:
        head=next(i for i,n in enumerate(nodes) if n.get('name')=='J_Bip_C_Head')
        j=np.tile([sk['joints'].index(head),0,0,0],(len(p),1));w=np.tile([1.,0,0,0],(len(p),1))
    else:
        ids=[sk['joints'].index(next(i for i,n in enumerate(nodes) if n.get('name')==f'Ponytail_{k}')) for k in range(4)]
        blend=np.clip((1.60-p[:,1])/.62*3,0,3);lo=np.minimum(blend.astype(int),2);f=blend-lo
        j=np.zeros((len(p),4),int);w=np.zeros((len(p),4));j[:,0]=np.array(ids)[lo];j[:,1]=np.array(ids)[lo+1];w[:,0]=1-f;w[:,1]=f
    j[w < 1e-8]=0
    return {'material':material,'indices':append(a,tr.reshape(-1,1),'SCALAR',USHORT,target=34963),'attributes':{
      'POSITION':append(a,p,'VEC3',FLOAT,True,34962),'NORMAL':append(a,normals(p,tr),'VEC3',FLOAT,target=34962),
      'COLOR_0':append(a,c,'VEC4',FLOAT,target=34962),'JOINTS_0':append(a,j,'VEC4',USHORT,target=34962),'WEIGHTS_0':append(a,w,'VEC4',FLOAT,target=34962)}}

def hair(a):
    node=next(n for n in a.d['nodes'] if n.get('name')=='Coda');mesh=a.d['meshes'][node['mesh']]
    silver=[.79,.74,.86];parts=[]
    for layer in range(2):
        for k in range(13):
            s=(k-6)/6;phase=k*1.71+layer*.8
            def path(t,s=s,phase=phase,layer=layer):
                wave=np.sin(t*3.8*np.pi+phase)*np.sin(t*np.pi/2)
                x=s*(.085+.105*np.sin(t*np.pi*.65))+.018*wave
                y=1.719-.045*abs(s)-(.69-.07*abs(s)+.035*np.sin(phase))*t
                z=.050+.068*np.sin(t*np.pi*.7)+layer*.022+.014*np.cos(t*3*np.pi+phase)*t
                return [x,y,z]
            parts.append(tube(path,lambda t:.0005+.017*np.sin(np.pi*t)**.65,silver,depth=.4))
    # Paired thin interlaced accent cords, attached to the same articulated chain.
    for side in [-1,1]:
      for strand in range(3):
        def braid(t,side=side,strand=strand):
            phase=t*24*np.pi+strand*2*np.pi/3
            return [side*(.06+.065*np.sin(t*np.pi*.7))+.0035*np.cos(phase),1.720-.665*t,.074+.09*np.sin(t*np.pi*.7)+.0035*np.sin(phase)]
        parts.append(tube(braid,.0022,[.40,.018,.035] if strand==0 else [.81,.70,.78],depth=1,rings=145,sides=6))
    mesh['primitives']=[primitive(a,parts,16,node['skin'])]
    a.d['materials'][16]['pbrMetallicRoughness']={'baseColorFactor':[1,1,1,1],'metallicFactor':0,'roughnessFactor':.72}
    # Replace the floating triangular clip with two intersecting solid ribbons.
    clip=next(n for n in a.d['nodes'] if n.get('name')=='Fermaglio')
    _,world=world_positions(a.d['nodes']);head_skin=next(n['skin'] for n in a.d['nodes'] if n.get('name')=='CioccheLaterali')
    center=np.array([-.063,1.687,-.104]);bars=[]
    for sign in [-1,1]:
        bars.append(tube(lambda t,sign=sign:center+np.array([.025*(t-.5),sign*.035*(t-.5),0]),.004,[.55,.012,.026],depth=.50,rings=9,sides=8))
    # A skinned accessory must have identity object transform in scene space.
    idx=a.d['nodes'].index(clip)
    for n in a.d['nodes']:
        if idx in n.get('children',[]):n['children'].remove(idx)
    a.d['scenes'][0]['nodes'].append(idx)
    clip.pop('translation',None);clip['skin']=head_skin
    a.d['meshes'][clip['mesh']]['primitives']=[primitive(a,bars,17,head_skin,True)]
    a.d['materials'][17]['pbrMetallicRoughness']={'baseColorFactor':[1,1,1,1],'metallicFactor':.25,'roughnessFactor':.32}


def build(source,target):
    if Path(source).resolve()==Path(target).resolve():raise ValueError('Preserve input')
    a=Asset(source)
    if 'physique 15' not in a.d['asset']['generator']:raise ValueError('Expected r15')
    apply_map(a,balance);skin(a);hair(a)
    from reference_outfit import finish
    finish(a);compact(a)
    a.d['asset']['generator']=GENERATOR;a.write(target)

if __name__=='__main__':build(*sys.argv[1:])
