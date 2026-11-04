"""Exercise Picard's actual loader with isolated settings and no audio files."""

import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, QEvent
from picard import config
import picard.options
from picard.plugin3.plugin import Plugin
from picard.ui.coverartbox.coverartthumbnail import CoverArtThumbnail


class ThumbnailFixture(QObject):
    """Use Picard's actual image equality without its unrelated rendering setup."""

    __eq__ = CoverArtThumbnail.__eq__

    def __init__(self, data=None):
        super().__init__()
        self.data = data
        self.current_pixmap_key = None


class LifecycleTests(unittest.TestCase):
    def test_load_enable_disable(self):
        app = QApplication.instance() or QApplication([])
        first = ThumbnailFixture()
        second = ThumbnailFixture()
        app.window = SimpleNamespace(cover_art_box=SimpleNamespace(
            cover_art=first, orig_cover_art=second, item=None))
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix='picard-lifecycle-') as tmp:
            config.setup_config(app, str(Path(tmp) / 'settings.ini'))
            plugin = Plugin(root.parent, root.name)
            plugin.read_manifest()
            module = plugin.load_module()
            plugin.enable(app)
            controller = module._review
            self.assertIsNotNone(controller)
            self.assertEqual(len(controller.widgets), 2)
            self.assertIs(controller.widgets[0], first)
            self.assertIs(controller.widgets[1], second)
            controller.attach()
            self.assertEqual(len(controller.widgets), 2)
            for data in (None, b'', b'same artwork'):
                first.data = second.data = data
                self.assertFalse(controller.eventFilter(second, QEvent(QEvent.Type.User)))
                unrelated = ThumbnailFixture(data)
                self.assertFalse(controller.eventFilter(unrelated, QEvent(QEvent.Type.User)))
            plugin.disable()
            self.assertIsNone(module._review)
            self.assertFalse(controller.attach_timer.isActive())


if __name__ == '__main__':
    unittest.main(verbosity=2)
