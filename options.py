"""Options for the album artwork comparison window."""

from pathlib import Path
import tomllib

from PyQt6.QtWidgets import QCheckBox, QLabel, QVBoxLayout
from picard.plugin3.api import OptionsPage

DEFAULTS = {'click_to_compare': True, 'review_caa': True, 'review_local': True}


class CoverReviewOptions(OptionsPage):
    NAME = 'album_cover_compare'
    TITLE = 'Album Cover Compare'
    PARENT = 'plugins'

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        info = tomllib.loads(Path(__file__).with_name('MANIFEST.toml').read_text(encoding='utf-8'))
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Album Cover Compare {info['version']} | Author: Borunzio"))
        self.controls = {}
        for key, title in [('click_to_compare', 'Open album cover comparison when clicking an artwork thumbnail'),
                           ('review_caa', 'Retrieve Cover Art Archive candidates when opening or refreshing the comparison'),
                           ('review_local', 'Find all supported images in the matched audio files\' folders, regardless of name')]:
            control = QCheckBox(title)
            self.controls[key] = control
            layout.addWidget(control)
        for text in [
            'You can also open the window from an album, track or file: Plugins > Compare album covers… '
            'Drop local files into the window to add candidates. Select an image and choose Use selected cover for this album.',
            'The comparison shows embedded artwork, Picard current artwork, local images, and CAA release/release-group candidates. '
            'CAA originals download when selected. Source errors do not remove other candidates. The browser search link sends '
            'the album artist and album title to Album Art Exchange; it does not download from that site.',
            'Applying changes the front image in Picard only. Save files when ready. Existing non-front artwork is preserved. '
            'Picard embedding and replacement settings still apply, including protection for larger embedded images. '
            'Choices and manually added paths last for the loaded album in this session; removing the album clears them.',
            'This plugin works independently of the normal artwork providers and does not restore identifiers into '
            'writable music tags. It can use matched album IDs or hidden Keep Only Tags IDs.',
        ]:
            label = QLabel(text)
            label.setWordWrap(True)
            layout.addWidget(label)
        layout.addStretch()

    def load(self):
        for key, control in self.controls.items():
            control.setChecked(self.api.plugin_config[key])

    def save(self):
        for key, control in self.controls.items():
            self.api.plugin_config[key] = control.isChecked()

    def restore_defaults(self):
        for key, control in self.controls.items():
            control.setChecked(DEFAULTS[key])
