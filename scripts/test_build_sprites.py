"""Regressões do recorte verde 12x8, detalhes internos e 480 PNGs reais."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np
from PIL import Image, ImageDraw

from scripts.build_sprites import (ACTIONS, THEMES, FRAME_COUNT, clean_cell,
    detect_grid, cell_bounds, stabilize, validate_output, source_for)


class ExtractionTests(unittest.TestCase):
    def cell(self):
        image = Image.new("RGB", (100, 100), (0, 255, 0))
        draw = ImageDraw.Draw(image)
        draw.rectangle((25, 22, 77, 83), fill=(145, 92, 49), outline=(25, 18, 18), width=3)
        draw.rectangle((35, 35, 53, 52), fill=(55, 180, 45), outline=(20, 20, 20), width=3)
        draw.rectangle((59, 35, 70, 44), fill=(240, 240, 230), outline=(20, 20, 20), width=2)
        return np.asarray(image).copy()

    def test_external_green_removed_but_green_detail_white_and_outline_remain(self):
        result, meta = clean_cell(self.cell())
        self.assertEqual(result.getpixel((0, 0))[3], 0)
        for point in ((43, 43), (64, 40), (25, 50), (60, 70)):
            self.assertEqual(result.getpixel(point)[3], 255)
        self.assertEqual(result.getpixel((43, 43))[:3], (55, 180, 45))
        self.assertGreater(meta["green_detail_pixels_preserved"], 0)

    def island_cell(self, neon_pixels):
        rgb = self.cell()
        rgb[55:69, 35:49] = (20, 20, 20)
        interior = np.tile(np.array([55, 180, 45], dtype=np.uint8), (10, 10, 1))
        interior.reshape(-1, 3)[:neon_pixels] = (0, 255, 0)
        rgb[57:67, 37:47] = interior
        return rgb

    def test_internal_hole_requires_strictly_more_than_85_percent_neon(self):
        kept, _ = clean_cell(self.island_cell(85))
        removed, meta = clean_cell(self.island_cell(90))
        self.assertEqual(kept.getpixel((40, 60))[3], 255)
        self.assertEqual(removed.getpixel((40, 60))[3], 0)
        self.assertEqual(removed.getpixel((35, 60))[3], 255)
        self.assertTrue(all(island["neon_fraction"] > .85 for island in meta["internal_islands"]))

    def test_despill_keeps_alpha_and_changes_only_one_pixel_boundary(self):
        rgb = self.cell()
        rgb[50, 25] = (90, 110, 100)
        rgb[60, 60] = (90, 110, 100)
        result, _ = clean_cell(rgb)
        self.assertEqual(result.getpixel((25, 50)), (90, 95, 100, 255))
        self.assertEqual(result.getpixel((60, 60)), (90, 110, 100, 255))

    def test_existing_transparency_is_preserved(self):
        rgba = np.dstack((self.cell(), np.full((100, 100), 255, np.uint8)))
        rgba[60, 60, 3] = 0
        result, _ = clean_cell(rgba)
        self.assertEqual(result.getpixel((60, 60))[3], 0)

    def test_despill_also_treats_opaque_pixels_at_cell_edge(self):
        rgb = self.cell()
        rgb[0:10, 30:50] = (90, 110, 100)
        result, _ = clean_cell(rgb)
        self.assertEqual(result.getpixel((40, 0)), (90, 95, 100, 255))

    def test_anchor_and_common_scale(self):
        cells = []
        for action in ("idle", "swing"):
            for index, (x, y) in enumerate(((5, 10), (25, 20))):
                image = Image.new("RGBA", (80, 90))
                ImageDraw.Draw(image).rectangle((x, y, x + 30, y + 50), fill="brown")
                cells.append(("normal", action, index, image, {}))
        result, _ = stabilize(cells, 128)
        self.assertEqual(result[0][3].tobytes(), result[1][3].tobytes())
        self.assertEqual(result[2][3].tobytes(), result[3][3].tobytes())
        self.assertEqual(result[0][3].getchannel("A").getbbox()[3], 124)
        self.assertEqual(result[2][3].getchannel("A").getbbox()[1], 0)

    def test_source_formats_alias_and_ambiguity(self):
        with TemporaryDirectory() as temp:
            base = Path(temp)
            for index, suffix in enumerate((".JPG", ".jpeg", ".PNG", ".webp")):
                folder = base / str(index)
                folder.mkdir()
                file = folder / ("anonovo" + suffix)
                file.touch()
                self.assertEqual(source_for(folder, "ano_novo"), file)
            (base / "0" / "ano_novo.png").touch()
            with self.assertRaises(ValueError):
                source_for(base / "0", "ano_novo")

    def test_real_grid_detects_12_rows_excluding_header_and_labels(self):
        for theme in THEMES:
            with Image.open(source_for("assets/raw_sheets", theme)) as image:
                rgb = np.asarray(image.convert("RGB"))
                xs, ys = detect_grid(rgb)
                self.assertEqual((len(xs), len(ys)), (9, 13))
                self.assertGreater(xs[0], image.width * .1)
                self.assertGreater(ys[0], image.height * .07)
                x0, y0, x1, y1 = cell_bounds(rgb, xs, ys, 0, 0)
                self.assertTrue(xs[0] < x0 < x1 < xs[1])
                self.assertTrue(ys[0] < y0 < y1 < ys[1])

    def test_explicit_grid_uses_twelve_rows(self):
        xs, ys = detect_grid(np.zeros((300, 400, 3), np.uint8), (40, 24, 360, 288))
        self.assertEqual((len(xs), len(ys)), (9, 13))
        self.assertEqual((xs[0], xs[-1], ys[0], ys[-1]), (40, 360, 24, 288))

    def test_all_480_pngs_transparent_aligned_and_not_cut(self):
        verified = validate_output(Path("assets/sprites"), 160)
        self.assertEqual(len(verified), len(THEMES) * len(ACTIONS))
        self.assertEqual(sum(v["frames"] for v in verified), 480)
        self.assertEqual(FRAME_COUNT, 16)


if __name__ == "__main__":
    unittest.main()
