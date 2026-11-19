"""Compare album artwork without changing tags until the user applies a choice."""

from pathlib import Path
import hashlib
import tempfile

from PyQt6.QtCore import QBuffer, QByteArray, QEvent, QIODevice, QSize, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QIcon, QImageReader, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QFileDialog, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QMessageBox, QPushButton, QScrollArea, QSplitter,
    QSizePolicy, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from picard.coverart.image import CoverArtImage, CoverArtImageError, LocalFileCoverArtImage
from picard.util import imageinfo

from .review_model import Candidate, album_ids, caa_candidates, exchange_url, local_images


_external_images = None


def external_image_path(image):
    """Export original bytes to a session cache, never the source artwork file."""
    global _external_images
    if _external_images is None:
        _external_images = tempfile.TemporaryDirectory(prefix='picard-cover-compare-')
    data = bytes(image.data)
    suffix = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/gif': '.gif',
              'image/webp': '.webp', 'image/tiff': '.tiff', 'image/bmp': '.bmp',
              'image/avif': '.avif'}.get(image.mimetype, '.img')
    path = Path(_external_images.name) / (hashlib.sha256(data).hexdigest() + suffix)
    # Rewrite the copy in case the external viewer edited it previously.
    path.write_bytes(data)
    return path


def preview(data, size=QSize(440, 440)):
    """Decode a bounded preview while retaining the original image bytes."""
    buffer = QBuffer()
    buffer.setData(QByteArray(data))
    buffer.open(QIODevice.OpenModeFlag.ReadOnly)
    reader = QImageReader(buffer)
    dimensions = reader.size()
    if dimensions.isValid():
        reader.setScaledSize(dimensions.scaled(size, Qt.AspectRatioMode.KeepAspectRatio))
    pixmap = QPixmap.fromImage(reader.read())
    buffer.close()
    return pixmap


def details(candidate):
    lines = ['Source: ' + ', '.join(candidate.sources), 'Artwork type: ' + candidate.types]
    image = candidate.image
    if image is not None:
        width, height = image.width, image.height
        lines += [f'{width} × {height} pixels · {width * height / 1_000_000:.2f} MP',
                  f'{image.mimetype} · {image.datalength / 1024:.1f} KiB',
                  'Original image loaded']
    else:
        lines += [candidate.state, 'Original dimensions and size are not known yet.']
    if candidate.location:
        lines.append(candidate.location)
    return '\n'.join(lines)


class ImagePane(QGroupBox):
    open_requested = pyqtSignal(object)

    def __init__(self, title, parent=None):
        super().__init__(title, parent)
        layout = QVBoxLayout(self)
        self.picture = QLabel('Select an image')
        self._pixmap = None
        self._candidate = None
        self.picture.setToolTip('Double-click to open the original in your default external image viewer.')
        self.picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.picture.setMinimumSize(220, 220)
        self.picture.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        self.picture.setStyleSheet('QLabel { background: #242629; color: #eeeeee; border-radius: 4px; }')
        self.picture.installEventFilter(self)
        layout.addWidget(self.picture, 1)
        self.info = QLabel()
        self.info.setTextFormat(Qt.TextFormat.PlainText)
        self.info.setWordWrap(True)
        self.info.setMinimumWidth(0)
        self.info.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.info)

    def show_candidate(self, candidate):
        self._candidate = candidate
        self._pixmap = None
        self.picture.clear()
        if candidate is None:
            self.picture.setText('Select an image')
            self.info.clear()
            return
        data = candidate.image.data if candidate.image is not None else None
        pixmap = preview(data) if data else candidate.thumbnail
        if pixmap is not None and not pixmap.isNull():
            self._pixmap = pixmap
            self.render_pixmap()
        else:
            self.picture.setText(candidate.state)
        self.info.setText(details(candidate))

    def render_pixmap(self):
        if self._pixmap is not None:
            self.picture.setPixmap(self._pixmap.scaled(
                max(1, self.picture.width() - 12), max(1, self.picture.height() - 12),
                Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def eventFilter(self, watched, event):
        if (watched is self.picture and event.type() == QEvent.Type.MouseButtonDblClick
                and event.button() == Qt.MouseButton.LeftButton and self._candidate is not None):
            self.open_requested.emit(self._candidate)
            return True
        if watched is self.picture and event.type() == QEvent.Type.Resize:
            self.render_pixmap()
        return False


class ReviewDialog(QDialog):
    def __init__(self, controller, album):
        super().__init__(getattr(controller.api.tagger, 'window', None))
        self.controller = controller
        self.album = album
        self.alive = True
        self.candidates = []
        self.by_key = {}
        self.reference = None
        self.source_status = {}
        self.jobs = []
        self.running = 0
        self.pending = []
        self.external_pending = set()
        self.setWindowTitle('Album Cover Compare — Compare album covers')
        self.resize(1340, 820)
        self.setAcceptDrops(True)
        layout = QVBoxLayout(self)
        title = QLabel(str(album.metadata.get('albumartist', '')) + ' — ' + str(album.metadata.get('album', 'Album')))
        title.setTextFormat(Qt.TextFormat.PlainText)
        title.setWordWrap(True)
        title.setStyleSheet('font-size: 18px; font-weight: bold;')
        layout.addWidget(title)
        instructions = QLabel('Drop local images anywhere in this window to compare them. Select a candidate on the left; '
                              'use Set as reference to compare any two images. Double-click an image or a row to open its original externally. Nothing is saved automatically.')
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        toolbar = QHBoxLayout()
        layout.addLayout(toolbar)
        self.source_filter = QComboBox()
        self.source_filter.addItem('All sources')
        self.source_filter.currentTextChanged.connect(self.filter_sources)
        toolbar.addWidget(self.source_filter)
        for text, callback in [('Add local images…', self.choose_files),
                               ('Refresh sources', self.refresh),
                               ('Search Album Art Exchange ↗', self.open_exchange)]:
            button = QPushButton(text)
            button.clicked.connect(callback)
            toolbar.addWidget(button)
        toolbar.addStretch()
        splitter = QSplitter()
        layout.addWidget(splitter, 1)
        self.table = QTableWidget(0, 3)
        self.table.setMinimumWidth(420)
        self.table.setHorizontalHeaderLabels(['Source', 'Type', 'Original image'])
        self.table.setIconSize(QSize(40, 40))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().hide()
        self.table.itemSelectionChanged.connect(self.selection_changed)
        self.table.cellDoubleClicked.connect(lambda row, column: self.open_external(self.candidates[row]))
        self.table.setAcceptDrops(False)
        self.table.viewport().setAcceptDrops(False)
        splitter.addWidget(self.table)
        pane_widget = QWidget()
        panes = QHBoxLayout(pane_widget)
        self.left = ImagePane('Reference')
        self.right = ImagePane('Selected candidate')
        self.left.open_requested.connect(self.open_external)
        self.right.open_requested.connect(self.open_external)
        panes.addWidget(self.left, 1)
        panes.addWidget(self.right, 1)
        splitter.addWidget(pane_widget)
        splitter.setChildrenCollapsible(False)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([420, 900])
        self.status = QLabel()
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.saving_notice = QLabel(controller.saving_notice())
        self.saving_notice.setWordWrap(True)
        layout.addWidget(self.saving_notice)
        buttons = QHBoxLayout()
        layout.addLayout(buttons)
        self.reference_button = QPushButton('Set as reference')
        self.reference_button.clicked.connect(self.set_reference)
        buttons.addWidget(self.reference_button)
        self.zoom_button = QPushButton('View original at 100%…')
        self.zoom_button.clicked.connect(self.zoom)
        buttons.addWidget(self.zoom_button)
        buttons.addStretch()
        self.apply_button = QPushButton('Use selected cover for this album')
        self.apply_button.clicked.connect(self.apply)
        buttons.addWidget(self.apply_button)
        close_button = QPushButton('Close')
        close_button.clicked.connect(self.close)
        buttons.addWidget(close_button)
        self.finished.connect(self.closed)
        self.metadata_timer = QTimer(self)
        self.metadata_timer.setSingleShot(True)
        self.metadata_timer.setInterval(300)
        self.metadata_timer.timeout.connect(self.collect_metadata)
        album.metadata_images_changed.connect(self.schedule_metadata)
        self.refresh()

    def selected(self):
        row = self.table.currentRow()
        return self.candidates[row] if 0 <= row < len(self.candidates) else None

    def add_candidate(self, candidate):
        previous = self.by_key.get(candidate.key)
        if previous is not None:
            for source in candidate.sources:
                previous.add_source(source)
            self.update_row(previous)
            return previous
        self.by_key[candidate.key] = candidate
        self.candidates.append(candidate)
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setRowHeight(row, 72)
        for column in range(3):
            self.table.setItem(row, column, QTableWidgetItem())
        self.update_row(candidate)
        if self.reference is None and candidate.image is not None:
            self.reference = candidate
        if self.table.currentRow() < 0:
            self.table.selectRow(row)
        return candidate

    def update_row(self, candidate):
        row = self.candidates.index(candidate)
        image = candidate.image
        text = f'{image.width} × {image.height}\n{image.mimetype} · {image.datalength / 1024:.1f} KiB' if image is not None else candidate.state
        for column, value in enumerate([', '.join(candidate.sources), candidate.types, text]):
            self.table.item(row, column).setText(value)
            self.table.item(row, column).setToolTip(', '.join(candidate.sources) + '\n' + candidate.location)
        if candidate.thumbnail is not None:
            self.table.item(row, 0).setIcon(QIcon(candidate.thumbnail))
        for source in candidate.sources:
            if self.source_filter.findText(source) < 0:
                self.source_filter.addItem(source)
        self.filter_sources()

    def filter_sources(self, *_):
        source = self.source_filter.currentText()
        for row, candidate in enumerate(self.candidates):
            self.table.setRowHidden(row, source != 'All sources' and source not in candidate.sources)

    def add_image(self, image, source):
        if not image.datahash or not image.can_be_saved_to_metadata:
            return
        key = 'data:' + str(image.datahash.hash)
        if key in self.by_key:
            self.by_key[key].add_source(source)
            self.update_row(self.by_key[key])
            return
        candidate = Candidate(key, [source], str(image.source),
                              image.types_as_string(translate=False), image=image, state='Ready')
        candidate.thumbnail = preview(image.data, QSize(64, 64))
        self.add_candidate(candidate)

    def collect_metadata(self):
        if not self.alive:
            return
        files = list(self.album.iterfiles())
        for file in files:
            for image in file.orig_metadata.images:
                self.add_image(image, 'Embedded in files')
        objects = [self.album, *self.album.tracks, *files]
        for obj in objects:
            for image in obj.metadata.images:
                self.add_image(image, 'Picard current artwork')
        self.paint_comparison()

    def schedule_metadata(self):
        if self.alive:
            self.metadata_timer.start()

    def refresh(self):
        self.collect_metadata()
        if self.controller.api.plugin_config['review_local']:
            extensions = {ext.casefold() for ext in imageinfo.get_supported_extensions()}
            for path in local_images(self.album.iterfiles(), extensions):
                self.add_path(str(path), 'Local album folder')
        for path in self.controller.extra_files.get(self.album, []):
            self.add_path(path, 'Added local file')
        if self.controller.api.plugin_config['review_caa']:
            self.fetch_caa()
        self.paint_comparison()

    def add_path(self, path, source='Added local file'):
        path = str(Path(path).resolve())
        if not Path(path).is_file():
            self.notice('Not a local file: ' + path)
            return
        reader = QImageReader(path)
        if not reader.canRead():
            self.notice('Unsupported or unreadable image: ' + Path(path).name)
            return
        candidate = Candidate('path:' + path.casefold(), [source], path, 'Front', path=path)
        size = reader.size()
        if size.isValid():
            reader.setScaledSize(size.scaled(QSize(64, 64), Qt.AspectRatioMode.KeepAspectRatio))
            candidate.state = f'{size.width()} × {size.height()} · select to inspect'
        candidate.thumbnail = QPixmap.fromImage(reader.read())
        candidate = self.add_candidate(candidate)
        if source == 'Added local file':
            self.controller.remember_file(self.album, path)
            self.table.selectRow(self.candidates.index(candidate))

    def choose_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, 'Add images to compare', '',
                                               'Images (*.jpg *.jpeg *.png *.gif *.tif *.tiff *.webp *.bmp);;All files (*)')
        for path in paths:
            self.add_path(path)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            if url.isLocalFile():
                self.add_path(url.toLocalFile())
        event.acceptProposedAction()

    def open_exchange(self):
        QDesktopServices.openUrl(QUrl(exchange_url(self.album.metadata)))

    def notice(self, message):
        self.source_status['Notice'] = message
        self.status.setText('\n'.join(f'{source}: {value}' for source, value in self.source_status.items()))

    def fetch_caa(self):
        release, group = album_ids(self.album)
        for kind, identifier, source in [('release', release, 'CAA release'), ('release-group', group, 'CAA release group')]:
            if self.source_status.get(source) == 'Loading…':
                continue
            if not identifier:
                self.source_status[source] = 'No MusicBrainz identifier available.'
                continue
            self.source_status[source] = 'Loading…'
            def received(document, reply, error, source=source):
                if not self.alive:
                    return
                if error:
                    self.source_status[source] = 'Unavailable: ' + reply.errorString()
                else:
                    try:
                        candidates = list(caa_candidates(document, source))
                        self.source_status[source] = f'{len(candidates)} images found. Select one to download its original.'
                        for candidate in candidates:
                            existing = self.add_candidate(candidate)
                            if existing is candidate and candidate.thumbnail_url:
                                self.jobs.append((candidate, True))
                        self.pump()
                    except (TypeError, ValueError, AttributeError) as exc:
                        self.source_status[source] = 'Invalid response: ' + str(exc)
                self.notice('Images are candidates until you choose Apply.')
            request = self.controller.api.web_service.get_url(
                url=f'https://coverartarchive.org/{kind}/{identifier}/', handler=received,
                parse_response_type='json', priority=False, important=False)
            self.pending.append(request)
        self.notice('Local images and embedded artwork remain available if a remote source fails.')

    def ensure_original(self, candidate):
        if candidate is None or candidate.image is not None or candidate.loading:
            return
        if candidate.path:
            try:
                image = LocalFileCoverArtImage(candidate.path, types=['front'], support_types=True)
                image.set_data(Path(candidate.path).read_bytes())
                candidate.image = image
                candidate.state = 'Ready'
                if self.reference is None:
                    self.reference = candidate
            except (OSError, CoverArtImageError) as exc:
                candidate.state = 'Cannot load image: ' + str(exc)
            self.update_row(candidate)
        elif candidate.url:
            candidate.loading = True
            candidate.state = 'Downloading original…'
            self.update_row(candidate)
            self.jobs.insert(0, (candidate, False))
            self.pump()

    def pump(self):
        while self.alive and self.jobs and self.running < 3:
            candidate, thumbnail = self.jobs.pop(0)
            self.running += 1
            def received(data, reply, error, candidate=candidate, thumbnail=thumbnail):
                self.running -= 1
                if not self.alive:
                    return
                if not thumbnail:
                    candidate.loading = False
                try:
                    if error:
                        if not thumbnail:
                            candidate.state = 'Download failed: ' + reply.errorString()
                    elif thumbnail:
                        candidate.thumbnail = preview(bytes(data), QSize(440, 440))
                    else:
                        candidate.image = CoverArtImage(url=candidate.url, data=bytes(data))
                        candidate.state = 'Ready'
                        candidate.thumbnail = preview(candidate.image.data, QSize(440, 440))
                except (CoverArtImageError, OSError, ValueError) as exc:
                    if not thumbnail:
                        candidate.state = 'Cannot read original: ' + str(exc)
                self.update_row(candidate)
                self.paint_comparison()
                if not thumbnail and candidate.key in self.external_pending:
                    self.external_pending.discard(candidate.key)
                    if candidate.image is not None:
                        self.open_external(candidate)
                    else:
                        self.notice('Could not open original externally: ' + candidate.state)
                self.pump()
            self.pending.append(self.controller.api.web_service.download_url(
                url=candidate.thumbnail_url if thumbnail else candidate.url,
                handler=received, priority=not thumbnail, important=False))

    def selection_changed(self):
        self.ensure_original(self.selected())
        self.paint_comparison()

    def paint_comparison(self):
        candidate = self.selected()
        self.left.show_candidate(self.reference)
        self.right.show_candidate(candidate)
        ready = candidate is not None and candidate.image is not None
        self.apply_button.setEnabled(ready)
        self.zoom_button.setEnabled(ready)
        self.reference_button.setEnabled(ready)

    def set_reference(self):
        self.reference = self.selected()
        self.paint_comparison()

    def open_external(self, candidate):
        if not self.alive or candidate is None:
            return
        if candidate.image is None:
            self.external_pending.add(candidate.key)
            self.ensure_original(candidate)
            if candidate.image is None:
                if candidate.loading:
                    self.notice('Downloading the original image before opening it externally…')
                else:
                    self.external_pending.discard(candidate.key)
                    self.notice('Could not open original externally: ' + candidate.state)
                return
            self.external_pending.discard(candidate.key)
        try:
            path = external_image_path(candidate.image)
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
                self.notice('Could not open the default image viewer. Temporary image: ' + str(path))
        except (OSError, CoverArtImageError) as exc:
            self.notice('Could not open original externally: ' + str(exc))

    def zoom(self):
        candidate = self.selected()
        if candidate is None or candidate.image is None:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle('Original image — 100% pixels')
        dialog.resize(900, 750)
        layout = QVBoxLayout(dialog)
        scroll = QScrollArea()
        picture = QLabel()
        pixmap = QPixmap()
        pixmap.loadFromData(candidate.image.data)
        picture.setPixmap(pixmap)
        scroll.setWidget(picture)
        layout.addWidget(scroll)
        dialog.exec()

    def apply(self):
        candidate = self.selected()
        if candidate is None or candidate.image is None:
            return
        try:
            self.controller.apply(self.album, candidate.image)
            self.notice('Selected front cover applied to this album. Save the files in Picard when ready.')
            self.saving_notice.setText(self.controller.saving_notice())
        except (CoverArtImageError, OSError, RuntimeError) as exc:
            QMessageBox.warning(self, 'Could not apply cover', str(exc))

    def closeEvent(self, event):
        self.closed()
        super().closeEvent(event)

    def closed(self, *_):
        if not self.alive:
            return
        self.alive = False
        self.metadata_timer.stop()
        self.jobs.clear()
        self.external_pending.clear()
        for request in self.pending:
            self.controller.api.web_service.abort_task(request)
        try:
            self.album.metadata_images_changed.disconnect(self.schedule_metadata)
        except (RuntimeError, TypeError):
            pass
        self.controller.dialogs.pop(self.album, None)
        self.deleteLater()
