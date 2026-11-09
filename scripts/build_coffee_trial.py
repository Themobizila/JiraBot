"""Ensaio local de café a partir de duas poses; não modifica o mascote ativo."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

try:
    from .build_idle_trial import palette_frames
except ImportError:
    from build_idle_trial import palette_frames


BOX = (48, 99, 118, 180)
# Correspondências conferidas no braço, mão, caneca e bordas fixas da região.
A = np.float32([(48,99),(83,99),(118,99),(118,140),(118,180),(83,180),(48,180),(48,140),
                (85,141),(108,141),(108,168),(86,169),(76,151),(66,158),(76,172)])
B = np.float32([(48,99),(83,99),(118,99),(118,140),(118,180),(83,180),(48,180),(48,140),
                (77,104),(100,113),(86,143),(65,135),(64,119),(54,133),(68,154)])


def triangles():
    middle = (A+B)/2
    subdiv = cv2.Subdiv2D((0, 0, 256, 256))
    for point in middle:
        subdiv.insert(tuple(map(float, point)))
    result = []
    for tri in subdiv.getTriangleList().reshape(-1, 3, 2):
        ids = np.linalg.norm(middle[None,:,:]-tri[:,None,:], axis=2).argmin(axis=1)
        if np.max(np.linalg.norm(middle[ids]-tri, axis=1)) < .1:
            result.append(ids.tolist())
    return result


TRIANGLES = triangles()


def warp(pixels, source_points, target_points):
    result = pixels.copy()
    for ids in TRIANGLES:
        out = target_points[ids]
        src = source_points[ids]
        x0,y0 = np.floor(out.min(axis=0)).astype(int)
        x1,y1 = np.ceil(out.max(axis=0)).astype(int)
        yy,xx = np.mgrid[y0:y1+1, x0:x1+1]
        grid = np.stack((xx,yy,np.ones_like(xx)),axis=-1)
        matrix = cv2.getAffineTransform(out.astype('float32'),src.astype('float32'))
        mapped = np.rint(grid @ matrix.T).astype(int)
        mask = np.zeros((y1-y0+1,x1-x0+1),np.uint8)
        cv2.fillConvexPoly(mask,np.rint(out-[x0,y0]).astype(int),1)
        good = (mask>0)&(mapped[:,:,0]>=0)&(mapped[:,:,0]<256)&(mapped[:,:,1]>=0)&(mapped[:,:,1]<256)
        result[yy[good],xx[good]]=pixels[mapped[:,:,1][good],mapped[:,:,0][good]]
    return result


def pose(first, last, amount):
    if amount <= 0:
        return first.copy()
    if amount >= 1:
        return last.copy()
    target = A*(1-amount)+B*amount
    # Uma superfície por frame: sem sobreposição translúcida das duas poses.
    source, points = (first,A) if amount < .5 else (last,B)
    changed = warp(np.asarray(source),points,target)
    pixels = np.asarray(first).copy()
    x0,y0,x1,y1=BOX
    pixels[y0:y1,x0:x1]=changed[y0:y1,x0:x1]
    return Image.fromarray(pixels)


def build(first_path,last_path,output):
    first_path,last_path,output=Path(first_path),Path(last_path),Path(output)
    hashes=[hashlib.sha256(p.read_bytes()).hexdigest() for p in (first_path,last_path)]
    first=Image.open(first_path).convert('RGBA')
    original_last=Image.open(last_path).convert('RGBA')
    if first.size!=(256,256) or original_last.size!=(256,256):
        raise ValueError('As duas poses precisam estar em 256x256.')
    output.mkdir(parents=True,exist_ok=True)
    first.save(output/'referencia_segurando.png')
    original_last.save(output/'referencia_bebendo_original.png')
    last=first.copy();last.paste(original_last.crop(BOX),BOX[:2])
    last.save(output/'pose_bebendo_estabilizada.png')
    ease=lambda t:float((1-np.cos(np.pi*t))/2)
    sequence=[0.0]*8+[ease(i/8) for i in range(1,9)]+[1.0]*6+[1-ease(i/8) for i in range(1,9)]+[0.0]*2
    frames=[]
    for index,amount in enumerate(sequence):
        frame=pose(first,last,amount)
        frame.save(output/f'frame_{index:02d}.png');frames.append(frame)
    checker=Image.new('RGBA',(256,256),'#333333');draw=ImageDraw.Draw(checker)
    for y in range(0,256,16):
        for x in range(0,256,16):
            if (x//16+y//16)%2:draw.rectangle((x,y,x+15,y+15),fill='#404040')
    durations=[120,130]*16
    for scale,name,bg in [(1,'cafe_transparente.gif',None),(1,'previa_cafe_256.gif',checker),(2,'previa_cafe_512.gif',checker)]:
        gifs=palette_frames(frames,bg,scale)
        options={'transparency':0} if bg is None else {}
        gifs[0].save(output/name,save_all=True,append_images=gifs[1:],duration=durations,loop=0,disposal=2,optimize=False,**options)
    contact=Image.new('RGB',(8*256,4*280),'#333333');draw=ImageDraw.Draw(contact)
    for index,frame in enumerate(frames):
        cell=checker.copy();cell.alpha_composite(frame)
        x,y=(index%8)*256,(index//8)*280
        contact.paste(cell.convert('RGB'),(x,y));draw.text((x+8,y+258),f'{index:02d} | {sequence[index]:.2f}',fill='white')
    contact.save(output/'contato_32_frames.png')
    outside=np.ones((256,256),bool);x0,y0,x1,y1=BOX;outside[y0:y1,x0:x1]=False
    for frame in frames:
        pixels=np.asarray(frame)
        assert np.array_equal(pixels[outside],np.asarray(first)[outside])
        assert set(np.unique(pixels[:,:,3]))<={0,255}
        bounds=frame.getchannel('A').getbbox();assert min(bounds[:2])>0 and max(bounds[2:])<256
    assert all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in zip((first_path,last_path),hashes))
    result={'date':datetime.now().strftime('%d/%m/%Y - %H:%M:%S'),'method':'local_piecewise_affine_pixel_sampling','frame_count':32,'fps':8,'duration_ms':4000,'size':[256,256],'region':BOX,'source_sha256':hashes,'positions':sequence,'checks':{'feet_fixed':True,'body_outside_arm_region_bit_exact':True,'alpha_binary':True,'canvas_not_clipped':True,'originals_unchanged':True}}
    (output/'cafe_manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--first',required=True,type=Path);parser.add_argument('--last',required=True,type=Path);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();print(json.dumps(build(args.first,args.last,args.output)['checks']))
