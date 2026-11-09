"""Prepara a parada quadrúpede com extremos exatos e alinhamento em pixels inteiros."""
import argparse
import json
from pathlib import Path
import zipfile

from PIL import Image, ImageDraw

try:
    from .build_seated_idle_trial import checkerboard
    from .build_swing_half_comparison import save_gif, sha
    from .extract_sit_pixellab import write_apng
except ImportError:
    from build_seated_idle_trial import checkerboard
    from build_swing_half_comparison import save_gif, sha
    from extract_sit_pixellab import write_apng


def read_frame(path):
    with Image.open(path) as image:
        if image.mode != 'RGBA' or image.size != (256, 256):
            raise ValueError(f'Esperado PNG RGBA de 256×256: {path.name}')
        return image.copy()


def build(sheet_path, walk_dir, pose_path, output):
    walk_paths = [walk_dir / f'frame_{index:02d}.png' for index in range(12)]
    inputs = [sheet_path, pose_path, *walk_paths]
    hashes = [sha(path) for path in inputs]
    walk = [read_frame(path) for path in walk_paths]
    pose = read_frame(pose_path)
    with Image.open(sheet_path) as sheet:
        if sheet.mode != 'RGBA' or sheet.size != (768, 512):
            raise ValueError('Esperada sheet RGBA de 768×512.')
        cells = []
        for index in range(6):
            x, y = index % 3 * 256, index // 3 * 256
            cells.append(sheet.crop((x, y, x + 256, y + 256)))
    assert cells[0].tobytes() == walk[-1].tobytes()
    assert cells[4].getchannel('A').tobytes() == pose.getchannel('A').tobytes()
    assert cells[5].getchannel('A').getbbox() is None

    output.mkdir(parents=True, exist_ok=True)
    originals = output / 'celulas_originais'
    frames_dir = output / 'parada'
    originals.mkdir(exist_ok=True)
    frames_dir.mkdir(exist_ok=True)
    (output / 'sheet_original.png').write_bytes(sheet_path.read_bytes())
    (output / 'pose_parada_quatro_patas.png').write_bytes(pose_path.read_bytes())
    for index, frame in enumerate(cells):
        frame.save(originals / f'frame_{index:02d}.png')

    start = walk[-1].getchannel('A').getbbox()
    end = pose.getchannel('A').getbbox()
    start_center = (start[0] + start[2]) / 2
    end_center = (end[0] + end[2]) / 2
    frames = [walk[-1]]
    offsets = [[0, 0]]
    for index, original in enumerate(cells[1:4], start=1):
        left, top, right, bottom = original.getchannel('A').getbbox()
        fraction = index / 4
        target_x = start_center + (end_center - start_center) * fraction
        target_y = start[3] + (end[3] - start[3]) * fraction
        dx = round(target_x - (left + right) / 2)
        dy = round(target_y) - bottom
        frame = Image.new('RGBA', (256, 256))
        frame.paste(original, (dx, dy))
        assert frame.getchannel('A').histogram() == original.getchannel('A').histogram()
        assert frame.crop((left + dx, top + dy, right + dx, bottom + dy)).tobytes() == original.crop((left, top, right, bottom)).tobytes()
        frames.append(frame)
        offsets.append([dx, dy])
    frames.append(pose)
    offsets.append([0, 0])

    for index, frame in enumerate(frames):
        target = frames_dir / f'frame_{index:02d}.png'
        frame.save(target)
        assert read_frame(target).tobytes() == frame.tobytes()
    durations = [160, 150, 150, 160, 1000]
    sequence = walk[:-1] + frames
    sequence_times = [200] * (len(walk) - 1) + durations
    write_apng(output / 'parada_sem_perdas.png', frames, durations, 1)
    write_apng(output / 'andar_parar_sem_perdas.png', sequence, sequence_times, 1)
    save_gif(output / 'previa_andar_parar_512.gif', sequence, sequence_times, checkerboard(), 2)
    contact = Image.new('RGB', (5 * 256, 280), '#333333')
    draw = ImageDraw.Draw(contact)
    for index, frame in enumerate(frames):
        cell = checkerboard()
        cell.alpha_composite(frame)
        contact.paste(cell.convert('RGB'), (index * 256, 0))
        draw.text((index * 256 + 8, 258), f'{index:02d} | dx={offsets[index][0]} dy={offsets[index][1]}', fill='white')
    contact.save(output / 'contato_parada.png')

    assert [sha(path) for path in inputs] == hashes
    assert sha(output / 'pose_parada_quatro_patas.png') == sha(pose_path)
    result = {
        'input_sha256': dict(zip(map(str, inputs), hashes, strict=True)),
        'frame_size': [256, 256],
        'intermediate_frames': 3,
        'offsets_xy': offsets,
        'stop_duration_ms': durations,
        'walk_stop_duration_ms': sum(sequence_times),
        'first_frame_matches_walk': True,
        'final_frame_matches_shared_pose': True,
    }
    (output / 'manifest.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    with zipfile.ZipFile(output.with_suffix('.zip'), 'w', zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(output.rglob('*')):
            if file.is_file():
                archive.write(file, arcname=output.name + '/' + file.relative_to(output).as_posix())
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ('sheet', 'walk', 'pose', 'output'):
        parser.add_argument('--' + argument, required=True, type=Path)
    args = parser.parse_args()
    result = build(args.sheet, args.walk, args.pose, args.output)
    print(json.dumps({key: result[key] for key in ('offsets_xy', 'walk_stop_duration_ms', 'first_frame_matches_walk', 'final_frame_matches_shared_pose')}))
