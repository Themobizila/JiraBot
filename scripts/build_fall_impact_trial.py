"""Une os dois trechos do impacto à recuperação já montada."""
import argparse
import json
from pathlib import Path
import zipfile

from PIL import Image, ImageDraw

try:
    from .build_fall_recovery_trial import read_sheet
    from .build_seated_idle_trial import checkerboard, coalesce_identical
    from .build_swing_half_comparison import save_gif, sha
    from .build_walk_stop_trial import read_frame
    from .extract_sit_pixellab import write_apng
except ImportError:
    from build_fall_recovery_trial import read_sheet
    from build_seated_idle_trial import checkerboard, coalesce_identical
    from build_swing_half_comparison import save_gif, sha
    from build_walk_stop_trial import read_frame
    from extract_sit_pixellab import write_apng


def build(hit_path, roll_path, side_path, recovery, output):
    recovery_manifest = recovery / 'manifest.json'
    recovery_entries = json.loads(recovery_manifest.read_text(encoding='utf-8'))['frames']
    recovery_paths = [recovery / 'frames' / f'frame_{entry["index"]:02d}.png'
                      for entry in recovery_entries]
    low_path = recovery / 'referencias' / 'baixo.png'
    inputs = [hit_path, roll_path, side_path, low_path, recovery_manifest, *recovery_paths]
    hashes = {str(path): sha(path) for path in inputs}
    hit = read_sheet(hit_path)
    roll = read_sheet(roll_path)
    low = read_frame(low_path)
    side = read_frame(side_path)
    recovery_frames = [read_frame(path) for path in recovery_paths]
    assert hit[0].tobytes() == low.tobytes()
    assert roll[0].tobytes() == side.tobytes()
    assert hit[5].getchannel('A').getbbox() is None and roll[5].getchannel('A').getbbox() is None
    ground = recovery_frames[0].getchannel('A').getbbox()[3]
    timeline = [('contato', 0, low, 90)]
    timeline += [('tombada', index, hit[index], duration)
                 for index, duration in enumerate((90, 90, 110), start=1)]
    timeline += [('lateral', 0, side, 130)]
    timeline += [('rolamento', index, roll[index], duration)
                 for index, duration in enumerate((130, 140, 170), start=1)]
    impact_count = len(timeline)
    timeline += [('recuperacao', entry['index'], frame, entry['duration_ms'])
                 for entry, frame in zip(recovery_entries, recovery_frames, strict=True)]

    directory = output / 'frames'
    directory.mkdir(parents=True, exist_ok=True)
    originals = output / 'referencias'
    originals.mkdir(exist_ok=True)
    for name, path in [('sheet_tombada', hit_path), ('sheet_rolamento', roll_path),
                       ('apoio_baixo', low_path), ('impacto_lateral', side_path)]:
        (originals / f'{name}.png').write_bytes(path.read_bytes())
    frames = []
    entries = []
    for index, (phase, cell, image, duration) in enumerate(timeline):
        alpha = image.getchannel('A')
        left, top, right, bottom = alpha.getbbox()
        dy = ground - bottom
        assert not any(alpha.histogram()[1:255])
        frame = Image.new('RGBA', (256, 256))
        frame.paste(image, (0, dy))
        assert frame.getchannel('A').histogram() == alpha.histogram()
        assert frame.crop((left, top + dy, right, bottom + dy)).tobytes() == image.crop((left, top, right, bottom)).tobytes()
        path = directory / f'frame_{index:02d}.png'
        frame.save(path)
        assert read_frame(path).tobytes() == frame.tobytes()
        frames.append(frame)
        entries.append({'index': index, 'phase': phase, 'source_frame': cell, 'dy': dy, 'duration_ms': duration})
    assert all(a.tobytes() == b.tobytes()
               for a, b in zip(frames[impact_count:], recovery_frames, strict=True))
    durations = [entry['duration_ms'] for entry in entries]
    encoded, timings = coalesce_identical(frames, durations)
    write_apng(output / 'impacto_e_recuperacao_execucao_unica.png', encoded, timings, 1)
    save_gif(output / 'previa_impacto_e_recuperacao_512.gif', frames, durations, checkerboard(), 2)

    contact = Image.new('RGB', (768, 840), '#333333')
    draw = ImageDraw.Draw(contact)
    for index, frame in enumerate(frames[:impact_count + 1]):
        cell = checkerboard()
        cell.alpha_composite(frame)
        x, y = index % 3 * 256, index // 3 * 280
        contact.paste(cell.convert('RGB'), (x, y))
        draw.text((x + 6, y + 257), f'{index:02d} | {entries[index]["phase"]}', fill='white')
    contact.save(output / 'contato_impacto.png')
    assert {str(path): sha(path) for path in inputs} == hashes
    result = {
        'input_sha256': hashes,
        'frame_size': [256, 256],
        'ground_y': ground,
        'impact_frames': impact_count,
        'impact_duration_ms': sum(durations[:impact_count]),
        'duration_ms': sum(durations),
        'frames': entries,
        'missing_segment': 'airborne',
    }
    (output / 'manifest.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    with zipfile.ZipFile(output.with_suffix('.zip'), 'w', zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(output.rglob('*')):
            if file.is_file():
                archive.write(file, arcname=output.name + '/' + file.relative_to(output).as_posix())
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('hit', 'roll', 'side', 'recovery', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    result = build(args.hit, args.roll, args.side, args.recovery, args.output)
    print(json.dumps({'frames': len(result['frames']), 'duration_ms': result['duration_ms'],
                      'impact_duration_ms': result['impact_duration_ms']}))
