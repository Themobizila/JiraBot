"""Refaz os sprites sem background em Pixel Art HD com temas completos e limpos.

Garante continuidade tematica completa e qualidade nativa do ilustrador:
- Ano Novo: mochila (backpack) e balanco (swing) com chapeu conico festivo em pixel art HD,
  cachecol ouro/carvao completo e oculos polarizados com reflexo suave.
- Preserva integralmente os desenhos originais de Natal, Halloween e Pascoa.
- Expansao deterministica solida para 16 quadros por acao (480 sprites).
- Reconstrucao dos 10 sprite sheets mestres (2560x960).
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_sprites import top_center, THEMES, ACTIONS
from scripts.expand_frames import expand_animation, SIZE, GROUND_ANCHOR


def dress_ano_novo_swing_hd(im: Image.Image, frame_idx: int = 0) -> Image.Image:
    """Caracteriza a capivara no balanco com tema festivo de Ano Novo em pixel art HD."""
    arr = np.asarray(im.convert("RGBA")).copy()
    r, g, b, a = (arr[:, :, i].astype(np.int16) for i in range(4))

    # Identifica regioes anatomicas
    is_blue_goggles = (a > 128) & (b > r + 15) & (b > g + 5) & (b > 40) & (np.arange(160)[:, None] >= 24) & (np.arange(160)[:, None] <= 45) & (np.arange(160)[None, :] >= 55) & (np.arange(160)[None, :] <= 95)
    is_rope = (np.arange(160)[:, None] < 50) & ((np.arange(160)[None, :] < 42) | (np.arange(160)[None, :] > 115))

    # 1. Cachecol completo (incluindo a ponta segurada na pata esquerda em x < 45)
    is_blue_scarf = (a > 128) & (b > r + 15) & (b > g + 5) & (b > 40) & (~is_blue_goggles) & (~is_rope)
    is_yellow_scarf = (a > 128) & (r > 150) & (g > 130) & (b < 115) & (r - b > 50) & (r - g < 50) & (~is_rope)

    # Remapeamento do azul para dourado gradiente mantendo todas as dobras e sombras
    for y, x in zip(*np.nonzero(is_blue_scarf)):
        val = b[y, x]
        norm = np.clip((val - 40) / 180.0, 0, 1)
        gold_r = int(150 + norm * 105)
        gold_g = int(110 + norm * 115)
        gold_b = int(25 + norm * 90)
        arr[y, x, :3] = [gold_r, gold_g, gold_b]

    # Remapeamento das listras amarelas para carvao/preto elegante
    for y, x in zip(*np.nonzero(is_yellow_scarf)):
        val = r[y, x]
        norm = np.clip((val - 150) / 100.0, 0, 1)
        dark_val = int(18 + norm * 34)
        arr[y, x, :3] = [dark_val, dark_val - 2, dark_val + 4]

    # 2. Oculos polarizados escuros com brilho especular (preserva o rosto e bochechas)
    for y, x in zip(*np.nonzero(is_blue_goggles)):
        val = b[y, x]
        if val > 140:
            arr[y, x, :3] = [200, 235, 255]
        elif val > 110:
            arr[y, x, :3] = [100, 140, 175]
        elif val > 80:
            arr[y, x, :3] = [45, 55, 75]
        else:
            arr[y, x, :3] = [20, 24, 34]

    # 3. Chapeu conico festivo dourado centralizado entre as orelhas
    head_region = (a > 128) & (np.arange(160)[None, :] >= 60) & (np.arange(160)[None, :] <= 100)
    ys_h, xs_h = np.nonzero(head_region)
    head_min_y = ys_h.min()
    mean_head_x = xs_h[ys_h == head_min_y].mean()
    dx = int(round(mean_head_x - 86.5))

    hat_pixels = [
        # Ponta com estrelinha / pompom cintilante
        (2, 82 + dx, 255, 255, 220, 255),
        (3, 81 + dx, 255, 255, 180, 255), (3, 82 + dx, 255, 255, 255, 255), (3, 83 + dx, 255, 230, 140, 255),
        (4, 82 + dx, 255, 215, 0, 255),
        # Corpo conico
        (5, 81 + dx, 50, 35, 20, 255), (5, 82 + dx, 255, 240, 150, 255), (5, 83 + dx, 50, 35, 20, 255),
        (6, 81 + dx, 50, 35, 20, 255), (6, 82 + dx, 255, 215, 0, 255), (6, 83 + dx, 218, 165, 32, 255), (6, 84 + dx, 50, 35, 20, 255),
        (7, 80 + dx, 50, 35, 20, 255), (7, 81 + dx, 255, 240, 150, 255), (7, 82 + dx, 255, 215, 0, 255), (7, 83 + dx, 218, 165, 32, 255), (7, 84 + dx, 50, 35, 20, 255),
        (8, 80 + dx, 50, 35, 20, 255), (8, 81 + dx, 255, 255, 255, 255), (8, 82 + dx, 255, 215, 0, 255), (8, 83 + dx, 184, 134, 11, 255), (8, 84 + dx, 50, 35, 20, 255),
        (9, 79 + dx, 50, 35, 20, 255), (9, 80 + dx, 255, 215, 0, 255), (9, 81 + dx, 255, 240, 150, 255), (9, 82 + dx, 218, 165, 32, 255), (9, 83 + dx, 184, 134, 11, 255), (9, 85 + dx, 50, 35, 20, 255),
        (10, 79 + dx, 50, 35, 20, 255), (10, 80 + dx, 255, 100, 120, 255), (10, 81 + dx, 255, 215, 0, 255), (10, 82 + dx, 255, 215, 0, 255), (10, 83 + dx, 184, 134, 11, 255), (10, 84 + dx, 140, 95, 8, 255), (10, 85 + dx, 50, 35, 20, 255),
        (11, 78 + dx, 50, 35, 20, 255), (11, 79 + dx, 255, 240, 150, 255), (11, 80 + dx, 255, 215, 0, 255), (11, 81 + dx, 255, 255, 255, 255), (11, 82 + dx, 218, 165, 32, 255), (11, 83 + dx, 184, 134, 11, 255), (11, 84 + dx, 140, 95, 8, 255), (11, 85 + dx, 50, 35, 20, 255),
        (12, 78 + dx, 50, 35, 20, 255), (12, 79 + dx, 255, 215, 0, 255), (12, 80 + dx, 255, 240, 150, 255), (12, 81 + dx, 255, 215, 0, 255), (12, 82 + dx, 218, 165, 32, 255), (12, 83 + dx, 184, 134, 11, 255), (12, 84 + dx, 140, 95, 8, 255), (12, 86 + dx, 50, 35, 20, 255),
        (13, 77 + dx, 50, 35, 20, 255), (13, 78 + dx, 255, 215, 0, 255), (13, 79 + dx, 100, 220, 255, 255), (13, 80 + dx, 255, 215, 0, 255), (13, 81 + dx, 255, 240, 150, 255), (13, 82 + dx, 218, 165, 32, 255), (13, 83 + dx, 184, 134, 11, 255), (13, 84 + dx, 140, 95, 8, 255), (13, 85 + dx, 140, 95, 8, 255), (13, 86 + dx, 50, 35, 20, 255),
        (14, 77 + dx, 50, 35, 20, 255), (14, 78 + dx, 255, 240, 150, 255), (14, 79 + dx, 255, 215, 0, 255), (14, 80 + dx, 255, 215, 0, 255), (14, 81 + dx, 255, 215, 0, 255), (14, 82 + dx, 218, 165, 32, 255), (14, 83 + dx, 218, 165, 32, 255), (14, 84 + dx, 184, 134, 11, 255), (14, 85 + dx, 140, 95, 8, 255), (14, 86 + dx, 50, 35, 20, 255),
        (15, 76 + dx, 50, 35, 20, 255), (15, 77 + dx, 255, 215, 0, 255), (15, 78 + dx, 255, 240, 150, 255), (15, 79 + dx, 255, 255, 255, 255), (15, 80 + dx, 255, 215, 0, 255), (15, 81 + dx, 218, 165, 32, 255), (15, 82 + dx, 255, 100, 120, 255), (15, 83 + dx, 218, 165, 32, 255), (15, 84 + dx, 184, 134, 11, 255), (15, 85 + dx, 140, 95, 8, 255), (15, 87 + dx, 50, 35, 20, 255),
        (16, 76 + dx, 50, 35, 20, 255), (16, 77 + dx, 255, 215, 0, 255), (16, 78 + dx, 255, 215, 0, 255), (16, 79 + dx, 255, 240, 150, 255), (16, 80 + dx, 255, 215, 0, 255), (16, 81 + dx, 218, 165, 32, 255), (16, 82 + dx, 218, 165, 32, 255), (16, 83 + dx, 184, 134, 11, 255), (16, 84 + dx, 184, 134, 11, 255), (16, 85 + dx, 140, 95, 8, 255), (16, 86 + dx, 140, 95, 8, 255), (16, 87 + dx, 50, 35, 20, 255),
        (17, 75 + dx, 50, 35, 20, 255), (17, 76 + dx, 255, 240, 150, 255), (17, 77 + dx, 255, 215, 0, 255), (17, 78 + dx, 255, 215, 0, 255), (17, 79 + dx, 255, 215, 0, 255), (17, 80 + dx, 218, 165, 32, 255), (17, 81 + dx, 218, 165, 32, 255), (17, 82 + dx, 184, 134, 11, 255), (17, 83 + dx, 184, 134, 11, 255), (17, 84 + dx, 140, 95, 8, 255), (17, 85 + dx, 140, 95, 8, 255), (17, 86 + dx, 140, 95, 8, 255), (17, 88 + dx, 50, 35, 20, 255),
        (18, 75 + dx, 50, 35, 20, 255), (18, 76 + dx, 255, 255, 255, 255), (18, 77 + dx, 255, 240, 150, 255), (18, 78 + dx, 255, 215, 0, 255), (18, 79 + dx, 255, 215, 0, 255), (18, 80 + dx, 218, 165, 32, 255), (18, 81 + dx, 218, 165, 32, 255), (18, 82 + dx, 184, 134, 11, 255), (18, 83 + dx, 184, 134, 11, 255), (18, 84 + dx, 140, 95, 8, 255), (18, 85 + dx, 140, 95, 8, 255), (18, 86 + dx, 140, 95, 8, 255), (18, 87 + dx, 100, 70, 5, 255), (18, 88 + dx, 50, 35, 20, 255),
        # Borda inferior dourada fofa
        (19, 74 + dx, 50, 35, 20, 255), (19, 75 + dx, 255, 250, 200, 255), (19, 76 + dx, 255, 240, 150, 255), (19, 77 + dx, 255, 215, 0, 255), (19, 78 + dx, 255, 250, 200, 255), (19, 79 + dx, 255, 215, 0, 255), (19, 80 + dx, 255, 250, 200, 255), (19, 81 + dx, 218, 165, 32, 255), (19, 82 + dx, 255, 250, 200, 255), (19, 83 + dx, 218, 165, 32, 255), (19, 84 + dx, 184, 134, 11, 255), (19, 85 + dx, 255, 250, 200, 255), (19, 86 + dx, 184, 134, 11, 255), (19, 87 + dx, 140, 95, 8, 255), (19, 88 + dx, 50, 35, 20, 255),
        (20, 74 + dx, 50, 35, 20, 255), (20, 75 + dx, 218, 165, 32, 255), (20, 76 + dx, 255, 215, 0, 255), (20, 77 + dx, 218, 165, 32, 255), (20, 78 + dx, 255, 215, 0, 255), (20, 79 + dx, 218, 165, 32, 255), (20, 80 + dx, 255, 215, 0, 255), (20, 81 + dx, 184, 134, 11, 255), (20, 82 + dx, 218, 165, 32, 255), (20, 83 + dx, 184, 134, 11, 255), (20, 84 + dx, 140, 95, 8, 255), (20, 85 + dx, 184, 134, 11, 255), (20, 86 + dx, 140, 95, 8, 255), (20, 87 + dx, 100, 70, 5, 255), (20, 88 + dx, 50, 35, 20, 255),
        (21, 75 + dx, 50, 35, 20, 255), (21, 76 + dx, 50, 35, 20, 255), (21, 77 + dx, 50, 35, 20, 255), (21, 78 + dx, 50, 35, 20, 255), (21, 79 + dx, 50, 35, 20, 255), (21, 80 + dx, 50, 35, 20, 255), (21, 81 + dx, 50, 35, 20, 255), (21, 82 + dx, 50, 35, 20, 255), (21, 83 + dx, 50, 35, 20, 255), (21, 84 + dx, 50, 35, 20, 255), (21, 85 + dx, 50, 35, 20, 255), (21, 86 + dx, 50, 35, 20, 255), (21, 87 + dx, 50, 35, 20, 255),
    ]

    for py, px, pr, pg, pb, pa in hat_pixels:
        if 0 <= py < 160 and 0 <= px < 160:
            arr[py, px] = [pr, pg, pb, pa]

    arr[:, :, 3] = np.where(arr[:, :, 3] >= 128, 255, 0).astype(np.uint8)
    return Image.fromarray(arr)


def dress_ano_novo_backpack_hd(im: Image.Image, frame_idx: int = 0) -> Image.Image:
    """Caracteriza a capivara mexendo na mochila com tema festivo de Ano Novo em pixel art HD."""
    arr = np.asarray(im.convert("RGBA")).copy()
    r, g, b, a = (arr[:, :, i].astype(np.int16) for i in range(4))

    # Identifica oculos e cachecol
    is_blue_goggles = (a > 128) & (b > r + 15) & (b > g + 5) & (b > 40) & (np.arange(160)[:, None] < 55) & (np.arange(160)[None, :] > 85)
    is_blue_scarf = (a > 128) & (b > r + 15) & (b > g + 5) & (b > 40) & (~is_blue_goggles)
    is_yellow_scarf = (a > 128) & (r > 150) & (g > 130) & (b < 115) & (r - b > 50) & (r - g < 50) & (np.arange(160)[:, None] > 40)

    # 1. Remapeamento do azul para dourado gradiente
    for y, x in zip(*np.nonzero(is_blue_scarf)):
        val = b[y, x]
        norm = np.clip((val - 40) / 180.0, 0, 1)
        gold_r = int(150 + norm * 105)
        gold_g = int(110 + norm * 115)
        gold_b = int(25 + norm * 90)
        arr[y, x, :3] = [gold_r, gold_g, gold_b]

    # 2. Listras amarelas para carvao/preto
    for y, x in zip(*np.nonzero(is_yellow_scarf)):
        val = r[y, x]
        norm = np.clip((val - 150) / 100.0, 0, 1)
        dark_val = int(18 + norm * 34)
        arr[y, x, :3] = [dark_val, dark_val - 2, dark_val + 4]

    # 3. Oculos polarizados na cabeca
    for y, x in zip(*np.nonzero(is_blue_goggles)):
        val = b[y, x]
        if val > 140:
            arr[y, x, :3] = [200, 235, 255]
        elif val > 110:
            arr[y, x, :3] = [100, 140, 175]
        elif val > 80:
            arr[y, x, :3] = [45, 55, 75]
        else:
            arr[y, x, :3] = [20, 24, 34]

    # 4. Chapeu conico festivo ajustado ao angulo da cabeca inclinada
    head_region = (a > 128) & (np.arange(160)[None, :] > 85) & (np.arange(160)[None, :] < 125) & (np.arange(160)[:, None] < 60)
    ys_h, xs_h = np.nonzero(head_region)
    min_y = ys_h.min()
    mean_head_x = xs_h[ys_h == min_y].mean()
    dx = int(round(mean_head_x - 90.0))

    hat_pixels_backpack = [
        # Estrelinha / pompom cintilante
        (11, 107 + dx, 255, 255, 220, 255),
        (12, 106 + dx, 255, 255, 180, 255), (12, 107 + dx, 255, 255, 255, 255), (12, 108 + dx, 255, 230, 140, 255),
        (13, 107 + dx, 255, 215, 0, 255),
        # Corpo conico inclinado
        (14, 105 + dx, 50, 35, 20, 255), (14, 106 + dx, 255, 240, 150, 255), (14, 107 + dx, 50, 35, 20, 255),
        (15, 104 + dx, 50, 35, 20, 255), (15, 105 + dx, 255, 215, 0, 255), (15, 106 + dx, 218, 165, 32, 255), (15, 107 + dx, 50, 35, 20, 255),
        (16, 103 + dx, 50, 35, 20, 255), (16, 104 + dx, 255, 240, 150, 255), (16, 105 + dx, 255, 215, 0, 255), (16, 106 + dx, 218, 165, 32, 255), (16, 107 + dx, 50, 35, 20, 255),
        (17, 102 + dx, 50, 35, 20, 255), (17, 103 + dx, 255, 255, 255, 255), (17, 104 + dx, 255, 215, 0, 255), (17, 105 + dx, 184, 134, 11, 255), (17, 107 + dx, 50, 35, 20, 255),
        (18, 102 + dx, 50, 35, 20, 255), (18, 103 + dx, 255, 215, 0, 255), (18, 104 + dx, 255, 240, 150, 255), (18, 105 + dx, 218, 165, 32, 255), (18, 106 + dx, 184, 134, 11, 255), (18, 108 + dx, 50, 35, 20, 255),
        (19, 101 + dx, 50, 35, 20, 255), (19, 102 + dx, 255, 100, 120, 255), (19, 103 + dx, 255, 215, 0, 255), (19, 104 + dx, 255, 215, 0, 255), (19, 105 + dx, 184, 134, 11, 255), (19, 106 + dx, 140, 95, 8, 255), (19, 108 + dx, 50, 35, 20, 255),
        (20, 100 + dx, 50, 35, 20, 255), (20, 101 + dx, 255, 240, 150, 255), (20, 102 + dx, 255, 215, 0, 255), (20, 103 + dx, 255, 255, 255, 255), (20, 104 + dx, 218, 165, 32, 255), (20, 105 + dx, 184, 134, 11, 255), (20, 106 + dx, 140, 95, 8, 255), (20, 108 + dx, 50, 35, 20, 255),
        (21, 99 + dx, 50, 35, 20, 255), (21, 100 + dx, 255, 215, 0, 255), (21, 101 + dx, 255, 240, 150, 255), (21, 102 + dx, 255, 215, 0, 255), (21, 103 + dx, 218, 165, 32, 255), (21, 104 + dx, 184, 134, 11, 255), (21, 105 + dx, 140, 95, 8, 255), (21, 107 + dx, 50, 35, 20, 255),
        (22, 98 + dx, 50, 35, 20, 255), (22, 99 + dx, 255, 215, 0, 255), (22, 100 + dx, 100, 220, 255, 255), (22, 101 + dx, 255, 215, 0, 255), (22, 102 + dx, 255, 240, 150, 255), (22, 103 + dx, 218, 165, 32, 255), (22, 104 + dx, 184, 134, 11, 255), (22, 105 + dx, 140, 95, 8, 255), (22, 106 + dx, 140, 95, 8, 255), (22, 107 + dx, 50, 35, 20, 255),
        (23, 98 + dx, 50, 35, 20, 255), (23, 99 + dx, 255, 240, 150, 255), (23, 100 + dx, 255, 215, 0, 255), (23, 101 + dx, 255, 215, 0, 255), (23, 102 + dx, 255, 215, 0, 255), (23, 103 + dx, 218, 165, 32, 255), (23, 104 + dx, 218, 165, 32, 255), (23, 105 + dx, 184, 134, 11, 255), (23, 106 + dx, 140, 95, 8, 255), (23, 108 + dx, 50, 35, 20, 255),
        (24, 97 + dx, 50, 35, 20, 255), (24, 98 + dx, 255, 215, 0, 255), (24, 99 + dx, 255, 240, 150, 255), (24, 100 + dx, 255, 255, 255, 255), (24, 101 + dx, 255, 215, 0, 255), (24, 102 + dx, 218, 165, 32, 255), (24, 103 + dx, 255, 100, 120, 255), (24, 104 + dx, 218, 165, 32, 255), (24, 105 + dx, 184, 134, 11, 255), (24, 106 + dx, 140, 95, 8, 255), (24, 108 + dx, 50, 35, 20, 255),
        (25, 96 + dx, 50, 35, 20, 255), (25, 97 + dx, 255, 215, 0, 255), (25, 98 + dx, 255, 215, 0, 255), (25, 99 + dx, 255, 240, 150, 255), (25, 100 + dx, 255, 215, 0, 255), (25, 101 + dx, 218, 165, 32, 255), (25, 102 + dx, 218, 165, 32, 255), (25, 103 + dx, 184, 134, 11, 255), (25, 104 + dx, 184, 134, 11, 255), (25, 105 + dx, 140, 95, 8, 255), (25, 106 + dx, 140, 95, 8, 255), (25, 108 + dx, 50, 35, 20, 255),
        (26, 96 + dx, 50, 35, 20, 255), (26, 97 + dx, 255, 240, 150, 255), (26, 98 + dx, 255, 215, 0, 255), (26, 99 + dx, 255, 215, 0, 255), (26, 100 + dx, 255, 215, 0, 255), (26, 101 + dx, 218, 165, 32, 255), (26, 102 + dx, 218, 165, 32, 255), (26, 103 + dx, 184, 134, 11, 255), (26, 104 + dx, 184, 134, 11, 255), (26, 105 + dx, 140, 95, 8, 255), (26, 106 + dx, 140, 95, 8, 255), (26, 107 + dx, 140, 95, 8, 255), (26, 109 + dx, 50, 35, 20, 255),
        (27, 95 + dx, 50, 35, 20, 255), (27, 96 + dx, 255, 255, 255, 255), (27, 97 + dx, 255, 240, 150, 255), (27, 98 + dx, 255, 215, 0, 255), (27, 99 + dx, 255, 215, 0, 255), (27, 100 + dx, 218, 165, 32, 255), (27, 101 + dx, 218, 165, 32, 255), (27, 102 + dx, 184, 134, 11, 255), (27, 103 + dx, 184, 134, 11, 255), (27, 104 + dx, 140, 95, 8, 255), (27, 105 + dx, 140, 95, 8, 255), (27, 106 + dx, 140, 95, 8, 255), (27, 107 + dx, 100, 70, 5, 255), (27, 109 + dx, 50, 35, 20, 255),
        # Borda inferior dourada
        (28, 95 + dx, 50, 35, 20, 255), (28, 96 + dx, 255, 250, 200, 255), (28, 97 + dx, 255, 240, 150, 255), (28, 98 + dx, 255, 215, 0, 255), (28, 99 + dx, 255, 250, 200, 255), (28, 100 + dx, 255, 215, 0, 255), (28, 101 + dx, 255, 250, 200, 255), (28, 102 + dx, 218, 165, 32, 255), (28, 103 + dx, 255, 250, 200, 255), (28, 104 + dx, 218, 165, 32, 255), (28, 105 + dx, 184, 134, 11, 255), (28, 106 + dx, 255, 250, 200, 255), (28, 107 + dx, 184, 134, 11, 255), (28, 108 + dx, 140, 95, 8, 255), (28, 109 + dx, 50, 35, 20, 255),
        (29, 95 + dx, 50, 35, 20, 255), (29, 96 + dx, 218, 165, 32, 255), (29, 97 + dx, 255, 215, 0, 255), (29, 98 + dx, 218, 165, 32, 255), (29, 99 + dx, 255, 215, 0, 255), (29, 100 + dx, 218, 165, 32, 255), (29, 101 + dx, 255, 215, 0, 255), (29, 102 + dx, 184, 134, 11, 255), (29, 103 + dx, 218, 165, 32, 255), (29, 104 + dx, 184, 134, 11, 255), (29, 105 + dx, 140, 95, 8, 255), (29, 106 + dx, 184, 134, 11, 255), (29, 107 + dx, 140, 95, 8, 255), (29, 108 + dx, 100, 70, 5, 255), (29, 109 + dx, 50, 35, 20, 255),
        (30, 96 + dx, 50, 35, 20, 255), (30, 97 + dx, 50, 35, 20, 255), (30, 98 + dx, 50, 35, 20, 255), (30, 99 + dx, 50, 35, 20, 255), (30, 100 + dx, 50, 35, 20, 255), (30, 101 + dx, 50, 35, 20, 255), (30, 102 + dx, 50, 35, 20, 255), (30, 103 + dx, 50, 35, 20, 255), (30, 104 + dx, 50, 35, 20, 255), (30, 105 + dx, 50, 35, 20, 255), (30, 106 + dx, 50, 35, 20, 255), (30, 107 + dx, 50, 35, 20, 255), (30, 108 + dx, 50, 35, 20, 255),
    ]

    for py, px, pr, pg, pb, pa in hat_pixels_backpack:
        if 0 <= py < 160 and 0 <= px < 160:
            arr[py, px] = [pr, pg, pb, pa]

    arr[:, :, 3] = np.where(arr[:, :, 3] >= 128, 255, 0).astype(np.uint8)
    return Image.fromarray(arr)


def process_clean_hd_sprites():
    """Gera o conjunto completo de 480 sprites e 10 sheets com qualidade HD autentica."""
    from scripts.build_sprites import build

    sprites_dir = ROOT / "assets" / "sprites"
    raw_dir = ROOT / "assets" / "raw_sheets"
    sheets_dir = ROOT / "mascote"
    assets_sheets_dir = ROOT / "assets" / "sheets"

    sheets_dir.mkdir(parents=True, exist_ok=True)
    assets_sheets_dir.mkdir(parents=True, exist_ok=True)

    # 1. Extrai a base canonica limpa de 8 quadros das raw sheets
    print("Extraindo base limpa de 8 quadros com build_sprites...")
    build(raw_dir, sprites_dir, size=SIZE)

    print("Iniciando refinamento e expansao para 16 quadros...")
    for theme in THEMES:
        sheet_canvas = Image.new("RGBA", (16 * SIZE, len(ACTIONS) * SIZE), (0, 0, 0, 0))

        for row, action in enumerate(ACTIONS):
            action_dir = sprites_dir / theme / action

            # Carrega os 8 quadros limpos recem-extraidos
            key_frames = [Image.open(action_dir / f"frame_{i}.png").convert("RGBA") for i in range(8)]

            # Apenas Ano Novo em swing e backpack recebe caracterizacao tematica HD
            transformed_8 = []
            for idx, frame in enumerate(key_frames):
                tf = frame
                if theme == "ano_novo":
                    if action == "swing":
                        tf = dress_ano_novo_swing_hd(tf, idx)
                    elif action == "backpack":
                        tf = dress_ano_novo_backpack_hd(tf, idx)

                # Reancoragem padronizada rigorosa
                bbox = tf.getchannel("A").getbbox()
                if bbox:
                    crop = tf.crop(bbox)
                    c = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
                    if action == "swing":
                        x = round(SIZE / 2 - top_center(crop))
                        y = 0
                    else:
                        x = (SIZE - crop.width) // 2
                        y = GROUND_ANCHOR - crop.height
                    c.alpha_composite(crop, (x, y))
                    tf = c
                transformed_8.append(tf)

            # Expande suavemente para 16 quadros continuos
            frames_16 = expand_animation(transformed_8, action)

            # Salva os 16 quadros individuais
            for idx, f16 in enumerate(frames_16):
                f16.save(action_dir / f"frame_{idx}.png", optimize=True)
                sheet_canvas.alpha_composite(f16, (idx * SIZE, row * SIZE))

        # Salva os sprite sheets mestres 2560x960
        sheet_canvas.save(sheets_dir / f"{theme}.png", optimize=True)
        sheet_canvas.save(assets_sheets_dir / f"{theme}.png", optimize=True)
        print(f"Tema '{theme}' finalizado com 16 quadros por acao e sheet 2560x960.")

    # Atualiza o manifest oficial
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
    print("Processamento HD concluido com sucesso!")


if __name__ == "__main__":
    process_clean_hd_sprites()
