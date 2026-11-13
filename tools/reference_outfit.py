"""Embedded modelling outfit and fitted accessories for the r16 asset.
The swimsuit is painted on the body UVs; it is not a simulated garment.
"""
import numpy as np
from PIL import Image, ImageFilter
from build_study_texture import body_primitive, texel_positions, remove_garments, skin_details
from refine_identity import image_of
from refine_body import world_positions
from refine_reference import embed, tube, merge
from refine_mesh import normals
from refine_subdivide import append, FLOAT, USHORT

def accessory(a,parts,mat,body):
 p,c,t=merge(parts);base=a.array(body['attributes']['POSITION']);nj=a.array(body['attributes']['JOINTS_0']);nw=a.array(body['attributes']['WEIGHTS_0'])
 nearest=[]
 for chunk in np.array_split(p,20):nearest.extend(np.argmin(((chunk[:,None,:]-base[None,:,:])**2).sum(2),axis=1))
 nearest=np.array(nearest)
 return {'material':mat,'indices':append(a,t.reshape(-1,1),'SCALAR',USHORT,target=34963),'attributes':{
 'POSITION':append(a,p,'VEC3',FLOAT,True,34962),'NORMAL':append(a,normals(p,t),'VEC3',FLOAT,target=34962),
 'COLOR_0':append(a,c,'VEC4',FLOAT,target=34962),'JOINTS_0':append(a,nj[nearest],'VEC4',USHORT,target=34962),'WEIGHTS_0':append(a,nw[nearest],'VEC4',FLOAT,target=34962)}}

def finish(a):
 body=body_primitive(a);m=a.d['materials'][body['material']];im,pic=image_of(a,m);size=pic.width
 pos,covered=texel_positions(a,body,size);x,y,z=np.moveaxis(pos,-1,0);ax=np.abs(x)
 rgb=remove_garments(np.array(pic.convert('RGB'))).astype(float)
 _,world=world_positions(a.d['nodes']);joint={n.get('name'):world[i] for i,n in enumerate(a.d['nodes'])}
 rgb=skin_details(rgb,pos,covered,joint).astype(float)
 cupcenter=.075-.10*np.maximum(y-1.35,0)
 cupwidth=.060*(1-np.clip((y-1.305)/.135,0,1))+.009
 cups=(np.abs(ax-cupcenter)<cupwidth)&(y>1.305)&(y<1.44)&(z<-.025)
 band=(abs(y-1.31)<.004)&(ax<.17)
 straps=(abs(ax-(.060-.30*(y-1.42)))<.004)&(y>1.41)&(y<1.50)&(z<-.025)
 briefs=(y> .929+.60*ax)&(y<1.008+.54*ax)&(ax<.20)
 # The lower torso UV border is covered through the gusset.
 gusset=(ax<.033)&(y>.912)&(y<1.02)
 suit=(cups|band|straps|briefs|gusset)&covered
 grown=np.asarray(Image.fromarray(suit).filter(ImageFilter.MaxFilter(9)));suit|=grown&~covered
 edge=suit&~np.asarray(Image.fromarray(suit|~covered).filter(ImageFilter.MinFilter(5)))
 rgb[suit]=[111,37,173];rgb[edge]=[191,116,231]
 # Geometric thigh marking in object space, independent of pose.
 dx=(x+.112)/.023;dy=(y-.80)/.050;diamond=abs(dx)+abs(dy)
 tattoo=covered&(z<-.065)&(((abs(diamond-1)<.08)|(abs(diamond-.58)<.07))|((abs(dx)<.1)&(abs(dy)<.12)))
 rgb[tattoo]=[58,42,77]
 pixels=np.dstack([np.clip(rgb,0,255).astype('uint8'),np.full((size,size),255,dtype='uint8')]);embed(a,im,Image.fromarray(pixels))
 # Replace floating sleeves/panels/boots with neck and ankle/wrist bands.
 mesh=next(mesh for mesh in a.d['meshes'] if body in mesh['primitives'])
 mesh['primitives']=[body]
 dark=[.045,.012,.08];silver=[.66,.56,.73]
 neck=joint['J_Bip_C_Neck'];neckpart=tube(lambda t:[.038*np.cos(t*2*np.pi),1.480,neck[2]+.032*np.sin(t*2*np.pi)],.008,dark,depth=1,rings=65,sides=8)
 # Rotation-independent nearest-skin weighting follows the original body rig.
 wrists=[];ankles=[]
 for side in ['L','R']:
  hand=joint[f'J_Bip_{side}_Hand']
  wrists.append(tube(lambda t,h=hand:h+np.array([0,.023*np.cos(t*2*np.pi),.023*np.sin(t*2*np.pi)]),.006,dark,depth=1,rings=49,sides=8))
  foot=joint[f'J_Bip_{side}_Foot']
  ankles.append(tube(lambda t,f=foot:[f[0]+.034*np.cos(t*2*np.pi),.166,f[2]+.037*np.sin(t*2*np.pi)],.006,dark,depth=1,rings=49,sides=8))
 for name,parts in [('Pannelli',[neckpart]),('Stivali',ankles),('Dettagli',wrists)]:
  mi=next(i for i,m in enumerate(a.d['materials']) if m['name']==name)
  a.d['materials'][mi]['pbrMetallicRoughness']={'baseColorFactor':[1,1,1,1],'metallicFactor':.2,'roughnessFactor':.45}
  a.d['materials'][mi].pop('emissiveTexture',None);a.d['materials'][mi]['emissiveFactor']=[0,0,0]
  mesh['primitives'].append(accessory(a,parts,mi,body))
