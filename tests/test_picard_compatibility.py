"""Optional compatibility checks against an installed/importable Picard source.

Requires Picard 3.0.2 and its Python dependencies on PYTHONPATH. Uses actual
Picard metadata, images, setters and save filters with simulated album/file
objects. Does not start Picard, access the network or save audio files.
"""

from contextlib import nullcontext
import importlib.util
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt6.QtCore import QBuffer, QIODevice
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QApplication

from picard import config
from picard.album import Album
from picard.coverart.image import CoverArtImage
from picard.coverart.processing.filters import filter_image_for_file
from picard.file import File
from picard.metadata import Metadata
from picard.track import Track


APP = QApplication.instance() or QApplication([])
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('compat_plugin', ROOT / '__init__.py', submodule_search_locations=[str(ROOT)])
plugin = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = plugin
spec.loader.exec_module(plugin)
from compat_plugin.review_controller import ReviewController


def image(size, kind='front'):
    pixels = QImage(size, size, QImage.Format.Format_RGB32)
    pixels.fill(0x336688)
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    pixels.save(buffer, 'PNG')
    return CoverArtImage(types=[kind], support_types=True, data=bytes(buffer.data()))


class CompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.settings = {'save_images_to_tags': True, 'dont_replace_cover_of_types': False,
                         'dont_replace_included_types': ['front'], 'dont_replace_with_smaller_cover': True,
                         'remove_images_from_tags': False, 'save_images_to_files': False}
        config.config = SimpleNamespace(setting=self.settings)
        self.album = Mock(spec=Album)
        self.album._new_tracks = None
        self.album.suspend_metadata_images_update = nullcontext()
        self.album.metadata = Metadata({'album': 'Synthetic album'})
        self.album.orig_metadata = Metadata({'album': 'Synthetic album'})
        self.file = Mock(spec=File)
        self.file.metadata = Metadata({'title': 'Synthetic track'})
        self.file.orig_metadata = Metadata({'title': 'Synthetic track'})
        self.track = Mock(spec=Track)
        self.track.album = self.album
        self.track.metadata = Metadata({'title': 'Synthetic track'})
        self.file.parent_item = self.track
        self.album.tracks = [self.track]
        self.album.iterfiles.return_value = [self.file]
        self.controller = ReviewController(SimpleNamespace(tagger=SimpleNamespace(window=None)))

    def tearDown(self):
        self.controller.disable()

    def test_real_setter_replaces_front_preserves_back_and_original(self):
        original, back, selected = image(1000), image(400, 'back'), image(1400)
        self.file.orig_metadata.images.extend([original, back])
        self.file.metadata.images.extend([original, back])
        self.controller.apply(self.album, selected)
        self.assertEqual(len(self.file.metadata.images), 2)
        self.assertIn(back, self.file.metadata.images)
        self.assertEqual(self.file.metadata.images[-1].data, selected.data)
        self.assertIs(self.file.orig_metadata.images[0], original)
        self.assertIsNot(self.file.metadata.images[-1], selected)
        self.assertTrue(self.file.metadata.images[-1].is_front_image())

    def test_native_protection_accepts_original_rejects_smaller_candidate(self):
        original = image(1600)
        self.file.orig_metadata.images.append(original)
        self.controller.apply(self.album, image(600))
        candidate = self.file.metadata.images[-1]
        self.assertFalse(filter_image_for_file(candidate, self.file.orig_metadata.images))
        self.controller.apply(self.album, original)
        self.assertTrue(filter_image_for_file(self.file.metadata.images[-1], self.file.orig_metadata.images))

    def test_real_presave_setter_reasserts_choice(self):
        chosen = image(1200)
        self.controller.apply(self.album, chosen)
        self.file.metadata.images.clear()
        self.file.metadata.images.append(image(500))
        self.controller.before_save(self.file)
        self.assertEqual(self.file.metadata.images[0].data, chosen.data)

    def test_native_setting_names(self):
        self.assertIn('larger', self.controller.saving_notice())
        self.settings['save_images_to_tags'] = False
        self.assertIn('disabled', self.controller.saving_notice())
        self.settings.update(save_images_to_files=True, remove_images_from_tags=True)
        self.assertIn('remove it from audio tags', self.controller.saving_notice())


if __name__ == '__main__':
    unittest.main(verbosity=2)
