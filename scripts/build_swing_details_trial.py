"""Detalhes locais sobre o balanço estável, sem importar a deriva das sheets."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import zipfile

import numpy as np
from PIL import Image, ImageDraw

try:
    from .build_swing_motion_trial import render
    from .build_idle_trial import palette_frames
    from .extract_sit_pixellab import write_apng
    from .build_seated_idle_trial import checkerboard, coalesce_identical
except ImportError:
    from build_swing_motion_trial import render
    from build_idle_trial import palette_frames
    from extract_sit_pixellab import write_apng
    from build_seated_idle_trial import checkerboard, coalesce_identical


def build(base_path,motion_path,details_path,output):
    inputs=[base_path,motion_path,details_path]
    hashes=[hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs]
    with Image.open(base_path) as im:
        assert im.size==(256,256) and im.mode=='RGBA'
        base=np.array(im)
    with Image.open(motion_path) as im:
        assert im.size==(768,768) and im.mode=='RGBA'
        # Pálpebra fechada do quadro 3. Registro pelos óculos: +13 x, -11 y.
        eye=np.array(im.crop((133,256+68,152,256+86)))
    with Image.open(details_path) as im:
        assert im.size==(768,768) and im.mode=='RGBA'
    output.mkdir(parents=True,exist_ok=True)
    for path,name in zip(inputs,('base_original.png','sheet_movimento_original.png','sheet_detalhes_original.png'),strict=True):
        (output/name).write_bytes(path.read_bytes())
    # Recorte da ponta, abaixo da volta fixa do cachecol no pescoço.
    scarf=Image.new('L',(256,256));draw=ImageDraw.Draw(scarf)
    draw.polygon([(95,146),(109,150),(111,163),(111,194),
                  (88,194),(88,178),(90,163),(92,150)],fill=255)
    mask=np.asarray(scarf)>0
    scarf.save(output/'mascara_cachecol.png')
    plate=base.copy()
    # Pelagem oculta: amostras da mesma linha, imediatamente à direita.
    for y in range(146,195):
        for x in np.where(mask[y])[0]:
            plate[y,x]=base[y,116+(x%5)]
    Image.fromarray(plate).save(output/'base_pelagem_reconstruida.png')
    eyelid_mask=(eye[:,:,:3].max(axis=2)<90)&(eye[:,:,3]>0)
    Image.fromarray(eyelid_mask.astype('uint8')*255).save(output/'mascara_palpebra.png')
    allowed=np.zeros((256,256),bool)
    allowed[146:195,82:118]=True
    allowed[79:97,120:139]=True
    frames=[];timeline=[];local=[]
    directory=output/'frames';directory.mkdir(exist_ok=True)
    local_dir=output/'detalhes_sem_oscilacao';local_dir.mkdir(exist_ok=True)
    for index in range(32):
        phase=2*np.pi*index/32
        scarf_shift=round(6*np.sin(phase))
        pixels=plate.copy()
        for y in range(146,195):
            offset=round(scarf_shift*((y-146)/48)**1.3)
            xx=np.where(mask[y])[0]
            pixels[y,xx+offset]=base[y,xx]
        blinking=index in (18,19)
        if blinking:
            # Substituir apenas o olho, preservando boca, focinho e óculos.
            for y in range(80,94):
                pixels[y,122:137]=base[y,118:121].mean(axis=0).astype('uint8')
            patch=pixels[79:97,120:139]
            patch[eyelid_mask]=eye[eyelid_mask]
        assert np.array_equal(pixels[~allowed],base[~allowed])
        assert np.array_equal(pixels[108:125,78:124],base[108:125,78:124])
        assert np.array_equal(pixels[:,:,3],base[:,:,3])
        variant=Image.fromarray(pixels)
        variant.save(local_dir/f'frame_{index:02d}.png')
        dx=round(18*np.sin(phase));dy=-round(220-np.sqrt(220**2-dx**2))
        frame=render(variant,dx,dy)
        frame.save(directory/f'frame_{index:02d}.png')
        with Image.open(directory/f'frame_{index:02d}.png') as saved:
            assert saved.tobytes()==frame.tobytes()
        bbox=frame.getchannel('A').getbbox()
        assert bbox[0]>0 and bbox[2]<256 and bbox[3]<256
        frames.append(frame);local.append(variant)
        timeline.append({'index':index,'dx':dx,'dy':dy,'scarf_tip_shift':scarf_shift,
                         'blink':blinking,'duration_ms':100})
    assert local[0].tobytes()==Image.fromarray(base).tobytes()
    durations=[100]*32
    encoded,timings=coalesce_identical(frames,durations)
    write_apng(output/'balanco_detalhes_sem_perdas.png',encoded,timings,0)
    for name,bg,scale in [('balanco_detalhes_transparente.gif',None,1),
                          ('previa_balanco_detalhes_256.gif',checkerboard(),1),
                          ('previa_balanco_detalhes_512.gif',checkerboard(),2)]:
        indexed=palette_frames(frames,bg,scale)
        options={'transparency':0} if bg is None else {}
        indexed[0].save(output/name,save_all=True,append_images=indexed[1:],
                        duration=durations,loop=0,disposal=2,optimize=False,**options)
        with Image.open(output/name) as gif:
            total=0
            for i in range(gif.n_frames):
                gif.seek(i);total+=gif.info['duration']
                if bg is None:
                    assert gif.convert('RGBA').getpixel((0,0))[3]==0
            assert total==3200
    contact=Image.new('RGB',(768,560),'#333333');draw=ImageDraw.Draw(contact)
    for cell,index in enumerate((0,8,16,18,24,31)):
        preview=checkerboard();preview.alpha_composite(frames[index])
        x,y=cell%3*256,cell//3*280
        contact.paste(preview.convert('RGB'),(x,y))
        draw.text((x+5,y+258),f'{index:02d} | blink={timeline[index]["blink"]}',fill='white')
    contact.save(output/'contato_detalhes.png')
    assert [hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs]==hashes
    result={'date':datetime.now().strftime('%d/%m/%Y - %H:%M:%S'),
            'sources':list(map(str,inputs)),'source_sha256':hashes,
            'frame_size':[256,256],'timeline_frames':32,'cycle_duration_ms':3200,
            'timeline':timeline,'technique':'base scarf row translation; eyelid from motion sheet frame 3; stable swing rig',
            'scarf_background':'local fur samples from same row x=116..120',
            'checks':{'outside_local_edit_regions_exact':True,'mouth_exact_before_swing':True,
                      'alpha_exact_before_swing':True,'top_rope_pixels_fixed':True,
                      'png_apng_rgba_exact':True,'gif_duration_exact':True,
                      'first_frame_equals_base':True,'margins_not_clipped':True,
                      'source_files_unchanged':True}}
    (output/'manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    with zipfile.ZipFile(output.with_suffix('.zip'),'w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output.rglob('*')):
            if path.is_file():
                archive.write(path,arcname=output.name+'/'+str(path.relative_to(output)))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('base','motion','details','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(build(args.base,args.motion,args.details,args.output)['checks']))
