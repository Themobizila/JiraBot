"""Extrai a caminhada PixelLab 3x3 sem alterar a arte ou o mascote ativo."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import zipfile

import numpy as np
from PIL import Image, ImageDraw, ImageOps

try:
    from .build_idle_trial import palette_frames
    from .extract_sit_pixellab import write_apng
except ImportError:
    from build_idle_trial import palette_frames
    from extract_sit_pixellab import write_apng


def build(source, output, frame_ms=200):
    if frame_ms < 20 or frame_ms % 10:
        raise ValueError('Duração deve ser múltiplo de 10 ms, a partir de 20 ms.')
    source_bytes=source.read_bytes()
    digest=hashlib.sha256(source_bytes).hexdigest()
    with Image.open(source) as image:
        if image.size != (768,768) or image.mode != 'RGBA':
            raise ValueError('Esperada sheet RGBA 768x768, grade 3x3.')
        sheet=image.copy()
    if not set(np.unique(np.asarray(sheet)[:,:,3])) <= {0,255}:
        raise ValueError('Esta exportação GIF requer alfa binário.')
    output.mkdir(parents=True,exist_ok=True)
    (output/'sheet_original.png').write_bytes(source_bytes)
    checker=Image.new('RGBA',(256,256),'#333333')
    draw=ImageDraw.Draw(checker)
    for y in range(0,256,16):
        for x in range(0,256,16):
            if (x//16+y//16)%2:
                draw.rectangle((x,y,x+15,y+15),fill='#404040')
    frames=[];metadata=[]
    for index in range(9):
        x,y=index%3*256,index//3*256
        frame=sheet.crop((x,y,x+256,y+256))
        bbox=frame.getchannel('A').getbbox()
        assert bbox and min(bbox[:2])>0 and max(bbox[2:])<256
        frames.append(frame)
        metadata.append({'index':index,'cell':[x,y,x+256,y+256],
                         'bbox':bbox,'rgba_sha256':hashlib.sha256(frame.tobytes()).hexdigest()})
    durations=[frame_ms]*9
    for direction,sequence in [('esquerda',frames),('direita',[ImageOps.mirror(f) for f in frames])]:
        directory=output/direction;directory.mkdir(exist_ok=True)
        for index,frame in enumerate(sequence):
            path=directory/f'frame_{index:02d}.png';frame.save(path)
            with Image.open(path) as saved:
                assert saved.tobytes()==frame.tobytes()
            if direction=='direita':
                assert ImageOps.mirror(frame).tobytes()==frames[index].tobytes()
        write_apng(output/f'caminhada_{direction}_sem_perdas.png',sequence,durations,0)
        for name,background,scale in [(f'caminhada_{direction}_transparente.gif',None,1),
                                      (f'previa_{direction}_256.gif',checker,1),
                                      (f'previa_{direction}_512.gif',checker,2)]:
            indexed=palette_frames(sequence,background,scale)
            options={'transparency':0} if background is None else {}
            indexed[0].save(output/name,save_all=True,append_images=indexed[1:],
                            duration=durations,loop=0,disposal=2,optimize=False,**options)
            with Image.open(output/name) as gif:
                total=0
                assert gif.n_frames==9
                for index in range(gif.n_frames):
                    gif.seek(index);total+=gif.info['duration']
                    if background is None:
                        assert gif.convert('RGBA').getpixel((0,0))[3]==0
                assert total==sum(durations)
    contact=Image.new('RGB',(768,840),'#333333');draw=ImageDraw.Draw(contact)
    for index,frame in enumerate(frames):
        cell=checker.copy();cell.alpha_composite(frame)
        x,y=index%3*256,index//3*280
        contact.paste(cell.convert('RGB'),(x,y))
        draw.text((x+8,y+258),f'{index:02d} | {frame_ms} ms',fill='white')
    contact.save(output/'contato_9_frames.png')
    # Compara mudanças de silhueta, incluindo a volta 8->0, sem reordenar o passo.
    alpha=[np.asarray(f)[:,:,3]>0 for f in frames]
    differences=[int(np.count_nonzero(alpha[i]^alpha[(i+1)%9])) for i in range(9)]
    assert hashlib.sha256(source.read_bytes()).hexdigest()==digest
    result={'date':datetime.now().strftime('%d/%m/%Y - %H:%M:%S'),
            'source':str(source),'source_sha256':digest,'frame_size':[256,256],
            'frame_count':9,'frame_order':list(range(9)),'duration_ms':durations,
            'cycle_duration_ms':sum(durations),'frames':metadata,
            'alpha_difference_to_next_including_loop':differences,
            'alignment':'original_positions_preserved',
            'checks':{'extracted_rgba_exact':True,'mirroring_reversible_exact':True,
                      'apng_decoded_rgba_exact':True,'gif_duration_exact':True,
                      'no_resize_warp_or_interpolation':True,'margins_not_clipped':True,
                      'binary_alpha':True,'source_unchanged':True}}
    (output/'manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    with zipfile.ZipFile(output.with_suffix('.zip'),'w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output.rglob('*')):
            if path.is_file():
                archive.write(path,arcname=output.name+'/'+str(path.relative_to(output)))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--frame-ms',default=200,type=int)
    args=parser.parse_args()
    print(json.dumps(build(args.source,args.output,args.frame_ms)))
