"""Idle sentado da sheet PixelLab: recorte exato e limpeza localizada de bolhas."""
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
except ImportError:
    from build_idle_trial import palette_frames
    from extract_sit_pixellab import write_apng


def cleanup(frame):
    pixels=np.asarray(frame)
    r,g,b=[pixels[:,:,i].astype('int16') for i in range(3)]
    color=((g>r+8)&(b>r+8))|((r>210)&(g>210)&(b>210))
    region=np.zeros((256,256),bool)
    # Esta região foi conferida nesta referência; fica acima dos óculos.
    # Não é um filtro global que possa apagar os acessórios azuis.
    region[:54,105:145]=True
    mask=color&region&(pixels[:,:,3]>0)
    result=pixels.copy();result[mask]=0
    assert np.array_equal(result[~mask],pixels[~mask])
    return Image.fromarray(result),mask


def checkerboard():
    image=Image.new('RGBA',(256,256),'#333333');draw=ImageDraw.Draw(image)
    for y in range(0,256,16):
        for x in range(0,256,16):
            if (x//16+y//16)%2:draw.rectangle((x,y,x+15,y+15),fill='#404040')
    return image


def save_gifs(output,prefix,frames,durations):
    # Converter ms em centésimos sem acumular erro na duração total.
    boundaries=np.rint(np.cumsum([0]+durations)/10).astype(int)*10
    timings=np.diff(boundaries).tolist()
    for name,bg,scale in [(prefix+'_transparente.gif',None,1),('previa_'+prefix+'_256.gif',checkerboard(),1),('previa_'+prefix+'_512.gif',checkerboard(),2)]:
        indexed=palette_frames(frames,bg,scale)
        extra={'transparency':0} if bg is None else {}
        indexed[0].save(output/name,save_all=True,append_images=indexed[1:],duration=timings,loop=0,disposal=2,optimize=False,**extra)
    with Image.open(output/(prefix+'_transparente.gif')) as gif:
        total=0
        for i in range(gif.n_frames):
            gif.seek(i);total+=gif.info['duration']
            assert gif.convert('RGBA').getpixel((0,0))[3]==0
        assert total==sum(durations)


def coalesce_identical(frames,durations):
    """Somar pausas contíguas iguais sem alterar pixels ou o tempo da sequência."""
    result=[];timings=[]
    for frame,duration in zip(frames,durations,strict=True):
        if result and frame.tobytes()==result[-1].tobytes():
            timings[-1]+=duration
        else:
            result.append(frame);timings.append(duration)
    return result,timings


def build(source,postures,output):
    fingerprint=hashlib.sha256(source.read_bytes()).hexdigest()
    with Image.open(source) as im:
        if im.mode!='RGBA' or im.size!=(768,768):
            raise ValueError('Esperada sheet RGBA 768x768, grade 3x3.')
        sheet=im.copy()
    output.mkdir(parents=True,exist_ok=True)
    (output/'sheet_original.png').write_bytes(source.read_bytes())
    for folder in ('originais','limpos','mascaras'):(output/folder).mkdir(exist_ok=True)
    frames,entries,originals=[],[],[]
    for index in range(9):
        x,y=index%3*256,index//3*256
        original=sheet.crop((x,y,x+256,y+256));path=output/'originais'/f'frame_{index:02d}.png'
        original.save(path)
        with Image.open(path) as decoded:assert decoded.tobytes()==original.tobytes()
        cleaned,mask=cleanup(original)
        cleaned.save(output/'limpos'/f'frame_{index:02d}.png')
        Image.fromarray(mask.astype('uint8')*255).save(output/'mascaras'/f'frame_{index:02d}.png')
        box=cleaned.getchannel('A').getbbox()
        assert box[3]==244 and min(box[:2])>0 and max(box[2:])<256
        assert set(np.unique(np.asarray(cleaned)[:,:,3]))<={0,255}
        frames.append(cleaned);originals.append(original)
        entries.append({'frame':index,'removed_artifact_pixels':int(mask.sum()),'bbox':box,'source_cell':[x,y,x+256,y+256],'clean_rgba_sha256':hashlib.sha256(cleaned.tobytes()).hexdigest()})
    durations=[875]+[125]*7+[250]
    write_apng(output/'idle_sentada_sem_perdas.png',frames,durations,0)
    write_apng(output/'original_com_bolhas.png',originals,durations,0)
    save_gifs(output,'idle_sentada',frames,durations)
    sit=[];stand=[]
    for index in range(9):
        for action,group in [('sentar',sit),('levantar',stand)]:
            with Image.open(postures/action/'alinhados'/f'frame_{index:02d}.png') as opened:group.append(opened.convert('RGBA'))
    transition_duration=[250]+[125]*7+[875]
    sequence=sit+frames+stand
    full_durations=transition_duration+durations+transition_duration
    encoded_sequence,encoded_durations=coalesce_identical(sequence,full_durations)
    write_apng(output/'sentar_idle_levantar_sem_perdas.png',encoded_sequence,encoded_durations,0)
    save_gifs(output,'sequencia_completa',sequence,full_durations)
    source_matches_sit_end=frames[0].tobytes()==sit[-1].tobytes()
    frames[0].save(output/'pose_base_idle_sentada.png')
    contact=Image.new('RGB',(768,840),'#333333');draw=ImageDraw.Draw(contact)
    for index,frame in enumerate(frames):
        cell=checkerboard();cell.alpha_composite(frame)
        x,y=index%3*256,index//3*280
        contact.paste(cell.convert('RGB'),(x,y));draw.text((x+8,y+258),f'{index:02d} | removidos: {entries[index]["removed_artifact_pixels"]}',fill='white')
    contact.save(output/'contato_9_frames_limpos.png')
    assert hashlib.sha256(source.read_bytes()).hexdigest()==fingerprint
    result={'date':datetime.now().strftime('%d/%m/%Y - %H:%M:%S'),'source':str(source),'source_sha256':fingerprint,'frame_size':[256,256],'frame_count':9,'cleanup_region':[105,0,145,54],'artifact_pixels_removed':sum(entry['removed_artifact_pixels'] for entry in entries),'frames':entries,'duration_ms':durations,'idle_duration_ms':2000,'combined_duration_ms':6000,'idle_first_frame_matches_end_of_sitting':source_matches_sit_end,'checks':{'original_crop_rgba_exact':True,'all_pixels_outside_artifact_mask_unchanged':True,'no_resize_or_warp':True,'ground_244_all_frames':True,'alpha_binary':True,'canvas_not_clipped':True,'apng_decoded_rgba_exact':True,'gif_durations_exact':True,'source_unchanged':True}}
    (output/'manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    with zipfile.ZipFile(output.with_suffix('.zip'),'w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output.rglob('*')):
            if path.is_file():archive.write(path,arcname=output.name+'/'+str(path.relative_to(output)))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True,type=Path)
    parser.add_argument('--postures',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();result=build(args.source,args.postures,args.output)
    print(json.dumps({'removed_pixels':result['artifact_pixels_removed'],'seam_matches':result['idle_first_frame_matches_end_of_sitting'],'checks':result['checks']}))
