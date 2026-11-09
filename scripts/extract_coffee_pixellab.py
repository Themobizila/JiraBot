"""Extrai sem perdas a sheet 3x3 do PixelLab e monta uma prévia de café."""
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
except ImportError:
    from build_idle_trial import palette_frames


def build(source, output):
    source, output = Path(source), Path(output)
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    with Image.open(source) as opened:
        if opened.size != (768, 768) or opened.mode != "RGBA":
            raise ValueError("Esperada a sheet PNG RGBA 768x768, grade 3x3.")
        sheet = opened.copy()
    output.mkdir(parents=True, exist_ok=True)
    # Copiar o arquivo exato, não regravar a fonte recebida.
    (output / "sheet_original.png").write_bytes(source.read_bytes())
    frames, entries = [], []
    for index in range(9):
        x, y = index % 3 * 256, index // 3 * 256
        frame = sheet.crop((x,y,x+256,y+256))
        path = output / f"frame_{index:02d}.png"
        frame.save(path)
        with Image.open(path) as decoded:
            assert decoded.mode == "RGBA" and decoded.tobytes() == frame.tobytes()
        frames.append(frame)
        entries.append({"frame":index,"cell":[x,y,x+256,y+256],"bbox":frame.getchannel("A").getbbox(),"rgba_sha256":hashlib.sha256(frame.tobytes()).hexdigest()})
    order = list(range(9)) + list(range(7,0,-1))
    cycle = [frames[index] for index in order]
    duration = [750 if index in (0,8) else 125 for index in range(16)]
    assert sum(duration) == 3250
    cycle[0].save(output / "cafe_sem_perdas.png",save_all=True,append_images=cycle[1:],duration=duration,loop=0,disposal=0,blend=0)
    # O PNG animado preserva RGBA. O GIF é somente a alternativa de visualização.
    gif_duration = []
    timing_index = 0
    for index in range(16):
        if index in (0,8):
            gif_duration.append(750)
        else:
            gif_duration.append(120 if timing_index % 2 == 0 else 130)
            timing_index += 1
    checker = Image.new("RGBA",(256,256),"#333333")
    draw = ImageDraw.Draw(checker)
    for y in range(0,256,16):
        for x in range(0,256,16):
            if (x//16+y//16)%2:
                draw.rectangle((x,y,x+15,y+15),fill="#404040")
    for name,background,scale in [("cafe_transparente.gif",None,1),("previa_cafe_256.gif",checker,1),("previa_cafe_512.gif",checker,2)]:
        gif = palette_frames(cycle,background,scale)
        options = {"transparency":0} if background is None else {}
        gif[0].save(output/name,save_all=True,append_images=gif[1:],duration=gif_duration,loop=0,disposal=2,optimize=False,**options)
    contact = Image.new("RGB",(768,3*280),"#333333")
    draw = ImageDraw.Draw(contact)
    for index,frame in enumerate(frames):
        cell = checker.copy();cell.alpha_composite(frame)
        x,y=index%3*256,index//3*280
        contact.paste(cell.convert("RGB"),(x,y));draw.text((x+8,y+258),f"{index:02d}",fill="white")
    contact.save(output / "contato_9_frames.png")
    with Image.open(output / "cafe_sem_perdas.png") as animation:
        assert animation.n_frames == len(cycle)
        total=0
        for index,expected in enumerate(cycle):
            animation.seek(index)
            assert animation.convert("RGBA").tobytes() == expected.tobytes(), "APNG não preservou RGBA."
            total += animation.info["duration"]
        assert total == 3250
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original_hash
    result = {"date":datetime.now().strftime("%d/%m/%Y - %H:%M:%S"),"source":str(source),"source_sha256":original_hash,"sheet_size":[768,768],"grid":[3,3],"frame_size":[256,256],"source_frame_count":9,"cycle_order":order,"duration_ms":duration,"cycle_duration_ms":3250,"frames":entries,"checks":{"extracted_rgba_exact":True,"apng_decoded_rgba_exact":True,"source_unchanged":True,"no_resize_or_warp":True},"notes":"Movimento e pequenas variações do corpo são do PixelLab; a descida é a subida em ordem reversa. GIF quantiza cores; PNGs e APNG mantêm RGBA exato."}
    (output/"manifest.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    with zipfile.ZipFile(output.with_suffix(".zip"),"w",zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output.iterdir()):
            if path.is_file():
                archive.write(path,arcname=output.name+"/"+path.name)
    return result


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    args=parser.parse_args()
    print(json.dumps(build(args.source,args.output)["checks"]))
