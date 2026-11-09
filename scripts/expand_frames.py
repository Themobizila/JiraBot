"""Gera 16 quadros por acao a partir dos 8 quadros-chave para todos os 5 temas.

Utiliza fluxo optico bidirecional DIS com preservacao absoluta do nucleo corporal
do personagem (sem fissuras ou buracos), eliminando o desaparecimento de membros
ou acessorios durante as transicoes. Mantem ancoras estritas (156 no solo e 0 no balanco),
centralizacao estavel e transparencia 100% alfa em PNG de alta definicao.
Tambem compoe os sprite sheets completos em formato PNG transparente (2560x960).
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_sprites import top_center, THEMES, ACTIONS

SIZE = 160
GROUND_ANCHOR = 156


def interpolate_pair(im1_rgba: np.ndarray, im2_rgba: np.ndarray, action: str, t: float = 0.5) -> Image.Image:
    """Interpola dois quadros RGBA preservando integralmente o corpo do personagem."""
    h, w = im1_rgba.shape[:2]

    a1 = (im1_rgba[:, :, 3] > 64).astype(np.uint8)
    a2 = (im2_rgba[:, :, 3] > 64).astype(np.uint8)

    gray1 = cv2.bitwise_and(cv2.cvtColor(im1_rgba[:, :, :3], cv2.COLOR_RGB2GRAY), cv2.cvtColor(im1_rgba[:, :, :3], cv2.COLOR_RGB2GRAY), mask=a1)
    gray2 = cv2.bitwise_and(cv2.cvtColor(im2_rgba[:, :, :3], cv2.COLOR_RGB2GRAY), cv2.cvtColor(im2_rgba[:, :, :3], cv2.COLOR_RGB2GRAY), mask=a2)

    dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    flow_fwd = dis.calc(gray1, gray2, None)
    flow_bwd = dis.calc(gray2, gray1, None)

    grid_x, grid_y = np.meshgrid(np.arange(w), np.arange(h))

    map1_x = np.clip(grid_x - flow_fwd[:, :, 0] * t, 0, w - 1).astype(np.float32)
    map1_y = np.clip(grid_y - flow_fwd[:, :, 1] * t, 0, h - 1).astype(np.float32)
    warped1 = cv2.remap(im1_rgba, map1_x, map1_y, interpolation=cv2.INTER_NEAREST)

    map2_x = np.clip(grid_x - flow_bwd[:, :, 0] * (1.0 - t), 0, w - 1).astype(np.float32)
    map2_y = np.clip(grid_y - flow_bwd[:, :, 1] * (1.0 - t), 0, h - 1).astype(np.float32)
    warped2 = cv2.remap(im2_rgba, map2_x, map2_y, interpolation=cv2.INTER_NEAREST)

    # O nucleo presente em ambos os quadros chave NUNCA pode desaparecer
    core_mask = (a1 > 0) & (a2 > 0)
    w1_mask = warped1[:, :, 3] > 64
    w2_mask = warped2[:, :, 3] > 64
    solid_mask = core_mask | w1_mask | w2_mask

    # Fechamento morfologico para vedar quaisquer fissuras de fluxo optico no contorno
    solid_mask = cv2.morphologyEx(solid_mask.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8)).astype(bool)
    if action != "swing":
        solid_mask[156:, :] = False

    out = np.zeros((h, w, 4), dtype=np.uint8)

    # Mistura suave de cores entre as projecoes forward e backward
    both_warped = w1_mask & w2_mask
    only_w1 = w1_mask & (~w2_mask)
    only_w2 = (~w1_mask) & w2_mask
    neither = solid_mask & (~w1_mask) & (~w2_mask)

    rgb1 = warped1[:, :, :3].astype(np.float32)
    rgb2 = warped2[:, :, :3].astype(np.float32)
    blended = np.clip((1.0 - t) * rgb1 + t * rgb2, 0, 255).astype(np.uint8)

    out[both_warped, :3] = blended[both_warped]
    out[only_w1, :3] = warped1[only_w1, :3]
    out[only_w2, :3] = warped2[only_w2, :3]

    if t <= 0.5:
        out[neither, :3] = np.where((im1_rgba[neither, 3:4] > 0), im1_rgba[neither, :3], im2_rgba[neither, :3])
    else:
        out[neither, :3] = np.where((im2_rgba[neither, 3:4] > 0), im2_rgba[neither, :3], im1_rgba[neither, :3])

    out[:, :, 3] = np.where(solid_mask, 255, 0).astype(np.uint8)

    if action == "swing":
        for y in range(4):
            rope_mask = (im1_rgba[y, :, 3] > 0) | (im2_rgba[y, :, 3] > 0)
            if np.any(rope_mask):
                out[y, rope_mask] = np.where((im1_rgba[y, rope_mask, 3:4] > 0), im1_rgba[y, rope_mask], im2_rgba[y, rope_mask])

    res = Image.fromarray(out)
    bbox = res.getchannel("A").getbbox()
    if bbox:
        crop = res.crop(bbox)
        canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        if action == "swing":
            x = round(w / 2 - top_center(crop))
            y = 0
        else:
            x = (w - crop.width) // 2
            y = GROUND_ANCHOR - crop.height
        canvas.alpha_composite(crop, (x, y))
        return canvas
    return res


def expand_animation(frames_8: list[Image.Image], action: str) -> list[Image.Image]:
    """Expande 8 quadros-chave para 16 quadros continuos com in-betweens suaves e solidos."""
    frames_16 = []
    for i in range(8):
        orig = frames_8[i]
        frames_16.append(orig)

        next_orig = frames_8[(i + 1) % 8]
        im1 = np.asarray(orig)
        im2 = np.asarray(next_orig)
        in_between = interpolate_pair(im1, im2, action=action, t=0.5)
        frames_16.append(in_between)
    return frames_16


def build_16_frames(sprites_dir: Path = ROOT / "assets" / "sprites", sheets_dir: Path = ROOT / "mascote") -> dict:
    """Gera os 480 quadros PNG e os 5 sprite sheets PNG transparentes."""
    sprites_dir = Path(sprites_dir)
    sheets_dir = Path(sheets_dir)
    assets_sheets_dir = ROOT / "assets" / "sheets"
    assets_sheets_dir.mkdir(parents=True, exist_ok=True)

    summary = {"themes": {}, "total_frames": 0, "sheets": []}

    for theme in THEMES:
        theme_summary = {"actions": {}}
        sheet_canvas = Image.new("RGBA", (16 * SIZE, len(ACTIONS) * SIZE), (0, 0, 0, 0))

        for row, action in enumerate(ACTIONS):
            action_dir = sprites_dir / theme / action
            if not action_dir.is_dir():
                raise FileNotFoundError(f"Diretorio nao encontrado: {action_dir}")

            # Carrega os 8 quadros-chave originais (indices pares)
            frame_files = sorted(action_dir.glob("frame_*.png"), key=lambda p: int(p.stem.split("_")[1]))
            if len(frame_files) == 16:
                key_files = [action_dir / f"frame_{i * 2}.png" for i in range(8)]
            else:
                key_files = [action_dir / f"frame_{i}.png" for i in range(8)]

            existing_frames = []
            for kf in key_files:
                if not kf.is_file():
                    raise FileNotFoundError(f"Quadro ausente: {kf}")
                with Image.open(kf) as f:
                    existing_frames.append(f.convert("RGBA"))

            # Gera os 16 quadros
            frames_16 = expand_animation(existing_frames, action)

            # Salva os 16 quadros
            for idx, frame in enumerate(frames_16):
                frame_path = action_dir / f"frame_{idx}.png"
                frame.save(frame_path, optimize=True)

                # Cola no sprite sheet
                sheet_canvas.alpha_composite(frame, (idx * SIZE, row * SIZE))

            theme_summary["actions"][action] = len(frames_16)
            summary["total_frames"] += len(frames_16)

        # Salva o sprite sheet PNG transparente em mascote/ e assets/sheets/
        sheet_path_mascote = sheets_dir / f"{theme}.png"
        sheet_path_assets = assets_sheets_dir / f"{theme}.png"
        sheet_canvas.save(sheet_path_mascote, optimize=True)
        sheet_canvas.save(sheet_path_assets, optimize=True)
        summary["sheets"].append(str(sheet_path_mascote))
        summary["sheets"].append(str(sheet_path_assets))
        summary["themes"][theme] = theme_summary

    # Atualiza o manifest.json para version: 2, frame_count: 16, fps: 14
    manifest_path = sprites_dir / "manifest.json"
    manifest_data = {
        "version": 2,
        "size": SIZE,
        "fps": 14,
        "frame_count": 16,
        "models": {
            theme: {
                "directory": theme,
                "frame_count": 16,
                "sheet": f"{theme}.png",
                **({"frame_aliases": {"idle": {"5": 4}, "walk": {"4": 3}}} if theme == "halloween" else {})
            }
            for theme in THEMES
        }
    }
    manifest_path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print("Iniciando geracao de 16 quadros solidos por acao...")
    res = build_16_frames()
    print(f"Sucesso! Total de quadros gerados: {res['total_frames']}")
    print(f"Sprite sheets criados: {len(res['sheets'])}")
