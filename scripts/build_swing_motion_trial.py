"""Oscilação em pixels inteiros: corpo rígido e cordas com topo fixo."""
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


# Somente trechos livres das cordas, conferidos na base indicada.
ROPES=((67,72,115),(188,193,99))


def render(base,dx,dy):
    source=np.asarray(base)
    body=source.copy()
    for x0,x1,end in ROPES:
        body[:end,x0:x1]=0
    canvas=np.zeros_like(body)
    for x0,x1,end in ROPES:
        for y in range(end+dy):
            row=round(y*end/(end+dy))
            offset=round(dx*y/(end+dy))
            canvas[y,x0+offset:x1+offset]=source[row,x0:x1]
    shifted=Image.new('RGBA',(256,256))
    shifted.paste(Image.fromarray(body),(dx,dy))
    assert shifted.getchannel('A').histogram()==Image.fromarray(body).getchannel('A').histogram()
    result=Image.fromarray(canvas)
    result.alpha_composite(shifted)
    visible=np.asarray(shifted)[:,:,3]>0
    assert np.array_equal(np.asarray(result)[visible],np.asarray(shifted)[visible])
    assert np.array_equal(np.asarray(result)[0],source[0])
    return result


def build(source,sheet_source,output):
    hashes=[hashlib.sha256(p.read_bytes()).hexdigest() for p in (source,sheet_source)]
    with Image.open(source) as image:
        assert image.mode=='RGBA' and image.size==(256,256)
        base=image.copy()
    with Image.open(sheet_source) as image:
        assert image.mode=='RGBA' and image.size==(768,768)
        sheet=image.copy()
    output.mkdir(parents=True,exist_ok=True)
    (output/'base_original.png').write_bytes(source.read_bytes())
    (output/'sheet_pixellab_original.png').write_bytes(sheet_source.read_bytes())
    originals=output/'sheet_recortada';originals.mkdir(exist_ok=True)
    source_anchors=[]
    for i in range(9):
        x,y=i%3*256,i//3*256
        frame=sheet.crop((x,y,x+256,y+256));frame.save(originals/f'frame_{i:02d}.png')
        source_anchors.append(np.where(np.asarray(frame)[0,:,3]>0)[0].tolist())
    frames=[];entries=[]
    directory=output/'frames';directory.mkdir(exist_ok=True)
    for i in range(32):
        dx=round(18*np.sin(2*np.pi*i/32))
        dy=-round(220-np.sqrt(220**2-dx**2))
        frame=render(base,dx,dy)
        bbox=frame.getchannel('A').getbbox()
        assert bbox[0]>0 and bbox[2]<256 and bbox[3]<256
        frame.save(directory/f'frame_{i:02d}.png')
        with Image.open(directory/f'frame_{i:02d}.png') as saved:
            assert saved.tobytes()==frame.tobytes()
        entries.append({'index':i,'dx':dx,'dy':dy,'duration_ms':100,'bbox':bbox})
        frames.append(frame)
    assert frames[0].tobytes()==base.tobytes()
    assert render(base,round(18*np.sin(2*np.pi)),0).tobytes()==base.tobytes()
    durations=[100]*32
    encoded,timings=coalesce_identical(frames,durations)
    write_apng(output/'balanco_sem_perdas.png',encoded,timings,0)
    for name,bg,scale in [('balanco_transparente.gif',None,1),
                           ('previa_balanco_256.gif',checkerboard(),1),
                           ('previa_balanco_512.gif',checkerboard(),2)]:
        indexed=palette_frames(frames,bg,scale)
        options={'transparency':0} if bg is None else {}
        indexed[0].save(output/name,save_all=True,append_images=indexed[1:],
                        duration=durations,loop=0,disposal=2,optimize=False,**options)
        with Image.open(output/name) as gif:
            total=0
            for index in range(gif.n_frames):
                gif.seek(index);total+=gif.info['duration']
                if bg is None:
                    assert gif.convert('RGBA').getpixel((0,0))[3]==0
            assert total==3200
    contact=Image.new('RGB',(512,560),'#333333');draw=ImageDraw.Draw(contact)
    for cell,index in enumerate((0,8,16,24)):
        frame=checkerboard();frame.alpha_composite(frames[index])
        x,y=cell%2*256,cell//2*280
        contact.paste(frame.convert('RGB'),(x,y))
        draw.text((x+5,y+258),f'{index:02d} | dx={entries[index]["dx"]}',fill='white')
    contact.save(output/'contato_centro_extremos.png')
    assert [hashlib.sha256(p.read_bytes()).hexdigest() for p in (source,sheet_source)]==hashes
    result={'date':datetime.now().strftime('%d/%m/%Y - %H:%M:%S'),
            'sources':[str(source),str(sheet_source)],'source_sha256':hashes,
            'source_sheet_top_opaque_x':source_anchors,
            'frame_size':[256,256],'timeline_frames':32,'encoded_frames':len(encoded),
            'cycle_duration_ms':3200,'amplitude_px':18,'rope_regions':ROPES,
            'frames':entries,'checks':{'body_rgba_preserved_under_integer_translation':True,
            'top_rope_pixels_fixed':True,'first_frame_matches_base_exactly':True,
            'periodic_return_exact':True,'body_alpha_histogram_preserved':True,
            'png_apng_rgba_exact':True,'gif_durations_exact':True,
            'canvas_not_clipped':True,'sources_unchanged':True}}
    (output/'manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    with zipfile.ZipFile(output.with_suffix('.zip'),'w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output.rglob('*')):
            if path.is_file():
                archive.write(path,arcname=output.name+'/'+str(path.relative_to(output)))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',type=Path,required=True)
    parser.add_argument('--sheet',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=build(args.base,args.sheet,args.output)
    print(json.dumps({'duration_ms':result['cycle_duration_ms'],'checks':result['checks']}))
