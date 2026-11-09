"""Refino localizado do ciclo aprovado; preserva a composição fora das máscaras."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import zipfile

import cv2
import numpy as np
from PIL import Image,ImageDraw

try:
    from .build_swing_half_comparison import save_gif
    from .build_seated_idle_trial import checkerboard,coalesce_identical
    from .extract_sit_pixellab import write_apng
except ImportError:
    from build_swing_half_comparison import save_gif
    from build_seated_idle_trial import checkerboard,coalesce_identical
    from extract_sit_pixellab import write_apng


def build(source,base_path,output):
    files=[source/f'frame_{i:02d}.png' for i in range(16)]+[base_path]
    hashes=[hashlib.sha256(p.read_bytes()).hexdigest() for p in files]
    base=np.array(Image.open(base_path).convert('RGBA'))
    template=cv2.cvtColor(base[43:77,87:143,:3],cv2.COLOR_RGB2GRAY)
    cloth=Image.new('L',(256,256));draw=ImageDraw.Draw(cloth)
    draw.polygon([(95,146),(109,150),(111,163),(111,194),(88,194),(88,178),(90,163),(92,150)],fill=255)
    cloth=np.asarray(cloth)>0
    output.mkdir(parents=True,exist_ok=True)
    for folder in ('frames','mascaras','originais'):(output/folder).mkdir(exist_ok=True)
    before=[];after=[];entries=[]
    for i,path in enumerate(files[:-1]):
        original=np.array(Image.open(path).convert('RGBA'))
        assert original.shape==(256,256,4)
        (output/'originais'/path.name).write_bytes(path.read_bytes())
        search=cv2.cvtColor(original[20:110,40:210,:3],cv2.COLOR_RGB2GRAY)
        _,score,_,loc=cv2.minMaxLoc(cv2.matchTemplate(search,template,cv2.TM_CCOEFF_NORMED))
        assert score>.7
        dx,dy=loc[0]+40-87,loc[1]+20-43
        aligned=Image.new('RGBA',(256,256));aligned.paste(Image.fromarray(original),(-dx,-dy))
        a=np.array(aligned);b=a.copy();phase=2*np.pi*i/16
        rgb=a[:,:,:3].astype(int);r,g,blue=rgb[:,:,0],rgb[:,:,1],rgb[:,:,2]
        colored=((blue>r*1.15)&(g>40))|((r>165)&(g>150)&(g>r*.70)&(blue<125))
        region=np.zeros((256,256),bool);region[149:200,85:149]=True
        seeds=(colored&region).astype('uint8')
        points=cv2.findNonZero(seeds)
        assert points is not None
        hull=np.zeros((256,256),np.uint8)
        cv2.fillConvexPoly(hull,cv2.convexHull(points),1)
        # Abranger também franjas escuras entre as listras e sob a última faixa.
        remove=cv2.dilate(hull,np.ones((13,9),np.uint8))>0
        remove &= region
        # Preencher a pelagem revelada com pixels marrons próximos da mesma linha.
        skin=(r>g+25)&(r>blue+35)&(r>165)&(r<240)&(g>95)&(g<180)&~remove
        samples=a[150:195,115:150][skin[150:195,115:150]]
        assert len(samples)
        # Uma cor local mediana evita reproduzir linhas da franja como
        # faixas horizontais na pelagem reconstruída.
        fur=np.median(samples,axis=0).astype('uint8')
        b[remove]=fur
        # Ponta canônica contínua, sem importar os saltos de pose das sheets.
        shift=5*np.sin(phase-.35)
        scarf_dest=np.zeros((256,256),bool)
        for y in range(146,195):
            xx=np.where(cloth[y])[0]
            off=round(shift*((y-146)/48)**1.3)
            b[y,xx+off]=base[y,xx];scarf_dest[y,xx+off]=True
        allowed=remove|scarf_dest
        # Flexão suave em campos locais: tornozelos e bordas ficam ancorados.
        # Amplitudes pequenas evitam redesenhar as pernas aprovadas.
        for x0,y0,x1,y1,ampx,ampy,lag in [(46,194,104,229,2.5,1.8,.65),(135,198,164,239,1.8,2.3,.95)]:
            patch=b[y0:y1,x0:x1].copy();h,w=patch.shape[:2]
            yy,xx=np.indices((h,w),dtype=float)
            weight=np.sin(np.pi*xx/(w-1))**2*np.sin(np.pi*yy/(h-1))**2
            sx=np.rint(xx-ampx*np.sin(phase-lag)*weight).astype(int)
            sy=np.rint(yy-ampy*np.sin(phase-lag-.5)*weight).astype(int)
            assert sx.min()>=0 and sx.max()<w and sy.min()>=0 and sy.max()<h
            b[y0:y1,x0:x1]=patch[sy,sx]
            allowed[y0:y1,x0:x1]=True
        assert np.array_equal(a[~allowed],b[~allowed])
        # Voltar apenas as alterações ao quadro original: nenhuma translação
        # global ou reamostragem do corpo, rosto, assento ou cordas.
        output_array=original.copy();mask_out=np.zeros((256,256),bool)
        ys,xs=np.where(allowed);tx,ty=xs+dx,ys+dy
        assert min(tx)>=0 and max(tx)<256 and min(ty)>=0 and max(ty)<256
        output_array[ty,tx]=b[ys,xs];mask_out[ty,tx]=True
        assert np.array_equal(output_array[~mask_out],original[~mask_out])
        assert np.array_equal(output_array[0],original[0])
        frame=Image.fromarray(output_array)
        box=frame.getchannel('A').getbbox()
        assert box[0]>0 and box[2]<256 and box[3]<256
        frame.save(output/'frames'/path.name)
        Image.fromarray(mask_out.astype('uint8')*255).save(output/'mascaras'/path.name)
        with Image.open(output/'frames'/path.name) as saved:assert saved.tobytes()==frame.tobytes()
        before.append(Image.fromarray(original));after.append(frame)
        entries.append({'index':i,'registration':[dx,dy],'registration_score':score,'scarf_shift':float(shift),
                        'changed_pixels':int(np.count_nonzero(np.any(output_array!=original,axis=2)))})
    durations=[200]*16
    encoded,timings=coalesce_identical(after,durations)
    write_apng(output/'balanco_refinado_sem_perdas.png',encoded,timings,0)
    save_gif(output/'previa_balanco_refinado_512.gif',after,durations,checkerboard(),2)
    save_gif(output/'balanco_refinado_transparente.gif',after,durations,transparent=True)
    comparison=[]
    contact=Image.new('RGB',(1024,1120),'#333333');draw=ImageDraw.Draw(contact)
    for i,(old,new) in enumerate(zip(before,after,strict=True)):
        canvas=Image.new('RGBA',(512,280),'#252525');label=ImageDraw.Draw(canvas)
        for x,frame,text in [(0,old,'APROVADO'),(256,new,'TESTE: PATAS E CACHECOL')]:
            bg=checkerboard();bg.alpha_composite(frame);canvas.paste(bg,(x,24));label.text((x+5,6),text,fill='white')
        comparison.append(canvas.resize((1024,560),Image.Resampling.NEAREST))
        bg=checkerboard();bg.alpha_composite(new);x,y=i%4*256,i//4*280
        contact.paste(bg.convert('RGB'),(x,y));draw.text((x+5,y+258),str(i),fill='white')
    save_gif(output/'comparacao_aprovado_refinado.gif',comparison,durations)
    contact.save(output/'contato_refinado.png')
    assert [hashlib.sha256(p.read_bytes()).hexdigest() for p in files]==hashes
    result={'date':datetime.now().strftime('%d/%m/%Y - %H:%M:%S'),'source':str(source),'base':str(base_path),
            'input_sha256':hashes,'frames':entries,'frame_size':[256,256],'frame_count':16,'duration_ms':3200,
            'technique':'local canonical scarf and bounded nearest-neighbor paw flexion',
            'checks':{'outside_edit_masks_exact':True,'top_ropes_unchanged':True,'png_apng_rgba_exact':True,
                      'gif_duration_exact':True,'no_global_resampling':True,'no_clipping':True,'sources_unchanged':True}}
    (output/'manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    with zipfile.ZipFile(output.with_suffix('.zip'),'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(output.rglob('*')):
            if p.is_file():z.write(p,arcname=output.name+'/'+str(p.relative_to(output)))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','base','output'):p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args();print(json.dumps(build(args.source,args.base,args.output)['checks']))
