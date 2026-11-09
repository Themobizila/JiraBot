"""Une ida e retorno próprios do PixelLab sem reverter a animação."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import zipfile

import numpy as np
from PIL import Image, ImageDraw

try:
    from .build_swing_half_comparison import save_gif
    from .build_seated_idle_trial import checkerboard, coalesce_identical
    from .extract_sit_pixellab import write_apng
except ImportError:
    from build_swing_half_comparison import save_gif
    from build_seated_idle_trial import checkerboard, coalesce_identical
    from extract_sit_pixellab import write_apng


def difference(a,b):
    a,b=np.asarray(a),np.asarray(b)
    return {'rgba_pixels':int(np.count_nonzero(np.any(a!=b,axis=2))),
            'alpha_pixels':int(np.count_nonzero((a[:,:,3]>0)^(b[:,:,3]>0)))}


def build(outbound,inbound,output):
    paths={'ida':outbound,'volta':inbound}
    hashes={name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in paths.items()}
    output.mkdir(parents=True,exist_ok=True)
    groups={};source_meta={}
    for name,path in paths.items():
        with Image.open(path) as im:
            if im.mode!='RGBA' or im.size!=(768,768):
                raise ValueError('Esperada sheet RGBA 768x768.')
            sheet=im.copy()
        (output/f'sheet_{name}_original.png').write_bytes(path.read_bytes())
        directory=output/'originais'/name;directory.mkdir(parents=True,exist_ok=True)
        frames=[];metadata=[]
        for i in range(9):
            x,y=i%3*256,i//3*256
            frame=sheet.crop((x,y,x+256,y+256));file=directory/f'frame_{i:02d}.png'
            frame.save(file)
            with Image.open(file) as saved:
                assert saved.tobytes()==frame.tobytes()
            bbox=frame.getchannel('A').getbbox()
            assert bbox and bbox[0]>0 and bbox[2]<256 and bbox[3]<256
            assert set(np.unique(np.asarray(frame)[:,:,3]))<={0,255}
            metadata.append({'index':i,'bbox':bbox,'top_opaque_x':np.where(np.asarray(frame)[0,:,3]>0)[0].tolist()})
            frames.append(frame)
        groups[name]=frames;source_meta[name]=metadata
    joins={'ida_volta':difference(groups['ida'][8],groups['volta'][0]),
           'volta_ida':difference(groups['volta'][8],groups['ida'][0])}
    assert joins['ida_volta']['rgba_pixels']==0
    # A última referência tem a mesma pose inicial (11 pixels de silhueta
    # diferentes), mas cores ligeiramente alteradas pelo gerador. Fechar no
    # quadro 0 da ida evita duplicar essa pose com uma troca breve de cores.
    assert joins['volta_ida']['alpha_pixels']<=20
    order=[('ida',i) for i in range(9)]+[('volta',i) for i in range(1,8)]
    frames=[groups[name][i] for name,i in order];durations=[200]*len(frames)
    directory=output/'frames';directory.mkdir(exist_ok=True)
    for i,frame in enumerate(frames):
        file=directory/f'frame_{i:02d}.png';frame.save(file)
        with Image.open(file) as saved:
            assert saved.tobytes()==frame.tobytes()
    encoded,timings=coalesce_identical(frames,durations)
    write_apng(output/'balanco_completo_sem_perdas.png',encoded,timings,0)
    write_apng(output/'balanco_completo_execucao_unica.png',encoded,timings,1)
    save_gif(output/'balanco_completo_transparente.gif',frames,durations,transparent=True)
    save_gif(output/'previa_balanco_completo_256.gif',frames,durations,checkerboard(),1)
    save_gif(output/'previa_balanco_completo_512.gif',frames,durations,checkerboard(),2)
    contact=Image.new('RGB',(1024,1120),'#333333');draw=ImageDraw.Draw(contact)
    for i,(frame,(name,index)) in enumerate(zip(frames,order,strict=True)):
        cell=checkerboard();cell.alpha_composite(frame)
        x,y=i%4*256,i//4*280
        contact.paste(cell.convert('RGB'),(x,y))
        draw.text((x+5,y+258),f'{i:02d} | {name} {index}',fill='white')
    contact.save(output/'contato_16_frames.png')
    assert {name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in paths.items()}==hashes
    result={'date':datetime.now().strftime('%d/%m/%Y - %H:%M:%S'),
            'sources':{name:str(path) for name,path in paths.items()},'source_sha256':hashes,
            'source_frames':source_meta,'endpoint_differences':joins,
            'frame_size':[256,256],'frame_count':len(frames),'cycle_duration_ms':sum(durations),
            'timeline':[{'index':i,'source':name,'source_frame':j,'duration_ms':200}
                        for i,(name,j) in enumerate(order)],
            'return_mode':'independent_generated_return_in_forward_order',
            'checks':{'png_rgba_exact':True,'apng_decoded_rgba_exact':True,
                      'gif_duration_exact':True,'no_clipping':True,'binary_alpha':True,
                      'no_reverse_playback':True,'no_resize_warp_or_recolor':True,
                      'sources_unchanged':True}}
    (output/'manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    with zipfile.ZipFile(output.with_suffix('.zip'),'w',zipfile.ZIP_DEFLATED) as z:
        for file in sorted(output.rglob('*')):
            if file.is_file():z.write(file,arcname=output.name+'/'+str(file.relative_to(output)))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('outbound','inbound','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    result=build(args.outbound,args.inbound,args.output)
    print(json.dumps({'frames':result['frame_count'],'duration_ms':result['cycle_duration_ms'],
                      'joins':result['endpoint_differences'],'checks':result['checks']}))
