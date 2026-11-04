"""Reversible Picard UI integration and album-level artwork choices."""

from weakref import WeakKeyDictionary

from PyQt6.QtCore import QEvent, QObject, QTimer, Qt
from PyQt6.QtWidgets import QMessageBox

from picard.album import Album
from picard.config import get_config
from picard.coverart.image import CoverArtImage
from picard.coverart.setters import CoverArtSetter, CoverArtSetterMode
from picard.plugin3.api import BaseAction


def albums_for(item):
    """Resolve albums from an album, track, file or aggregate selection."""
    if isinstance(item, Album):
        return [item]
    album = getattr(item, 'album', None)
    if isinstance(album, Album):
        return [album]
    parent = getattr(item, 'parent_item', None)
    if parent is not None and parent is not item:
        return albums_for(parent)
    albums = []
    for child in getattr(item, 'items', []):
        for album in albums_for(child):
            if album not in albums:
                albums.append(album)
    return albums


class ReviewController(QObject):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self.active = True
        self.dialogs = {}
        self.extra_files = WeakKeyDictionary()
        self.choices = WeakKeyDictionary()
        self.widgets = []
        self.box = None
        self.attach_timer = QTimer(self)
        self.attach_timer.setInterval(1000)
        self.attach_timer.timeout.connect(self.attach)
        self.attach_timer.start()
        self.attach()

    def attach(self):
        if not self.active:
            return
        window = getattr(self.api.tagger, 'window', None)
        box = getattr(window, 'cover_art_box', None)
        if box is None:
            return
        self.box = box
        for name in ('cover_art', 'orig_cover_art'):
            widget = getattr(box, name, None)
            # Picard thumbnails compare image data in __eq__, not widget identity.
            if widget is not None and not any(widget is existing for existing in self.widgets):
                widget.installEventFilter(self)
                self.widgets.append(widget)
        self.attach_timer.stop()

    def eventFilter(self, watched, event):
        if (self.active and self.api.plugin_config['click_to_compare']
                and any(watched is widget for widget in self.widgets)
                and event.type() == QEvent.Type.MouseButtonRelease
                and event.button() == Qt.MouseButton.LeftButton):
            albums = albums_for(self.box.item)
            if len(albums) == 1:
                album = albums[0]
                QTimer.singleShot(0, lambda: self.open(album) if self.active else None)
                return True
        return False

    def open(self, album):
        if not self.active:
            return
        if album not in self.dialogs:
            from .review_dialog import ReviewDialog
            self.dialogs[album] = ReviewDialog(self, album)
        dialog = self.dialogs[album]
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def remember_file(self, album, path):
        paths = self.extra_files.setdefault(album, [])
        if path not in paths:
            paths.append(path)

    def apply(self, album, source):
        if not source.can_be_saved_to_metadata or not source.can_be_saved_to_tags:
            raise RuntimeError('This image cannot be embedded. Choose an original raster image.')
        data = source.data
        if not data:
            raise RuntimeError('The original image is no longer available. Reload it before applying.')
        # A fresh front image avoids changing the type of embedded or CAA source objects.
        image = CoverArtImage(data=data, types=['front'], support_types=True)
        if not CoverArtSetter(CoverArtSetterMode.REPLACE, image, album).set_coverart():
            raise RuntimeError('Picard could not apply this image to the album.')
        self.choices[album] = image

    def before_save(self, file):
        if not self.active:
            return
        albums = albums_for(file)
        image = self.choices.get(albums[0]) if len(albums) == 1 else None
        if image is not None:
            # Reassert an explicit choice if a later provider or Lookup replaced it.
            CoverArtSetter(CoverArtSetterMode.REPLACE, image, file).set_coverart()

    def saving_notice(self):
        settings = get_config().setting
        if settings['remove_images_from_tags'] and settings['save_images_to_files']:
            return 'Picard is configured to export artwork and remove it from audio tags. Disable Remove images from tags to keep an embedded cover.'
        if not settings['save_images_to_tags']:
            return 'Embedding is disabled in Picard. Enable Save cover images to tags to write the selected cover into audio files.'
        if settings['dont_replace_cover_of_types'] and 'front' in settings['dont_replace_included_types']:
            return 'Picard is set to keep existing embedded artwork. Its save settings can retain it instead of this choice.'
        if settings['dont_replace_with_smaller_cover']:
            return 'Picard will keep a larger existing image of the same type when saving. Pixel dimensions do not guarantee visual quality.'
        return 'Save in Picard to write the choice. Other artwork types are kept. Pixel dimensions do not guarantee visual quality.'

    def remove_album(self, album):
        dialog = self.dialogs.get(album)
        if dialog:
            dialog.close()
        self.extra_files.pop(album, None)
        self.choices.pop(album, None)

    def disable(self):
        self.active = False
        self.attach_timer.stop()
        for dialog in list(self.dialogs.values()):
            dialog.close()
        for widget in self.widgets:
            try:
                widget.removeEventFilter(self)
            except RuntimeError:
                pass
        self.widgets.clear()
        self.choices.clear()
        self.extra_files.clear()


class CompareCovers(BaseAction):
    NAME = 'Compare album covers…'
    TITLE = NAME

    def callback(self, items):
        from . import _review
        albums = []
        for item in items:
            for album in albums_for(item):
                if album not in albums:
                    albums.append(album)
        if not albums:
            QMessageBox.information(None, 'Compare album covers', 'Select a matched album or one of its tracks first.')
        for album in albums:
            _review.open(album)
