"""Ensaio idle determinístico: PNG de referência, respiração e piscada.

Não modifica o catálogo nem o mascote em execução. Uso:
python scripts/build_idle_trial.py --source CAMINHO --output PASTA
"""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def blink_image(source, state):
    if state == "open":
        return source.copy()
    pixels = np.array(source)
    # Olho visível deste PNG: coordenadas conferidas na imagem ampliada.
    for y in range(79, 92):
        skin = np.median(pixels[y, 117:122, :3], axis=0).astype(np.uint8)
        pixels[y, 123:137, :3] = skin
    closed = Image.fromarray(pixels)
    draw = ImageDraw.Draw(closed)
    if state == "half":
        original = np.array(source)
        patch = np.array(closed)
        patch[85:92, 123:137] = original[85:92, 123:137]
        closed = Image.fromarray(patch)
        draw = ImageDraw.Draw(closed)
        draw.line([(124, 85), (134, 85)], fill=(37, 23, 39, 255), width=2)
    else:
        draw.line([(124, 84), (126, 86), (132, 86), (135, 83)], fill=(50, 29, 40, 255), width=2)
    return closed


def breathing_image(source, amount):
    pixels = np.array(source)
    yy, xx = np.indices(pixels.shape[:2], dtype=np.float64)
    # Cabeça/ombros/mochila sobem juntos. A deformação se dissipa antes dos pés.
    lift_weight = np.clip((226 - yy) / 76, 0, 1)
    sy = np.rint(yy + 2 * amount * lift_weight).astype(int)
    belly_weight = np.clip(1 - np.abs(yy - 185) / 40, 0, 1)
    side_weight = np.clip((178 - xx) / 24, 0, 1)
    scale = 1 + .025 * amount * belly_weight * side_weight
    sx = np.rint(124 + (xx - 124) / scale).astype(int)
    # Pés e chão ficam bit a bit iguais ao original em todos os frames.
    fixed = yy >= 226
    sy[fixed] = yy[fixed].astype(int)
    sx[fixed] = xx[fixed].astype(int)
    result = np.zeros_like(pixels)
    valid = (sy >= 0) & (sy < 256) & (sx >= 0) & (sx < 256)
    result[valid] = pixels[sy[valid], sx[valid]]
    return Image.fromarray(result)


def palette_frames(frames, background=None, scale=1):
    rendered = []
    for frame in frames:
        if background is not None:
            image = background.copy()
            image.alpha_composite(frame)
        else:
            image = frame
        if scale != 1:
            image = image.resize((256*scale, 256*scale), Image.Resampling.NEAREST)
        rendered.append(image)
    contact = Image.new("RGB", (rendered[0].width * len(rendered), rendered[0].height))
    for index, frame in enumerate(rendered):
        contact.paste(frame.convert("RGB"), (index*frame.width, 0))
    palette = contact.quantize(colors=255 if background is None else 256, method=Image.Quantize.MAXCOVERAGE)
    result = []
    for frame in rendered:
        indexed = frame.convert("RGB").quantize(palette=palette, dither=Image.Dither.NONE)
        if background is None:
            data = np.asarray(indexed).astype(np.uint16) + 1
            data[np.asarray(frame.getchannel("A")) == 0] = 0
            indexed = Image.fromarray(data.astype(np.uint8))
            indexed.putpalette([0, 0, 0] + palette.getpalette()[:765])
            indexed.info["transparency"] = 0
        result.append(indexed)
    return result


def build(source_path, output):
    source_path, output = Path(source_path), Path(output)
    original_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    source = Image.open(source_path).convert("RGBA")
    if source.size != (256, 256):
        raise ValueError("Este rig foi conferido para a referência original de 256x256.")
    # O rig é específico à identidade e à posição do olho desta referência.
    expected_eye = np.asarray(source)[79:92, 123:137]
    if not np.any((expected_eye[:, :, :3].max(axis=2) < 70) & (expected_eye[:, :, 3] > 0)):
        raise ValueError("A posição do olho não corresponde à referência conferida.")
    output.mkdir(parents=True, exist_ok=True)
    source.save(output / "referencia_original.png")
    frames, metadata = [], []
    for index in range(16):
        amount = float((1 - np.cos(2 * np.pi * index / 16)) / 2)
        eye = "half" if index in (10, 12) else "closed" if index == 11 else "open"
        frame = breathing_image(blink_image(source, eye), amount)
        frame.save(output / f"frame_{index:02d}.png")
        frames.append(frame)
        metadata.append({"frame": index, "breathing": round(amount, 4), "eye": eye, "duration_ms": 125, "bbox": frame.getchannel("A").getbbox()})
    checker = Image.new("RGBA", (256, 256), "#333333")
    draw = ImageDraw.Draw(checker)
    for y in range(0, 256, 16):
        for x in range(0, 256, 16):
            if (x//16+y//16) % 2:
                draw.rectangle((x,y,x+15,y+15), fill="#404040")
    durations = [120, 130] * 8  # GIF usa centésimos de segundo: total exato 2 s.
    transparent = palette_frames(frames)
    transparent[0].save(output / "idle_transparente.gif", save_all=True, append_images=transparent[1:], duration=durations, loop=0, transparency=0, disposal=2, optimize=False)
    for scale, name in ((1, "previa_idle_256.gif"), (2, "previa_idle_512.gif")):
        preview = palette_frames(frames, checker, scale)
        preview[0].save(output / name, save_all=True, append_images=preview[1:], duration=durations, loop=0, disposal=2, optimize=False)
    contact = Image.new("RGB", (4*256, 4*280), "#333333")
    draw = ImageDraw.Draw(contact)
    for index, frame in enumerate(frames):
        cell = checker.copy()
        cell.alpha_composite(frame)
        x, y = (index % 4)*256, (index//4)*280
        contact.paste(cell.convert("RGB"), (x,y))
        draw.text((x+8,y+258), f"{index:02d} | {metadata[index]['eye']}", fill="white")
    contact.save(output / "contato_16_frames.png")
    baseline = np.asarray(source)
    for frame in frames:
        pixels = np.asarray(frame)
        assert np.array_equal(pixels[226:], baseline[226:]), "Pés se moveram."
        assert set(np.unique(pixels[:, :, 3])) <= {0, 255}, "Alfa inválido."
        box = frame.getchannel("A").getbbox()
        assert min(box[:2]) > 0 and max(box[2:]) < 256, "Desenho cortado."
    assert np.array_equal(np.asarray(frames[0]), baseline)
    assert hashlib.sha256(source_path.read_bytes()).hexdigest() == original_hash
    with Image.open(output / "idle_transparente.gif") as gif:
        gif_duration = 0
        for index in range(gif.n_frames):
            gif.seek(index)
            gif_duration += gif.info["duration"]
        assert gif_duration == 2000
    result = {"date": datetime.now().strftime("%d/%m/%Y - %H:%M:%S"), "source": str(source_path), "source_sha256": original_hash, "method": "deterministic_pixel_rig", "size": [256,256], "frame_count": 16, "fps": 8, "duration_ms": 2000, "fixed_feet_from_y": 226, "max_upper_body_lift_px": 2, "frames": metadata, "checks": {"source_unchanged": True, "feet_bit_exact": True, "first_frame_bit_exact": True, "no_canvas_clipping": True, "alpha_binary": True, "gif_duration_ms": gif_duration}}
    (output / "idle_manifest.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = build(args.source, args.output)
    print(json.dumps(result["checks"]))
