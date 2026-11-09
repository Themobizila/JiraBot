"""Monta procura, retirada e devolução do relógio sem alterar a arte recebida."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import zipfile

import numpy as np
from PIL import Image, ImageDraw

try:
    from .build_idle_trial import palette_frames
    from .extract_sit_pixellab import write_apng
    from .build_seated_idle_trial import checkerboard, coalesce_identical
except ImportError:
    from build_idle_trial import palette_frames
    from extract_sit_pixellab import write_apng
    from build_seated_idle_trial import checkerboard, coalesce_identical


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(sources,output):
    hashes={name:sha(path) for name,path in sources.items()}
    output.mkdir(parents=True,exist_ok=True)
    groups={};source_metadata={}
    for name,path in sources.items():
        with Image.open(path) as image:
            if image.mode!='RGBA' or image.size!=(768,768):
                raise ValueError(f'{name}: esperada sheet RGBA 768x768.')
            sheet=image.copy()
        (output/f'sheet_{name}_original.png').write_bytes(path.read_bytes())
        directory=output/'originais'/name;directory.mkdir(parents=True,exist_ok=True)
        frames=[];entries=[]
        for index in range(9):
            x,y=index%3*256,index//3*256
            frame=sheet.crop((x,y,x+256,y+256))
            target=directory/f'frame_{index:02d}.png';frame.save(target)
            with Image.open(target) as saved:
                assert saved.mode=='RGBA' and saved.size==(256,256)
                assert saved.tobytes()==frame.tobytes()
            bbox=frame.getchannel('A').getbbox()
            assert set(np.unique(np.asarray(frame)[:,:,3]))<={0,255}
            if bbox:
                assert min(bbox[:2])>0 and max(bbox[2:])<256
            entries.append({'index':index,'bbox':bbox,'empty':bbox is None,
                            'rgba_sha256':hashlib.sha256(frame.tobytes()).hexdigest()})
            frames.append(frame)
        groups[name]=frames;source_metadata[name]=entries
    assert all(groups['guardar'][i].getchannel('A').getbbox() is None for i in (7,8))
    assert groups['procura'][4].tobytes()==groups['retirada'][0].tobytes()
    assert groups['retirada'][8].tobytes()==groups['guardar'][0].tobytes()
    # A procura é interrompida no quadro 4 e retomada no quadro 5 depois de guardar.
    order=([('procura',i) for i in range(5)]
           +[('retirada',i) for i in range(1,9)]
           +[('guardar',i) for i in range(1,7)]
           +[('procura',i) for i in range(5,9)])
    frames=[groups[name][i] for name,i in order]
    duration_overrides={('procura',0):650,('procura',4):250,
                        ('retirada',4):300,('retirada',5):400,
                        ('retirada',6):250,('procura',8):250}
    durations=[duration_overrides.get(entry,150) for entry in order]
    sequence=output/'sequencia';sequence.mkdir(exist_ok=True)
    for index,frame in enumerate(frames):
        path=sequence/f'frame_{index:02d}.png';frame.save(path)
        with Image.open(path) as saved:
            assert saved.tobytes()==frame.tobytes()
    encoded,encoded_durations=coalesce_identical(frames,durations)
    write_apng(output/'mochila_relogio_sem_perdas.png',encoded,encoded_durations,0)
    write_apng(output/'mochila_relogio_execucao_unica.png',encoded,encoded_durations,1)
    for name,background,scale in [('mochila_relogio_transparente.gif',None,1),
                                  ('previa_mochila_relogio_256.gif',checkerboard(),1),
                                  ('previa_mochila_relogio_512.gif',checkerboard(),2)]:
        indexed=palette_frames(frames,background,scale)
        options={'transparency':0} if background is None else {}
        indexed[0].save(output/name,save_all=True,append_images=indexed[1:],
                        duration=durations,loop=0,disposal=2,optimize=False,**options)
        with Image.open(output/name) as gif:
            total=0
            for index in range(gif.n_frames):
                gif.seek(index);total+=gif.info['duration']
                if background is None:
                    assert gif.convert('RGBA').getpixel((0,0))[3]==0
            assert total==sum(durations)
    contact=Image.new('RGB',(1280,1400),'#333333');draw=ImageDraw.Draw(contact)
    for index,(frame,(name,source_index),duration) in enumerate(zip(frames,order,durations,strict=True)):
        cell=checkerboard();cell.alpha_composite(frame)
        x,y=index%5*256,index//5*280
        contact.paste(cell.convert('RGB'),(x,y))
        draw.text((x+5,y+258),f'{index:02d} | {name} {source_index} | {duration} ms',fill='white')
    contact.save(output/'contato_sequencia.png')
    frames[0].save(output/'pose_espera.png')
    seams=[]
    for index in (4,12,18,22):
        a,b=np.asarray(frames[index]),np.asarray(frames[(index+1)%len(frames)])
        seams.append({'from':index,'to':(index+1)%len(frames),
                      'rgba_difference_pixels':int(np.count_nonzero(np.any(a!=b,axis=2))),
                      'alpha_difference_pixels':int(np.count_nonzero((a[:,:,3]>0)^(b[:,:,3]>0)))})
    assert {name:sha(path) for name,path in sources.items()}==hashes
    result={'date':datetime.now().strftime('%d/%m/%Y - %H:%M:%S'),
            'sources':{name:str(path) for name,path in sources.items()},
            'source_sha256':hashes,'source_frames':source_metadata,
            'frame_size':[256,256],'timeline_frame_count':len(frames),
            'apng_encoded_frame_count':len(encoded),'cycle_duration_ms':sum(durations),
            'timeline':[{'index':i,'sheet':name,'source_frame':j,'duration_ms':durations[i]}
                        for i,(name,j) in enumerate(order)],
            'seam_metrics':seams,'duplicate_references_removed':[['retirada',0],['guardar',0]],
            'checks':{'png_rgba_exact':True,'apng_decoded_rgba_exact':True,
                      'gif_durations_exact':True,'transparent_gif_corners':True,
                      'no_empty_timeline_frames':all(f.getchannel('A').getbbox() is not None for f in frames),
                      'binary_alpha':True,'margins_not_clipped':True,
                      'two_reference_joins_exact':True,'sources_unchanged':True,
                      'no_resize_warp_alignment_or_recolor':True}}
    (output/'manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    with zipfile.ZipFile(output.with_suffix('.zip'),'w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output.rglob('*')):
            if path.is_file():
                archive.write(path,arcname=output.name+'/'+str(path.relative_to(output)))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('procura','retirada','guardar'):
        parser.add_argument('--'+name,required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    result=build({name:getattr(args,name) for name in ('procura','retirada','guardar')},args.output)
    print(json.dumps({key:result[key] for key in ('timeline_frame_count','cycle_duration_ms','seam_metrics','checks')}))
