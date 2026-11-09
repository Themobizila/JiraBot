"""Monta a recuperação após o impacto com os quadros selecionados do PixelLab."""
import argparse
import json
from pathlib import Path
import zipfile

from PIL import Image, ImageDraw

try:
    from .build_seated_idle_trial import checkerboard, coalesce_identical
    from .build_swing_half_comparison import save_gif, sha
    from .build_walk_stop_trial import read_frame
    from .extract_sit_pixellab import write_apng
except ImportError:
    from build_seated_idle_trial import checkerboard, coalesce_identical
    from build_swing_half_comparison import save_gif, sha
    from build_walk_stop_trial import read_frame
    from extract_sit_pixellab import write_apng


def read_sheet(path):
    with Image.open(path) as sheet:
        if sheet.mode != 'RGBA' or sheet.size not in {(768, 512), (768, 768)}:
            raise ValueError(f'Grade RGBA inválida: {path.name}')
        return [sheet.crop((x, y, x + 256, y + 256))
                for y in range(0, sheet.height, 256) for x in range(0, sheet.width, 256)]


def build(paths, output):
    hashes = {name: sha(path) for name, path in paths.items()}
    groups = {name: read_sheet(paths[name]) for name in ('patinhas', 'rolamento', 'apoio', 'subida')}
    for name in ('costas', 'baixo', 'parada'):
        groups[name] = [read_frame(paths[name])]
    assert groups['patinhas'][0].tobytes() == groups['costas'][0].tobytes()
    assert groups['subida'][0].tobytes() == groups['baixo'][0].tobytes()
    assert groups['subida'][4].getchannel('A').tobytes() == groups['parada'][0].getchannel('A').tobytes()

    # A pose lateral do apoio substitui a pose lateral quase igual do rolamento.
    # As células 4 em diante do apoio trazem a ponta extra do cachecol.
    timeline = [('costas', 0, 280)]
    timeline += [('patinhas', index, 130) for index in range(1, 9)]
    timeline += [('rolamento', 1, 160)]
    timeline += [('apoio', index, 160) for index in range(4)]
    timeline += [('baixo', 0, 180)]
    timeline += [('subida', index, 150) for index in range(1, 4)]
    timeline += [('parada', 0, 1000)]

    output.mkdir(parents=True, exist_ok=True)
    directory = output / 'frames'
    directory.mkdir(exist_ok=True)
    originals = output / 'referencias'
    originals.mkdir(exist_ok=True)
    for name, path in paths.items():
        (originals / f'{name}.png').write_bytes(path.read_bytes())
    ground = groups['parada'][0].getchannel('A').getbbox()[3]
    frames = []
    entries = []
    for index, (name, cell, duration) in enumerate(timeline):
        source = groups[name][cell]
        alpha = source.getchannel('A')
        left, top, right, bottom = alpha.getbbox()
        assert not any(alpha.histogram()[1:255])
        dy = ground - bottom
        frame = Image.new('RGBA', (256, 256))
        frame.paste(source, (0, dy))
        assert frame.getchannel('A').histogram() == alpha.histogram()
        assert frame.crop((left, top + dy, right, bottom + dy)).tobytes() == source.crop((left, top, right, bottom)).tobytes()
        frame_path = directory / f'frame_{index:02d}.png'
        frame.save(frame_path)
        assert read_frame(frame_path).tobytes() == frame.tobytes()
        frames.append(frame)
        entries.append({'index': index, 'source': name, 'cell': cell, 'dy': dy, 'duration_ms': duration})
    assert frames[0].tobytes() == groups['costas'][0].tobytes()
    assert frames[-1].tobytes() == groups['parada'][0].tobytes()

    durations = [entry['duration_ms'] for entry in entries]
    encoded, timings = coalesce_identical(frames, durations)
    write_apng(output / 'recuperacao_execucao_unica.png', encoded, timings, 1)
    save_gif(output / 'previa_recuperacao_512.gif', frames, durations, checkerboard(), 2)
    contact = Image.new('RGB', (5 * 256, 4 * 280), '#333333')
    draw = ImageDraw.Draw(contact)
    for index, (frame, entry) in enumerate(zip(frames, entries, strict=True)):
        background = checkerboard()
        background.alpha_composite(frame)
        x, y = index % 5 * 256, index // 5 * 280
        contact.paste(background.convert('RGB'), (x, y))
        draw.text((x + 8, y + 258), f'{index:02d} | {entry["source"]} {entry["cell"]}', fill='white')
    contact.save(output / 'contato_recuperacao.png')

    assert {name: sha(path) for name, path in paths.items()} == hashes
    result = {
        'sources': {name: str(path) for name, path in paths.items()},
        'input_sha256': hashes,
        'frame_size': [256, 256],
        'ground_y': ground,
        'frames': entries,
        'duration_ms': sum(durations),
        'final_hold_ms': durations[-1],
        'starts_on_back': True,
        'missing_segment': 'impact_to_back',
    }
    (output / 'manifest.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    with zipfile.ZipFile(output.with_suffix('.zip'), 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output.rglob('*')):
            if path.is_file():
                archive.write(path, arcname=output.name + '/' + path.relative_to(output).as_posix())
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('patinhas', 'rolamento', 'apoio', 'subida', 'costas', 'baixo', 'parada', 'output'):
        parser.add_argument('--' + key, required=True, type=Path)
    args = vars(parser.parse_args())
    output = args.pop('output')
    result = build(args, output)
    print(json.dumps({'frames': len(result['frames']), 'duration_ms': result['duration_ms']}))
