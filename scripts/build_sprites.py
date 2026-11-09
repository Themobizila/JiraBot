"""Extrai sheets verdes 12x8: seis ações de 16 frames, sem erosão do desenho.

Uso: python scripts/build_sprites.py --input assets/raw_sheets
Dependências de preparação: Pillow, numpy, opencv-python.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
THEMES = ("normal", "halloween", "natal", "ano_novo", "pascoa")
ACTIONS = ("idle", "walk", "drink", "sit", "backpack", "swing")
FRAME_COUNT = 16
FPS = 12
FORMATS = {".jpg", ".jpeg", ".png", ".webp"}


def groups(values):
    indices = np.flatnonzero(values)
    return [int(round(group.mean())) for group in np.split(indices, np.flatnonzero(np.diff(indices) > 1) + 1) if len(group)]


def regular_lines(candidates, count, length, min_start=.05, min_span=.7):
    """Ajusta uma sequência inteira sem combinações exponenciais de candidatos."""
    values = np.array(candidates)
    best = None
    for start in candidates:
        for end in candidates:
            if start < min_start * length or end - start < min_span * length:
                continue
            targets = np.linspace(start, end, count)
            selected = values[np.abs(values[:, None] - targets).argmin(axis=0)]
            step = (end - start) / (count - 1)
            if len(set(selected)) != count or np.max(np.abs(selected - targets)) > max(3, step * .15):
                continue
            score = float(np.abs(selected - targets).mean() / step)
            if best is None or score < best[0]:
                best = score, selected.tolist()
    if best is None:
        raise ValueError("Grade escura 12x8 não detectada. Informe --grid X0 Y0 X1 Y1.")
    return best[1]


def detect_grid(rgb, explicit=None):
    height, width = rgb.shape[:2]
    if explicit:
        x0, y0, x1, y1 = explicit
        if not (0 <= x0 < x1 < width and 0 <= y0 < y1 < height):
            raise ValueError("Coordenadas da grade fora da imagem.")
        return np.linspace(x0, x1, 9).round().astype(int).tolist(), np.linspace(y0, y1, 13).round().astype(int).tolist()
    dark = (cv2.cvtColor(rgb[:, :, :3], cv2.COLOR_RGB2GRAY) < 145).astype(np.uint8)
    # Abertura na máscara de detecção de linhas, nunca no personagem.
    vertical = cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((max(3, int(height * .65)), 1), np.uint8))
    horizontal = cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((1, max(3, int(width * .65))), np.uint8))
    xs = groups(vertical.sum(axis=0) > height * .65)
    ys = groups(horizontal.sum(axis=1) > width * .65)
    return regular_lines(xs, 9, width), regular_lines(ys, 13, height)


def green_masks(rgb):
    r, g, b = (rgb[:, :, i].astype(np.int16) for i in range(3))
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    candidate = ((hsv[:, :, 0] >= 48) & (hsv[:, :, 0] <= 78) & (hsv[:, :, 1] > 140) & (hsv[:, :, 2] > 140)) | ((g > 190) & (r < 80) & (b < 80))
    # Transições JPEG só são elegíveis para o flood fill externo. Ilhas
    # internas ainda precisam atender à pureza neon superior a 85%.
    transition = (g > np.maximum(r, b) + 24) & (hsv[:, :, 1] > 90) & (g > 70)
    neon = (g > 215) & (r < 45) & (b < 45)
    return candidate, transition, neon


def cell_bounds(rgb, xs, ys, row, col):
    """Ajusta linhas locais que desviam alguns pixels da projeção da sheet."""
    gray = cv2.cvtColor(rgb[:, :, :3], cv2.COLOR_RGB2GRAY)
    height, width = gray.shape
    def refine(position, start, stop, vertical):
        limit = width if vertical else height
        low, high = max(0, position - 6), min(limit, position + 7)
        sample = gray[start:stop, low:high] if vertical else gray[low:high, start:stop]
        scores = (sample < 130).mean(axis=0 if vertical else 1)
        choices = np.flatnonzero(scores >= .75)
        if not len(choices):
            return position
        runs = [g for g in np.split(choices, np.flatnonzero(np.diff(choices) > 1) + 1) if len(g)]
        run = min(runs, key=lambda g: abs(low + g.mean() - position))
        return int(round(low + run.mean()))
    left = refine(xs[col], ys[row]+4, ys[row+1]-4, True)
    right = refine(xs[col+1], ys[row]+4, ys[row+1]-4, True)
    top = refine(ys[row], left+4, right-4, False)
    bottom = refine(ys[row+1], left+4, right-4, False)
    return left+2, top+2, right-2, bottom-2


def clean_cell(pixels):
    pixels = np.asarray(pixels, dtype=np.uint8)
    rgb = pixels[:, :, :3].copy()
    original_alpha = pixels[:, :, 3] if pixels.shape[2] == 4 else np.full(rgb.shape[:2], 255, np.uint8)
    candidate, transition, neon = green_masks(rgb)
    eligible = ((candidate | transition) & (original_alpha > 0)).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(eligible, connectivity=4)
    edge_ids = np.unique(np.concatenate((labels[0], labels[-1], labels[:, 0], labels[:, -1])))
    edge_ids = edge_ids[edge_ids != 0]
    external = np.isin(labels, edge_ids)
    removed = external.copy()
    islands = []
    for component in range(1, count):
        if component in edge_ids:
            continue
        region = labels == component
        purity = float(neon[region].mean())
        if purity > .85:
            removed |= region
            islands.append({"area": int(stats[component, cv2.CC_STAT_AREA]), "neon_fraction": purity})
    alpha = original_alpha.copy()
    alpha[removed] = 0
    opaque = alpha > 0
    if not np.any(opaque):
        raise ValueError("Célula sem personagem após a limpeza do verde.")
    # Despill altera só a cor de um pixel de borda, sem afinar a máscara alfa.
    boundary = opaque & (cv2.dilate((~opaque).astype(np.uint8), np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], np.uint8), borderType=cv2.BORDER_CONSTANT, borderValue=1) > 0)
    r, g, b = (rgb[:, :, i].astype(np.int16) for i in range(3))
    spill = boundary & (g > np.maximum(r, b))
    rgb[:, :, 1][spill] = ((r[spill] + b[spill]) // 2).astype(np.uint8)
    rgb[~opaque] = 0
    return Image.fromarray(np.dstack((rgb, alpha))), {
        "background_removed": int(removed.sum()), "external_removed": int(external.sum()),
        "internal_islands": islands, "green_detail_pixels_preserved": int((candidate & opaque).sum()),
        "despill_pixels": int(spill.sum()), "foreground_pixels": int(opaque.sum()),
    }


def top_center(image):
    box = image.getchannel("A").getbbox()
    return (box[0] + box[2]) / 2


def stabilize(cells, size=160, padding=4):
    boxes = [image.getchannel("A").getbbox() for _, _, _, image, _ in cells]
    max_width = max(box[2] - box[0] for box in boxes)
    max_height = max(box[3] - box[1] for box in boxes)
    scale = min((size - 2 * padding) / max_width, (size - 2 * padding) / max_height)
    result = []
    for entry, box in zip(cells, boxes):
        theme, action, index, image, meta = entry
        crop = image.crop(box)
        crop = crop.resize((max(1, round(crop.width * scale)), max(1, round(crop.height * scale))), Image.Resampling.NEAREST)
        crop = crop.crop(crop.getchannel("A").getbbox())
        canvas = Image.new("RGBA", (size, size))
        x = (size - crop.width) // 2
        y = 0 if action == "swing" else size - padding - crop.height
        canvas.alpha_composite(crop, (x, y))
        result.append((theme, action, index, canvas, dict(meta, source_bbox=box, output_bbox=canvas.getchannel("A").getbbox(), anchor="top-center" if action == "swing" else "bottom-center")))
    return result, scale


def validate_output(output, size=160):
    inspected = []
    expected = {f"frame_{i:02d}.png" for i in range(FRAME_COUNT)}
    for theme in THEMES:
        for action in ACTIONS:
            files = sorted((Path(output) / theme / action).glob("frame_*.png"))
            if {file.name for file in files} != expected:
                raise ValueError(f"Esperados exatamente 16 PNGs frame_00..15 em {theme}/{action}.")
            for file in files:
                with Image.open(file) as image:
                    if image.mode != "RGBA" or image.size != (size, size):
                        raise ValueError(f"Formato inválido: {file}")
                    alpha = image.getchannel("A")
                    box = alpha.getbbox()
                    if not box or alpha.getextrema() != (0, 255):
                        raise ValueError(f"Transparência inválida: {file}")
                    if box[0] < 4 or box[2] > size - 4 or (action != "swing" and (box[1] < 4 or box[3] != size - 4)) or (action == "swing" and box[1] != 0):
                        raise ValueError(f"Margem ou âncora inválida: {file}")
                    if abs((box[0] + box[2]) / 2 - size / 2) > .5:
                        raise ValueError(f"Centro desalinhado: {file}")
            inspected.append({"theme": theme, "action": action, "frames": FRAME_COUNT})
    return inspected


def debug_preview(output, destination, size=160):
    canvas = Image.new("RGB", (len(ACTIONS) * (size + 12) + 110, len(THEMES) * (size + 32) + 32), "#333333")
    draw = ImageDraw.Draw(canvas)
    for col, action in enumerate(ACTIONS):
        draw.text((110 + col * (size + 12), 8), action, fill="white")
    for row, theme in enumerate(THEMES):
        y = 32 + row * (size + 32)
        draw.text((4, y + size // 2), theme, fill="white")
        for col, action in enumerate(ACTIONS):
            index = 4 if action == "drink" else 0
            with Image.open(Path(output) / theme / action / f"frame_{index:02d}.png") as image:
                canvas.paste(image, (110 + col * (size + 12), y), image)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination)


def source_for(input_dir, theme):
    names = {theme, "anonovo"} if theme == "ano_novo" else {theme}
    choices = sorted(p for p in Path(input_dir).iterdir() if p.is_file() and p.stem.lower().replace(" ", "_").replace("-", "_") in names and p.suffix.lower() in FORMATS)
    if len(choices) != 1:
        raise ValueError(f"Esperada uma única sheet JPG/JPEG/PNG/WebP de {theme} em {input_dir}; encontrados {len(choices)}.")
    return choices[0]


def build(input_dir, output_dir, size=160, grid=None, report=None, preview=None):
    input_dir, output_dir = Path(input_dir), Path(output_dir)
    sources, cells = {}, []
    for theme in THEMES:
        source = source_for(input_dir, theme)
        with Image.open(source) as image:
            pixels = np.asarray(image.convert("RGBA"))
        xs, ys = detect_grid(pixels, grid)
        sources[theme] = {"source": source.name, "sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "x_lines": xs, "y_lines": ys, "rows": 12, "columns": 8}
        for action_index, action in enumerate(ACTIONS):
            for index in range(FRAME_COUNT):
                row, col = 2 * action_index + index // 8, index % 8
                x0, y0, x1, y1 = cell_bounds(pixels, xs, ys, row, col)
                crop = pixels[y0:y1, x0:x1].copy()
                if min(crop.shape[:2]) < 8:
                    raise ValueError("Célula pequena demais após remover dois pixels da grade.")
                cleaned, meta = clean_cell(crop)
                cells.append((theme, action, index, cleaned, dict(meta, row=row, column=col, cell_bbox=[x0,y0,x1,y1])))
    frames, scale = stabilize(cells, size)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".sprites-build-", dir=output_dir.parent) as temp:
        stage = Path(temp)
        assert stage.resolve().parent == output_dir.parent.resolve()
        for theme, action, index, image, _ in frames:
            folder = stage / theme / action
            folder.mkdir(parents=True, exist_ok=True)
            image.save(folder / f"frame_{index:02d}.png", optimize=True)
        verified = validate_output(stage, size)
        manifest = {"version": 2, "size": size, "fps": FPS, "frame_count": FRAME_COUNT, "frame_digits": 2, "layout": "stacked_2x8", "models": {theme: {"directory": theme, "source_sha256": sources[theme]["sha256"]} for theme in THEMES}}
        for theme in THEMES:
            for action in ACTIONS:
                folder = output_dir / theme / action
                folder.mkdir(parents=True, exist_ok=True)
                for index in range(FRAME_COUNT):
                    shutil.copyfile(stage / theme / action / f"frame_{index:02d}.png", folder / f"frame_{index:02d}.png")
        temp_manifest = output_dir / "manifest.json.tmp"
        temp_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        temp_manifest.replace(output_dir / "manifest.json")
        expected = {f"frame_{i:02d}.png" for i in range(FRAME_COUNT)}
        for theme in THEMES:
            for action in ACTIONS:
                for old in (output_dir / theme / action).glob("frame_*.png"):
                    if re.fullmatch(r"frame_\d+\.png", old.name) and old.name not in expected:
                        old.unlink()  # Só frames gerados obsoletos, após validar os novos.
    validate_output(output_dir, size)
    destination = Path(preview) if preview else output_dir.parent / "debug_preview.png"
    debug_preview(output_dir, destination, size)
    result = {"generated_at": datetime.now().astimezone().isoformat(), "total_pngs": len(frames), "fps": FPS, "scale": scale, "size": size, "sources": sources, "verified": verified, "preview": str(destination), "frames": [dict(theme=t, action=a, frame=i, **meta) for t, a, i, _, meta in frames]}
    if report:
        Path(report).parent.mkdir(parents=True, exist_ok=True)
        Path(report).write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "assets" / "raw_sheets")
    parser.add_argument("--output", type=Path, default=ROOT / "assets" / "sprites")
    parser.add_argument("--preview", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--size", type=int, default=160)
    parser.add_argument("--grid", type=int, nargs=4, metavar=("X0", "Y0", "X1", "Y1"))
    args = parser.parse_args()
    if not 64 <= args.size <= 512:
        parser.error("Tamanho deve estar entre 64 e 512.")
    result = build(args.input, args.output, args.size, args.grid, report=args.report, preview=args.preview)
    print(f"Gerados e validados {result['total_pngs']} PNGs; {FRAME_COUNT} frames por ação a {FPS} FPS.")


if __name__ == "__main__":
    main()
