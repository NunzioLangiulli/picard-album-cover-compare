"""Real Qt UI tests with a simulated Picard host; no music or network writes.

Run with Python 3.12+ and PyQt6: python -B tests/test_review.py
Optionally set COVER_REVIEW_SCREENSHOT to a PNG path for the UI fixture.
"""

import hashlib
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from urllib.parse import parse_qs, urlsplit

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt6.QtCore import QByteArray, QBuffer, QEvent, QIODevice, QMimeData, QObject, QPointF, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QDropEvent, QFont, QFontDatabase, QImage, QMouseEvent
from PyQt6.QtWidgets import QApplication, QLabel, QWidget

APP = QApplication.instance() or QApplication([])
font_path = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / 'segoeui.ttf'
if font_path.is_file():
    QFontDatabase.addApplicationFont(str(font_path))
    APP.setFont(QFont('Segoe UI', 9))
ROOT = Path(__file__).resolve().parents[1]


def module(name, **values):
    result = types.ModuleType(name)
    result.__dict__.update(values)
    sys.modules[name] = result
    return result


def picture(width=800, height=800, color='#658e9c'):
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor(color))
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, 'PNG')
    return bytes(buffer.data())


class Metadata(dict):
    def __init__(self, *args, images=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.images = list(images)

    def copy(self, other):
        self.update(other)
        self.images = list(other.images)


class ImageError(Exception):
    pass


class Image:
    def __init__(self, url=None, types=None, data=None, support_types=False):
        self.url = url
        self.types = types or []
        self.support_types = support_types
        self.can_be_saved_to_metadata = True
        self.can_be_saved_to_tags = True
        self.datahash = None
        self.data = None
        self.source = str(url or 'Embedded fixture')
        if data is not None:
            self.set_data(data)

    def set_data(self, data):
        image = QImage.fromData(data)
        if image.isNull():
            raise ImageError('Unsupported image')
        self.data = data
        self.width, self.height = image.width(), image.height()
        self.datalength = len(data)
        self.mimetype = 'image/png'
        self.datahash = types.SimpleNamespace(hash=hashlib.sha256(data).hexdigest())

    def types_as_string(self, translate=False):
        return ', '.join(self.types) or 'Front'


class LocalImage(Image):
    pass


class Album(QObject):
    metadata_images_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.id = 'b67da832-4e7a-4dc7-b8c4-8fe0ef1ca21f'
        self.release_group = types.SimpleNamespace(id='d67da832-4e7a-4dc7-b8c4-8fe0ef1ca21f')
        self.metadata = Metadata(albumartist='Example Artist', album='Cover Comparison')
        self.tracks = []

    def iterfiles(self):
        return iter(file for track in self.tracks for file in track.files)


class Setter:
    calls = []

    def __init__(self, mode, image, target):
        self.image, self.target = image, target

    def set_coverart(self):
        Setter.calls.append(self.target)
        targets = [self.target]
        if isinstance(self.target, Album):
            targets += self.target.tracks + list(self.target.iterfiles())
        for target in targets:
            target.metadata.images = [i for i in target.metadata.images if i.types and 'front' not in i.types] + [self.image]
        if isinstance(self.target, Album):
            self.target.metadata_images_changed.emit()
        return True


SETTINGS = dict(save_images_to_tags=True, dont_replace_cover_of_types=False,
                dont_replace_included_types=['front'], dont_replace_with_smaller_cover=True,
                remove_images_from_tags=False, save_images_to_files=False)
module('picard')
module('picard.plugin3')
module('picard.plugin3.api', Metadata=Metadata, BaseAction=object, OptionsPage=QWidget)
module('picard.album', Album=Album)
module('picard.config', get_config=lambda: types.SimpleNamespace(setting=SETTINGS))
module('picard.coverart')
module('picard.coverart.image', CoverArtImage=Image, CoverArtImageError=ImageError, LocalFileCoverArtImage=LocalImage)
module('picard.coverart.setters', CoverArtSetter=Setter, CoverArtSetterMode=types.SimpleNamespace(REPLACE=1))
module('picard.util', imageinfo=types.SimpleNamespace(get_supported_extensions=lambda: ['.jpg', '.png', '.webp']))

spec = importlib.util.spec_from_file_location('review_plugin', ROOT / '__init__.py', submodule_search_locations=[str(ROOT)])
plugin = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = plugin
spec.loader.exec_module(plugin)
from review_plugin.review_controller import ReviewController, albums_for
from review_plugin.review_dialog import ReviewDialog
from review_plugin.review_model import album_ids, caa_candidates, exchange_url, local_images


class WebService:
    def __init__(self):
        self.requests = []

    def get_url(self, **kwargs):
        request = types.SimpleNamespace(aborted=False, kwargs=kwargs)
        self.requests.append(request)
        return request

    download_url = get_url

    def abort_task(self, request):
        request.aborted = True


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.album = Album()
        self.embedded = Image(types=['front'], data=picture(1200, 1200, '#35545c'))
        self.downloaded = Image(url='https://example.org/front.png', types=['front'], data=picture(600, 600, '#a88867'))
        self.back = Image(types=['back'], data=picture(300, 300, '#444444'))
        self.file = types.SimpleNamespace(filename=str(Path(self.temp.name) / 'track.flac'),
            metadata=Metadata(images=[self.downloaded, self.back]), orig_metadata=Metadata(images=[self.embedded, self.back]))
        self.track = types.SimpleNamespace(album=self.album, files=[self.file], metadata=Metadata(images=[self.downloaded]))
        self.file.parent_item = self.track
        self.album.tracks = [self.track]
        self.window = QWidget()
        self.window.cover_art_box = types.SimpleNamespace(item=self.album, cover_art=QLabel(self.window), orig_cover_art=QLabel(self.window))
        self.api = types.SimpleNamespace(tagger=types.SimpleNamespace(window=self.window),
            plugin_config={'click_to_compare': True, 'review_caa': False, 'review_local': True}, web_service=WebService())
        self.controller = ReviewController(self.api)
        self.dialog = ReviewDialog(self.controller, self.album)
        self.controller.dialogs[self.album] = self.dialog

    def tearDown(self):
        self.controller.disable()
        APP.processEvents()
        self.window.close()
        self.temp.cleanup()

    def test_existing_images_and_no_automatic_tag_changes(self):
        self.assertGreaterEqual(len(self.dialog.candidates), 3)
        self.assertIs(self.file.metadata.images[0], self.downloaded)
        self.assertIs(self.dialog.reference.image, self.embedded)
        self.assertEqual(self.api.web_service.requests, [])

    def test_arbitrary_filename_scan_and_no_recursion(self):
        path = Path(self.temp.name) / 'artist_album_unrelated.PNG'
        path.write_bytes(picture())
        subdir = Path(self.temp.name) / 'subfolder'
        subdir.mkdir()
        (subdir / 'cover.png').write_bytes(picture())
        self.assertEqual(list(local_images([self.file], {'.png'})), [path])
        self.dialog.refresh()
        self.assertTrue(any(c.path == str(path) for c in self.dialog.candidates))

    def test_drop_adds_candidate_without_applying(self):
        path = Path(self.temp.name) / 'my choice.png'
        path.write_bytes(picture(1500, 1400))
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(path))])
        event = QDropEvent(QPointF(10, 10), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        self.dialog.dropEvent(event)
        candidate = self.dialog.selected()
        self.assertEqual(candidate.image.width, 1500)
        self.assertIs(self.file.metadata.images[0], self.downloaded)
        self.assertIn(str(path), self.controller.extra_files[self.album])

    def test_apply_preserves_original_and_nonfront(self):
        self.controller.apply(self.album, self.embedded)
        self.assertEqual(self.file.metadata.images[-1].data, self.embedded.data)
        self.assertIn(self.back, self.file.metadata.images)
        self.assertIs(self.file.orig_metadata.images[0], self.embedded)
        self.assertIsNot(self.file.metadata.images[-1], self.embedded)
        self.file.metadata.images = [self.downloaded]
        self.controller.before_save(self.file)
        self.assertEqual(self.file.metadata.images[-1].data, self.embedded.data)

    def test_missing_original_cannot_be_applied(self):
        image = Image()
        with self.assertRaises(RuntimeError):
            self.controller.apply(self.album, image)

    def test_album_resolution(self):
        self.assertEqual(albums_for(self.file), [self.album])
        self.assertEqual(albums_for(types.SimpleNamespace(items=[self.file, self.track])), [self.album])
        self.assertEqual(albums_for(None), [])

    def test_click_opens_only_one_album_and_toggle_restores_behavior(self):
        calls = []
        self.controller.open = calls.append
        event = QMouseEvent(QEvent.Type.MouseButtonRelease, QPointF(4, 4), QPointF(4, 4),
                            Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        self.assertTrue(self.controller.eventFilter(self.window.cover_art_box.cover_art, event))
        APP.processEvents()
        self.assertEqual(calls, [self.album])
        self.api.plugin_config['click_to_compare'] = False
        self.assertFalse(self.controller.eventFilter(self.window.cover_art_box.cover_art, event))

    def test_ids_and_exchange_encoding(self):
        self.assertEqual(album_ids(self.album)[0], self.album.id)
        self.album.id = ''
        self.album.metadata['~ko_musicbrainz_albumid'] = 'b67da832-4e7a-4dc7-b8c4-8fe0ef1ca21f'
        self.assertIsNotNone(album_ids(self.album)[0])
        query = parse_qs(urlsplit(exchange_url({'albumartist': 'A & B', 'album': 'Café / #1'})).query)
        self.assertEqual(query['q'], ['A & B Café / #1'])

    def test_remote_thumbnails_never_become_applied_originals(self):
        document = {'images': [{'image': 'http://ia800407.us.archive.org/test.jpg', 'types': ['Front'],
                               'thumbnails': {'250': 'https://archive.org/thumb.jpg'}}]}
        candidate = next(caa_candidates(document, 'CAA release'))
        self.assertTrue(candidate.url.startswith('https://'))
        self.dialog.add_candidate(candidate)
        self.dialog.jobs.append((candidate, True))
        self.dialog.pump()
        request = self.api.web_service.requests[-1]
        request.kwargs['handler'](picture(250, 250), None, False)
        self.assertIsNone(candidate.image)
        self.assertFalse(candidate.thumbnail.isNull())
        self.dialog.table.selectRow(self.dialog.candidates.index(candidate))
        self.assertFalse(self.dialog.apply_button.isEnabled())
        request = self.api.web_service.requests[-1]
        request.kwargs['handler'](picture(1800, 1800), None, False)
        self.assertEqual(candidate.image.width, 1800)
        self.assertTrue(self.dialog.apply_button.isEnabled())

    def test_caa_errors_do_not_remove_other_candidates(self):
        before = len(self.dialog.candidates)
        self.dialog.fetch_caa()
        for request in list(self.api.web_service.requests):
            request.kwargs['handler'](None, types.SimpleNamespace(errorString=lambda: 'Forbidden'), True)
        self.assertEqual(len(self.dialog.candidates), before)
        self.assertIn('Forbidden', self.dialog.status.text())

    def test_close_aborts_requests_and_ignores_late_callbacks(self):
        self.dialog.fetch_caa()
        requests = list(self.api.web_service.requests)
        self.dialog.close()
        self.assertTrue(all(request.aborted for request in requests))
        for request in requests:
            request.kwargs['handler']({'images': []}, None, False)
        self.assertNotIn(self.album, self.controller.dialogs)

    def test_remove_album_clears_choice(self):
        self.controller.apply(self.album, self.embedded)
        self.controller.remove_album(self.album)
        self.assertNotIn(self.album, self.controller.choices)
        self.assertFalse(self.dialog.alive)

    def test_window_fixture(self):
        path = Path(self.temp.name) / 'artist_album_cover.png'
        path.write_bytes(picture(1800, 1800, '#7d8767'))
        self.dialog.add_path(str(path))
        self.dialog.show()
        APP.processEvents()
        self.dialog.paint_comparison()
        if os.environ.get('COVER_REVIEW_SCREENSHOT'):
            self.dialog.grab().save(os.environ['COVER_REVIEW_SCREENSHOT'])
        self.assertIn('1800', self.dialog.right.info.text())
        self.assertIn('1200', self.dialog.left.info.text())


if __name__ == '__main__':
    unittest.main(verbosity=2)
