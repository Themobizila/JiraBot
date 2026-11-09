"""Clipes próprios de sentar e levantar, extraídos de duas sheets PixelLab."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import zipfile

from PIL import Image, ImageDraw

try:
    from .build_idle_trial import palette_frames
    from .extract_sit_pixellab import write_apng
except ImportError:
    from build_idle_trial import palette_frames
    from extract_sit_pixellab import write_apng


def extract(source, folder):
    fingerprint=hashlib.sha256(source.read_bytes()).hexdigest()
    with Image.open(source) as opened:
        if opened.size!=(768,768) or opened.mode!="RGBA":
            raise ValueError("Esperada sheet RGBA 768x768, grade 3x3.")
        sheet=opened.copy()
    folder.mkdir(parents=True,exist_ok=True)
    (folder/"sheet_original.png").write_bytes(source.read_bytes())
    (folder/"originais").mkdir(exist_ok=True)
    (folder/"alinhados").mkdir(exist_ok=True)
    frames,entries=[],[]
    for index in range(9):
        x,y=index%3*256,index//3*256
        frame=sheet.crop((x,y,x+256,y+256))
        original=folder/"originais"/f"frame_{index:02d}.png"
        frame.save(original)
        with Image.open(original) as decoded:assert decoded.tobytes()==frame.tobytes()
        bounds=frame.getchannel("A").getbbox()
        dy=244-bounds[3]
        aligned=Image.new("RGBA",(256,256));aligned.paste(frame,(0,dy))
        shifted=aligned.getchannel("A").getbbox()
        assert shifted==(bounds[0],bounds[1]+dy,bounds[2],244)
        assert aligned.crop(shifted).tobytes()==frame.crop(bounds).tobytes()
        assert aligned.getchannel("A").histogram()==frame.getchannel("A").histogram()
        assert min(shifted[:2])>0 and max(shifted[2:])<256
        aligned.save(folder/"alinhados"/f"frame_{index:02d}.png")
        frames.append(aligned)
        entries.append({"frame":index,"source_cell":[x,y,x+256,y+256],"source_bbox":bounds,"aligned_bbox":shifted,"vertical_offset":dy,"rgba_sha256":hashlib.sha256(frame.tobytes()).hexdigest()})
    assert hashlib.sha256(source.read_bytes()).hexdigest()==fingerprint
    return frames,{"source":str(source),"source_sha256":fingerprint,"frame_count":9,"frame_order":list(range(9)),"frames":entries}


def build(sitting,standing,output):
    output.mkdir(parents=True,exist_ok=True)
    sit,sit_info=extract(sitting,output/"sentar")
    stand,stand_info=extract(standing,output/"levantar")
    assert sit_info["source_sha256"]!=stand_info["source_sha256"]
    clip_duration=[250]+[125]*7+[875]
    write_apng(output/"sentar_sem_perdas.png",sit,clip_duration,1)
    write_apng(output/"levantar_sem_perdas.png",stand,clip_duration,1)
    cycle=sit+stand
    duration=[500]+[125]*7+[1000,250]+[125]*7+[500]
    assert len(cycle)==18 and sum(duration)==4000
    write_apng(output/"ciclo_sem_perdas.png",cycle,duration,0)
    sit[-1].save(output/"fim_sentada.png")
    stand[0].save(output/"inicio_sentada.png")
    stand[-1].save(output/"fim_em_pe.png")
    checker=Image.new("RGBA",(256,256),"#333333");draw=ImageDraw.Draw(checker)
    for y in range(0,256,16):
        for x in range(0,256,16):
            if (x//16+y//16)%2:draw.rectangle((x,y,x+15,y+15),fill="#404040")
    timings=[];middle=0
    for index in range(18):
        if index in (0,8,9,17):timings.append(duration[index])
        else:timings.append(120 if middle%2==0 else 130);middle+=1
    for name,bg,scale in [("ciclo_transparente.gif",None,1),("previa_posturas_256.gif",checker,1),("previa_posturas_512.gif",checker,2)]:
        indexed=palette_frames(cycle,bg,scale)
        extra={"transparency":0} if bg is None else {}
        indexed[0].save(output/name,save_all=True,append_images=indexed[1:],duration=timings,loop=0,disposal=2,optimize=False,**extra)
    with Image.open(output/"ciclo_transparente.gif") as gif:
        total=0
        for index in range(gif.n_frames):
            gif.seek(index);total+=gif.info["duration"]
            assert gif.convert("RGBA").getpixel((0,0))[3]==0
        assert total==4000
    contact=Image.new("RGB",(9*256,2*280),"#333333");draw=ImageDraw.Draw(contact)
    for row,(action,frames) in enumerate((("sentar",sit),("levantar",stand))):
        for index,frame in enumerate(frames):
            cell=checker.copy();cell.alpha_composite(frame)
            x,y=index*256,row*280
            contact.paste(cell.convert("RGB"),(x,y));draw.text((x+8,y+258),f"{action} {index:02d}",fill="white")
    contact.save(output/"contato_duas_sequencias.png")
    result={"date":datetime.now().strftime("%d/%m/%Y - %H:%M:%S"),"frame_size":[256,256],"alignment":"integer_vertical_translation","ground_anchor":244,"sitting":sit_info,"standing":stand_info,"cycle_order":[{"action":a,"frame":i} for a in ("sentar","levantar") for i in range(9)],"clip_duration_ms":clip_duration,"cycle_duration_ms":duration,"checks":{"two_distinct_source_sheets":True,"no_reversal_for_standing":True,"original_frames_exact_rgba":True,"translated_pixels_preserved":True,"no_resize_or_deformation":True,"alpha_preserved":True,"no_canvas_clipping":True,"apng_decoded_rgba_exact":True,"gif_duration_ms":4000}}
    (output/"manifest.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    with zipfile.ZipFile(output.with_suffix(".zip"),"w",zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output.rglob("*")):
            if path.is_file():archive.write(path,arcname=output.name+"/"+str(path.relative_to(output)))
    return result


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sitting",required=True,type=Path)
    parser.add_argument("--standing",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    args=parser.parse_args();print(json.dumps(build(args.sitting,args.standing,args.output)["checks"]))
