"""Prévia da meia oscilação recebida e comparação sincronizada com o rig."""
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


def save_gif(path,frames,durations,background=None,scale=1,transparent=False):
    indexed=palette_frames(frames,background,scale)
    options={'transparency':0} if transparent else {}
    indexed[0].save(path,save_all=True,append_images=indexed[1:],duration=durations,
                    disposal=2,loop=0,optimize=False,**options)
    with Image.open(path) as gif:
        total=0
        for i in range(gif.n_frames):
            gif.seek(i);total+=gif.info['duration']
        assert total==sum(durations)


def build(source,original_sheet,rig,output):
    paths=[source,original_sheet]+[rig/f'frame_{i:02d}.png' for i in range(8,25,2)]
    hashes=[sha(path) for path in paths]
    with Image.open(source) as im:
        assert im.mode=='RGBA' and im.size==(768,768)
        sheet=im.copy()
    output.mkdir(parents=True,exist_ok=True)
    (output/'sheet_interpolacao_original.png').write_bytes(source.read_bytes())
    (output/'sheet_movimento_anterior_original.png').write_bytes(original_sheet.read_bytes())
    directory=output/'interpolados';directory.mkdir(exist_ok=True)
    reference=output/'rig_referencia';reference.mkdir(exist_ok=True)
    frames=[];old=[];entries=[]
    for i in range(9):
        x,y=i%3*256,i//3*256
        frame=sheet.crop((x,y,x+256,y+256));target=directory/f'frame_{i:02d}.png'
        frame.save(target)
        with Image.open(target) as saved:
            assert saved.tobytes()==frame.tobytes()
        box=frame.getchannel('A').getbbox()
        assert box and box[0]>0 and box[2]<256 and box[3]<256
        assert set(np.unique(np.asarray(frame)[:,:,3]))<={0,255}
        frames.append(frame)
        with Image.open(paths[i+2]) as im:old.append(im.convert('RGBA'))
        old[-1].save(reference/f'frame_{i:02d}.png')
        entries.append({'index':i,'source_cell':[x,y,x+256,y+256],'bbox':box,
                        'rig_frame':8+2*i,'top_opaque_x':np.where(np.asarray(frame)[0,:,3]>0)[0].tolist()})
    durations=[100]+[200]*7+[100]
    encoded,timings=coalesce_identical(frames,durations)
    write_apng(output/'meia_oscilacao_execucao_unica.png',encoded,timings,1)
    write_apng(output/'rig_meia_oscilacao_execucao_unica.png',old,durations,1)
    # O retorno abaixo é apenas conveniência de visualização, não uma nova
    # animação de inércia gerada nem uma ação final aprovada.
    order=list(range(9))+list(range(7,0,-1))
    loop=[frames[i] for i in order];loop_durations=[200]*16
    save_gif(output/'previa_interpolada_512.gif',loop,loop_durations,checkerboard(),2)
    save_gif(output/'interpolada_transparente.gif',loop,loop_durations,transparent=True)
    comparison=[]
    for i in order:
        canvas=Image.new('RGBA',(512,280),'#252525');draw=ImageDraw.Draw(canvas)
        for x,frame,label in [(0,old[i],'ANTERIOR: RIG'),(256,frames[i],'NOVA INTERPOLACAO')]:
            cell=checkerboard();cell.alpha_composite(frame)
            canvas.paste(cell,(x,24));draw.text((x+8,6),label,fill='white')
        comparison.append(canvas.resize((1024,560),Image.Resampling.NEAREST))
    save_gif(output/'comparacao_anterior_nova.gif',comparison,loop_durations)
    contact=Image.new('RGB',(768,840),'#333333');draw=ImageDraw.Draw(contact)
    for i,frame in enumerate(frames):
        cell=checkerboard();cell.alpha_composite(frame)
        x,y=i%3*256,i//3*280
        contact.paste(cell.convert('RGB'),(x,y));draw.text((x+5,y+258),f'{i:02d}',fill='white')
    contact.save(output/'contato_9_frames.png')
    assert [sha(path) for path in paths]==hashes
    result={'date':datetime.now().strftime('%d/%m/%Y - %H:%M:%S'),
            'inputs':list(map(str,paths)),'input_sha256':hashes,
            'frame_size':[256,256],'frame_count':9,'half_duration_ms':1600,
            'half_duration_by_frame':durations,'preview_order':order,
            'preview_duration_ms':3200,'preview_return':'reversed_for_review_only',
            'frames':entries,'checks':{'extracted_rgba_exact':True,'apng_decoded_rgba_exact':True,
            'gif_duration_exact':True,'no_resize_or_warp_in_animation_frames':True,
            'no_clipping':True,'binary_alpha':True,'inputs_unchanged':True}}
    (output/'manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    with zipfile.ZipFile(output.with_suffix('.zip'),'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(output.rglob('*')):
            if p.is_file():z.write(p,arcname=output.name+'/'+str(p.relative_to(output)))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source','original-sheet','rig','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(build(args.source,args.original_sheet,args.rig,args.output)['checks']))
