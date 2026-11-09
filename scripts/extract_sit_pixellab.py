"""Preserva a sheet de sentar e prepara transições com alinhamento sem perdas."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import zipfile

from PIL import Image, ImageDraw

try:
    from .build_idle_trial import palette_frames
except ImportError:
    from build_idle_trial import palette_frames


def write_apng(path, frames, durations, loop):
    frames[0].save(path,save_all=True,append_images=frames[1:],duration=durations,loop=loop,disposal=0,blend=0)
    with Image.open(path) as animation:
        assert animation.n_frames == len(frames)
        duration = 0
        for index, expected in enumerate(frames):
            animation.seek(index)
            assert animation.convert("RGBA").tobytes() == expected.tobytes()
            duration += animation.info["duration"]
        assert duration == sum(durations)


def build(source, seated_source, output):
    source,seated_source,output=Path(source),Path(seated_source),Path(output)
    original_hashes=[hashlib.sha256(p.read_bytes()).hexdigest() for p in (source,seated_source)]
    with Image.open(source) as im:
        if im.mode!="RGBA" or im.size!=(768,768):
            raise ValueError("Sheet esperada: PNG RGBA 768x768, grade 3x3.")
        sheet=im.copy()
    with Image.open(seated_source) as im:
        if im.mode!="RGBA" or im.size!=(256,256):
            raise ValueError("Pose sentada esperada: PNG RGBA 256x256.")
        seated=im.copy()
    output.mkdir(parents=True,exist_ok=True)
    (output/"sheet_original.png").write_bytes(source.read_bytes())
    (output/"pose_sentada_original.png").write_bytes(seated_source.read_bytes())
    (output/"originais").mkdir(exist_ok=True)
    (output/"alinhados").mkdir(exist_ok=True)
    originals,aligned,metadata=[],[],[]
    for index in range(9):
        x,y=index%3*256,index//3*256
        frame=sheet.crop((x,y,x+256,y+256))
        original_path=output/"originais"/f"frame_{index:02d}.png"
        frame.save(original_path)
        with Image.open(original_path) as saved:
            assert saved.tobytes()==frame.tobytes()
        box=frame.getchannel("A").getbbox()
        offset=244-box[3]
        shifted=Image.new("RGBA",(256,256))
        shifted.paste(frame,(0,offset))
        moved_box=shifted.getchannel("A").getbbox()
        assert moved_box==(box[0],box[1]+offset,box[2],box[3]+offset)
        assert shifted.crop(moved_box).tobytes()==frame.crop(box).tobytes()
        assert shifted.getchannel("A").histogram()==frame.getchannel("A").histogram()
        assert min(moved_box[:2])>0 and max(moved_box[2:])<256
        shifted.save(output/"alinhados"/f"frame_{index:02d}.png")
        originals.append(frame);aligned.append(shifted)
        metadata.append({"frame":index,"cell":[x,y,x+256,y+256],"source_bbox":box,"aligned_bbox":moved_box,"vertical_offset_px":offset,"rgba_sha256":hashlib.sha256(frame.tobytes()).hexdigest()})
    end_matches=originals[-1].tobytes()==seated.tobytes()
    aligned[-1].save(output/"pose_sentada_continuidade.png")
    box=seated.getchannel("A").getbbox();static=Image.new("RGBA",(256,256))
    static.paste(seated,(0,244-box[3]));static.save(output/"pose_sentada_alinhada.png")
    order=list(range(9))+list(range(7,0,-1))
    cycle=[aligned[i] for i in order]
    duration=[750 if i==0 else 1500 if i==8 else 125 for i in range(16)]
    one_way=[250]+[125]*7+[875]
    write_apng(output/"sentar_sem_perdas.png",aligned,one_way,1)
    write_apng(output/"levantar_sem_perdas.png",list(reversed(aligned)),one_way,1)
    write_apng(output/"ciclo_sem_perdas.png",cycle,duration,0)
    write_apng(output/"ciclo_original_sem_alinhamento.png",[originals[i] for i in order],duration,0)
    checker=Image.new("RGBA",(256,256),"#333333");draw=ImageDraw.Draw(checker)
    for y in range(0,256,16):
        for x in range(0,256,16):
            if (x//16+y//16)%2:draw.rectangle((x,y,x+15,y+15),fill="#404040")
    gif_duration=[];middle=0
    for i in range(16):
        if i in (0,8):gif_duration.append(duration[i])
        else:
            gif_duration.append(120 if middle%2==0 else 130);middle+=1
    for name,bg,scale in [("ciclo_transparente.gif",None,1),("previa_sentar_256.gif",checker,1),("previa_sentar_512.gif",checker,2)]:
        gif=palette_frames(cycle,bg,scale)
        options={"transparency":0} if bg is None else {}
        gif[0].save(output/name,save_all=True,append_images=gif[1:],duration=gif_duration,loop=0,disposal=2,optimize=False,**options)
    with Image.open(output/"ciclo_transparente.gif") as gif:
        total=0
        for i in range(gif.n_frames):
            gif.seek(i);total+=gif.info["duration"]
            assert gif.convert("RGBA").getpixel((0,0))[3]==0
        assert total==4000
    contact=Image.new("RGB",(768,3*280),"#333333");draw=ImageDraw.Draw(contact)
    for index,frame in enumerate(aligned):
        cell=checker.copy();cell.alpha_composite(frame)
        x,y=index%3*256,index//3*280
        contact.paste(cell.convert("RGB"),(x,y))
        draw.text((x+8,y+258),f"{index:02d} | dy={metadata[index]['vertical_offset_px']}",fill="white")
    contact.save(output/"contato_alinhado_9_frames.png")
    assert [hashlib.sha256(p.read_bytes()).hexdigest() for p in (source,seated_source)]==original_hashes
    result={"date":datetime.now().strftime("%d/%m/%Y - %H:%M:%S"),"source":str(source),"seated_source":str(seated_source),"source_sha256":original_hashes,"frame_count":9,"frame_size":[256,256],"ground_anchor":244,"alignment":"integer_vertical_translation_only","original_last_frame_matches_static_seated_pose":end_matches,"cycle_order":order,"duration_ms":duration,"cycle_duration_ms":4000,"one_way_duration_ms":2000,"frames":metadata,"checks":{"extracted_rgba_exact":True,"translated_rgba_preserved":True,"alpha_histogram_preserved":True,"all_aligned_bases_244":True,"apng_decoded_rgba_exact":True,"gif_duration_ms":4000,"sources_unchanged":True,"no_resize_or_deformation":True}}
    (output/"manifest.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    with zipfile.ZipFile(output.with_suffix(".zip"),"w",zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output.rglob("*")):
            if path.is_file():archive.write(path,arcname=output.name+"/"+str(path.relative_to(output)))
    return result


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",required=True,type=Path)
    parser.add_argument("--seated",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    args=parser.parse_args();result=build(args.source,args.seated,args.output)
    print(json.dumps({"checks":result["checks"],"last_frame_matches_seated_pose":result["original_last_frame_matches_static_seated_pose"]}))
