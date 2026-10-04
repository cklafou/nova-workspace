# @nova: Audit visible facial defects against the approved source and identify which eye meshes deform during blinks.
import os,io,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
os.environ['NOVA_RENDER_VERSION']='v15'
import render_showcase as r
root=Path(__file__).resolve().parents[1];out=root/'preview/v16-audit';out.mkdir(exist_ok=True)
def save(im,name):
 b=io.BytesIO();im.save(b,format='PNG');p=out/name;t=p.with_name(p.name+'.tmp');t.write_bytes(b.getvalue());t.replace(p)
r.W=1100;r.H=320;r.S=4;r.ORIGIN=np.array([890.,280.]);r.cache={}
ref=Image.open(root/'preview/FRONT_source_crop.png').convert('RGBA');refCrop=ref.crop((115,140,252.5,180)).resize((1100,320),Image.Resampling.BICUBIC)
base=r.m.state();checks=[]
for opening in [1,.8,.6,.4,.2,0]:
 s=r.m.state(ParamEyeLOpen=opening,ParamEyeROpen=opening)
 for side in 'RL':
  dims={};movement={}
  for p in ['White','Iris','Rim']:
   n='FRONT_'+p+side;dims[p]=np.ptp(s[n]['xy'],axis=0).tolist();movement[p]=float(np.max(np.linalg.norm(s[n]['xy']-base[n]['xy'],axis=1)))
  checks.append({'opening':opening,'side':side,'bounds':dims,'movement':movement})
font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',22);sheet=Image.new('RGB',(1100,7*360),'#171a23')
for row,(label,im) in enumerate([('Approved frontal reference',refCrop.convert('RGB'))]+[(f'Actual v15 / eye opening {o}',Image.fromarray(r.render({'ParamEyeLOpen':o,'ParamEyeROpen':o},'')).crop((0,58,1100,378))) for o in [1,.8,.6,.4,.2,0]]):
 sheet.paste(im,(0,row*360+35));ImageDraw.Draw(sheet).text((14,row*360+3),label,font=font,fill='white')
save(sheet,'reference_and_blinks.png')
# Inspect the backing alone. No feature art is painted into this diagnostic.
i=r.names.index('FRONT_Head');rgba=r.layer(i,base['FRONT_Head']['xy']);rgb=rgba[:,:,:3]+np.array([.4,.4,.4])*(1-rgba[:,:,3:4]);save(Image.fromarray(np.uint8(np.clip(rgb[:,:,::-1]*255,0,255))),'head_backing.png')
p=out/'geometry_audit.json';t=p.with_name(p.name+'.tmp');t.write_text(json.dumps(checks,indent=2));t.replace(p)
print(json.dumps(checks,indent=2))
