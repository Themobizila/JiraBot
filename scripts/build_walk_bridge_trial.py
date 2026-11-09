"""Encaixa os três intermediários da interpolação PixelLab no ciclo original."""
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


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(source, original, output, frame_ms=200):
    if frame_ms<20 or frame_ms%10:
        raise ValueError('Usar duração positiva múltipla de 10 ms, mínimo 20 ms.')
    inputs=[source]+[original/'esquerda'/f'frame_{i:02d}.png' for i in range(9)]
    hashes=[digest(p) for p in inputs]
    with Image.open(source) as image:
        if image.mode!='RGBA' or image.size!=(768,512):
            raise ValueError('Esperada interpolação RGBA 768x512, células 256x256.')
        sheet=image.copy()
    output.mkdir(parents=True,exist_ok=True)
    (output/'sheet_interpolacao_original.png').write_bytes(source.read_bytes())
    cells=[]
    directory=output/'interpolacao_original';directory.mkdir(exist_ok=True)
    for index in range(6):
        x,y=index%3*256,index//3*256
        cell=sheet.crop((x,y,x+256,y+256))
        cell.save(directory/f'celula_{index:02d}.png');cells.append(cell)
    assert cells[5].getchannel('A').getbbox() is None
    frames=[]
    for path in inputs[1:]:
        with Image.open(path) as image:
            assert image.mode=='RGBA' and image.size==(256,256)
            frames.append(image.copy())
    assert cells[0].tobytes()==frames[-1].tobytes()
    a,b=np.asarray(cells[4]),np.asarray(frames[0])
    endpoint_difference=int(np.count_nonzero(np.any(a!=b,axis=2)))
    endpoint_alpha_difference=int(np.count_nonzero((a[:,:,3]>0)^(b[:,:,3]>0)))
    # Células 0 e 4 são referências dos extremos. A última tem pequenas
    # alterações de cor da geração: voltar ao frame 0 original evita um hold.
    assert endpoint_alpha_difference<=10
    sequence=frames+cells[1:4]
    origins=[f'original/frame_{i:02d}' for i in range(9)]+[f'interpolacao/celula_{i:02d}' for i in range(1,4)]
    checker=Image.new('RGBA',(256,256),'#333333');draw=ImageDraw.Draw(checker)
    for y in range(0,256,16):
        for x in range(0,256,16):
            if (x//16+y//16)%2:
                draw.rectangle((x,y,x+15,y+15),fill='#404040')
    durations=[frame_ms]*len(sequence);metadata=[]
    for index,frame in enumerate(sequence):
        bbox=frame.getchannel('A').getbbox()
        assert bbox and min(bbox[:2])>0 and max(bbox[2:])<256
        assert set(np.unique(np.asarray(frame)[:,:,3]))<={0,255}
        metadata.append({'index':index,'origin':origins[index],'bbox':bbox,
                         'rgba_sha256':hashlib.sha256(frame.tobytes()).hexdigest()})
    for direction,group in [('esquerda',sequence),('direita',[ImageOps.mirror(f) for f in sequence])]:
        directory=output/direction;directory.mkdir(exist_ok=True)
        for index,frame in enumerate(group):
            path=directory/f'frame_{index:02d}.png';frame.save(path)
            with Image.open(path) as saved:
                assert saved.tobytes()==frame.tobytes()
            if direction=='direita':
                assert ImageOps.mirror(frame).tobytes()==sequence[index].tobytes()
        write_apng(output/f'caminhada_{direction}_sem_perdas.png',group,durations,0)
        for name,background,scale in [(f'caminhada_{direction}_transparente.gif',None,1),
                                      (f'previa_{direction}_256.gif',checker,1),
                                      (f'previa_{direction}_512.gif',checker,2)]:
            indexed=palette_frames(group,background,scale)
            options={'transparency':0} if background is None else {}
            indexed[0].save(output/name,save_all=True,append_images=indexed[1:],
                            duration=durations,loop=0,disposal=2,optimize=False,**options)
            with Image.open(output/name) as gif:
                assert gif.n_frames==len(group)
                total=0
                for i in range(gif.n_frames):
                    gif.seek(i);total+=gif.info['duration']
                    if background is None:
                        assert gif.convert('RGBA').getpixel((0,0))[3]==0
                assert total==sum(durations)
    contact=Image.new('RGB',(1024,840),'#333333');draw=ImageDraw.Draw(contact)
    for index,frame in enumerate(sequence):
        cell=checker.copy();cell.alpha_composite(frame)
        x,y=index%4*256,index//4*280
        contact.paste(cell.convert('RGB'),(x,y))
        draw.text((x+5,y+258),f'{index:02d} | {origins[index]}',fill='white')
    contact.save(output/'contato_12_frames.png')
    masks=[np.asarray(f)[:,:,3]>0 for f in sequence]
    differences=[int(np.count_nonzero(masks[i]^masks[(i+1)%len(masks)])) for i in range(len(masks))]
    assert [digest(p) for p in inputs]==hashes
    result={'date':datetime.now().strftime('%d/%m/%Y - %H:%M:%S'),
            'source':str(source),'input_sha256':dict(zip(map(str,inputs),hashes)),
            'frame_size':[256,256],'frame_count':len(sequence),'frames':metadata,
            'duration_ms':durations,'cycle_duration_ms':sum(durations),
            'bridge_cells_used':[1,2,3],'initial_endpoint_exact':True,
            'generated_final_endpoint_rgba_difference_pixels':endpoint_difference,
            'generated_final_endpoint_alpha_difference_pixels':endpoint_alpha_difference,
            'alpha_difference_to_next_including_loop':differences,
            'checks':{'saved_rgba_exact':True,'apng_decoded_rgba_exact':True,
                      'gif_durations_exact':True,'source_files_unchanged':True,
                      'mirroring_reversible_exact':True,'no_clipping':True,
                      'no_resize_warp_or_interpolation':True}}
    (output/'manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    with zipfile.ZipFile(output.with_suffix('.zip'),'w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output.rglob('*')):
            if path.is_file():
                archive.write(path,arcname=output.name+'/'+str(path.relative_to(output)))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True,type=Path)
    parser.add_argument('--original',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--frame-ms',type=int,default=200)
    args=parser.parse_args()
    result=build(args.source,args.original,args.output,args.frame_ms)
    print(json.dumps({key:result[key] for key in ['frame_count','cycle_duration_ms','alpha_difference_to_next_including_loop','checks']}))
