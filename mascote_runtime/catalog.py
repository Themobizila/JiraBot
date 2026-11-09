"""Contrato de modelos: sheets PNG e retângulos definidos em JSON."""
import json
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
ACTIONS = {"idle", "walk", "drink", "sit", "backpack", "swing"}


def load_catalog(path=None):
    if path is None:
        built = PROJECT / "assets" / "sprites" / "manifest.json"
        if built.is_file():
            catalog = load_png_catalog(built)
            hd = built.with_name("normal_hd.json")
            if hd.is_file():
                catalog["models"]["normal"] = load_png_catalog(hd)["models"]["normal"]
            return catalog
        files = sorted((PROJECT / "mascote" / "modelos").glob("*.json"), key=lambda p: (p.stat().st_mtime, p.name))
        if not files:
            raise ValueError("Nenhum manifesto em mascote/modelos.")
        path = files[-1]
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if data.get("version") == 2:
        return load_png_catalog(path)
    if data.get("version") != 1 or "normal" not in data.get("models", {}):
        raise ValueError("Manifesto de mascote inválido: versão 1 e modelo normal obrigatórios.")
    for model in data["models"].values():
        sheet = (PROJECT / "mascote" / model["sheet"]).resolve()
        try:
            sheet.relative_to((PROJECT / "mascote").resolve())
        except ValueError:
            raise ValueError("A sheet deve ficar dentro da pasta mascote.")
        if sheet.suffix.lower() != ".png" or not sheet.is_file():
            raise ValueError("Sheet PNG não encontrada: " + sheet.name)
        model["path"] = str(sheet)
        if not ACTIONS.issubset(model.get("actions", {})):
            raise ValueError("Modelo deve definir as seis ações, mesmo usando fallback visual.")
        for action in model["actions"].values():
            fps = action.get("fps", 6)
            if isinstance(fps, bool) or not isinstance(fps, (int, float)) or not 1 <= fps <= 24:
                raise ValueError("FPS deve estar entre 1 e 24.")
            # Faixas normalizadas permitem trocar a resolução sem alterar o motor.
            if "frames" in action:
                frames = action["frames"]
                if not isinstance(frames, list) or not frames:
                    raise ValueError("Lista de quadros vazia.")
                for rect in frames:
                    if len(rect) != 4 or not 0 <= rect[0] < rect[2] <= 1 or not 0 <= rect[1] < rect[3] <= 1:
                        raise ValueError("Retângulo de quadro inválido.")
            else:
                y0, y1 = action["band"]
                count = action["count"]
                if not 0 <= y0 < y1 <= 1 or type(count) is not int or not 1 <= count <= 64:
                    raise ValueError("Faixa de animação inválida.")
    return data


def load_png_catalog(path):
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if data.get("version") != 2 or "normal" not in data.get("models", {}):
        raise ValueError("Manifesto PNG inválido.")
    fps = data.get("fps", 12)
    if type(fps) is not int or not 1 <= fps <= 24:
        raise ValueError("FPS do catálogo deve estar entre 1 e 24.")
    models = {}
    default_frame_count = data.get("frame_count", 16)
    digits = data.get("frame_digits", 0)
    if type(digits) is not int or digits not in (0, 2):
        raise ValueError("Numeração de frames inválida.")
    if data.get("layout") == "stacked_2x8":
        if default_frame_count != 16 or digits != 2 or fps != 12 or set(data["models"]) != {"normal", "halloween", "natal", "ano_novo", "pascoa"}:
            raise ValueError("Catálogo 12x8 deve conter cinco temas, 16 frames e 12 FPS.")
    for theme, entry in data["models"].items():
        folder = (path.parent / entry["directory"]).resolve()
        try:
            folder.relative_to(path.parent.resolve())
        except ValueError:
            raise ValueError("Pasta de sprites fora do catálogo.")
        frame_count = entry.get("frame_count", default_frame_count)
        if type(frame_count) is not int or not 1 <= frame_count <= 64:
            raise ValueError("Quantidade de frames inválida.")
        actions = {}
        specs = entry.get("actions", {})
        optional_actions = {"sit_down", "stand_up", "fall", "recover", "walk_stop", "idle_quad"}
        for action in sorted(ACTIONS | (set(specs) & optional_actions)):
            spec = specs.get(action, {})
            count = spec.get("frame_count", frame_count)
            if type(count) is not int or not 1 <= count <= 64:
                raise ValueError("Quantidade de quadros da ação inválida.")
            files = [folder / action / f"frame_{i:0{digits}d}.png" for i in range(count)]
            if not all(file.is_file() for file in files):
                raise ValueError(f"Esperados {count} quadros em {theme}/{action}. Execute scripts/build_sprites.py.")
            aliases = entry.get("frame_aliases", {}).get(action, {})
            for destination, source in aliases.items():
                if not str(destination).isdigit() or not 0 <= int(destination) < frame_count or type(source) is not int or not 0 <= source < frame_count:
                    raise ValueError("Substituição de quadro inválida.")
                files[int(destination)] = folder / action / f"frame_{source:0{digits}d}.png"
            actions[action] = {"files": [str(f) for f in files], "fps": fps, "anchor": "top-center" if action == "swing" else "bottom-center"}
            durations = spec.get("duration_ms")
            if durations is not None:
                if not isinstance(durations, list) or len(durations) != count or any(type(v) is not int or not 20 <= v <= 10000 for v in durations):
                    raise ValueError("Durações dos quadros inválidas.")
                actions[action]["duration_ms"] = durations
        models[theme] = {"sprite_frames": True, "actions": actions,
                         "walk_faces_left": bool(entry.get("walk_faces_left", False))}
    return {"version": 2, "models": models}


def rectangles(action, width, height):
    if "frames" in action:
        return [tuple(round(v * (width if i % 2 == 0 else height)) for i, v in enumerate(r)) for r in action["frames"]]
    y0, y1 = action["band"]
    n = action["count"]
    return [(round(i * width / n), round(y0 * height), round((i + 1) * width / n), round(y1 * height)) for i in range(n)]


def sprite_rectangles(action, sheet):
    """Ajusta divisórias de faixas ao espaço vazio entre os personagens.

    Recortes explícitos do modelo são usados exatamente como definidos.
    """
    boxes = rectangles(action, *sheet.size)
    if "frames" in action or len(boxes) < 2:
        return boxes
    width, _height = sheet.size
    y0, y1 = boxes[0][1], boxes[0][3]
    mask = sheet.getchannel("A").point(lambda a: 255 if a >= 160 else 0)
    radius = max(1, width // (len(boxes) * 4))
    cuts = [0]
    for box in boxes[:-1]:
        expected = box[2]
        start, end = max(cuts[-1] + 1, expected - radius), min(width - 1, expected + radius)
        cut = min(range(start, end + 1), key=lambda x: (mask.crop((x, y0, x + 1, y1)).histogram()[255], abs(x - expected)))
        cuts.append(cut)
    cuts.append(width)
    return [(cuts[i], y0, cuts[i + 1], y1) for i in range(len(boxes))]


def character_anchor(frame):
    """Centro horizontal e base do maior componente opaco do personagem.

    Ignora margens transparentes e efeitos soltos, sem inverter quadros ou pixels.
    """
    mask = frame.getchannel("A").point(lambda a: 255 if a >= 160 else 0)
    pixels = bytearray(mask.tobytes())
    width, height = frame.size
    best_count, best = 0, None
    for start in range(len(pixels)):
        if not pixels[start]:
            continue
        pixels[start] = 0
        stack = [start]
        count = 0
        left = right = start % width
        bottom = start // width
        while stack:
            index = stack.pop()
            x, y = index % width, index // width
            count += 1
            left, right, bottom = min(left, x), max(right, x), max(bottom, y)
            adjacent = []
            if x:
                adjacent.append(index - 1)
            if x + 1 < width:
                adjacent.append(index + 1)
            if y:
                adjacent.append(index - width)
            if y + 1 < height:
                adjacent.append(index + width)
            for neighbor in adjacent:
                if pixels[neighbor]:
                    pixels[neighbor] = 0
                    stack.append(neighbor)
        if count > best_count:
            best_count, best = count, ((left + right + 1) / 2, bottom + 1)
    return best or (width / 2, height)


def align_frames(groups, size):
    """Alinha as poses a um apoio fixo, preservando escala e orientação comuns."""
    from PIL import Image
    prepared = {}
    side = above = below = 1.0
    for name, frames in groups.items():
        prepared[name] = []
        for frame in frames:
            # O mesmo limiar usado pelo renderizador evita que franjas de alfa
            # quase zero determinem o centro ou o tamanho do personagem.
            bbox = frame.getchannel("A").point(lambda a: 255 if a >= 160 else 0).getbbox()
            if bbox is None:
                raise ValueError("Quadro sem personagem visível.")
            ax, ay = character_anchor(frame)
            left, top, right, bottom = bbox
            side = max(side, ax - left, right - ax)
            above, below = max(above, ay - top), max(below, bottom - ay)
            prepared[name].append((frame.crop(bbox), ax - left, ay - top))
    scale = min(size / (2 * side), size / (above + below))
    baseline = size - round(below * scale)
    out = {}
    for name, entries in prepared.items():
        out[name] = []
        for frame, ax, ay in entries:
            frame = frame.resize((max(1, round(frame.width * scale)), max(1, round(frame.height * scale))), Image.Resampling.NEAREST)
            canvas = Image.new("RGBA", (size, size))
            canvas.alpha_composite(frame, (round(size / 2 - ax * scale), baseline - round(ay * scale)))
            out[name].append(canvas)
    return out


def load_frames(model, size=180, actions=None):
    """Recorta somente em memória. Originais e PNGs permanecem inalterados."""
    from PIL import Image
    if model.get("sprite_frames"):
        groups = {}
        for action, spec in model["actions"].items():
            if actions is not None and action not in actions:
                continue
            groups[action] = []
            for file in spec["files"]:
                with Image.open(file) as source:
                    image = source.convert("RGBA")
                if image.size != (size, size):
                    image = image.resize((size, size), Image.Resampling.NEAREST)
                groups[action].append(image)
        return groups
    with Image.open(model["path"]) as source:
        sheet = source.convert("RGBA")
    groups = {}
    for name, action in model["actions"].items():
        if actions is not None and name not in actions:
            continue
        frames = [sheet.crop(r) for r in sprite_rectangles(action, sheet)]
        groups[name] = frames
    return align_frames(groups, size)
