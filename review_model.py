"""Album identity and candidate helpers without UI dependencies."""

from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlencode, urlsplit, urlunsplit
from uuid import UUID


def valid_id(value):
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        return None


def album_ids(album):
    metadata = album.metadata
    release = valid_id(getattr(album, 'id', None))
    group = valid_id(getattr(getattr(album, 'release_group', None), 'id', None))
    for tag, existing in [('musicbrainz_albumid', release), ('musicbrainz_releasegroupid', group)]:
        value = existing or valid_id(metadata.get(tag)) or valid_id(metadata.get('~ko_' + tag))
        if tag == 'musicbrainz_albumid':
            release = value
        else:
            group = value
    return release, group


def exchange_url(metadata):
    query = ' '.join(str(metadata.get(tag, '')).strip() for tag in ('albumartist', 'album')).strip()
    return 'https://www.albumartexchange.com/covers?' + urlencode({'q': query})


def image_url(value):
    """Accept HTTP artwork URLs and upgrade Internet Archive links to HTTPS."""
    parts = urlsplit(str(value or ''))
    if parts.scheme not in ('http', 'https') or not parts.hostname:
        return None
    if parts.hostname == 'archive.org' or parts.hostname.endswith('.archive.org'):
        parts = parts._replace(scheme='https')
    return urlunsplit(parts)


def local_images(files, extensions):
    """Find images next to matched files, regardless of name; do not recurse."""
    folders = sorted({Path(file.filename).parent for file in files}, key=str)
    for folder in folders:
        try:
            paths = sorted(folder.iterdir(), key=lambda p: p.name.casefold())
        except OSError:
            continue
        for path in paths:
            if path.is_file() and path.suffix.casefold() in extensions:
                yield path


@dataclass(eq=False)
class Candidate:
    key: str
    sources: list = field(default_factory=list)
    location: str = ''
    types: str = 'Unknown'
    image: object = None
    path: str = ''
    url: str = ''
    thumbnail_url: str = ''
    thumbnail: object = None
    state: str = 'Select to load original'
    loading: bool = False

    def add_source(self, source):
        if source not in self.sources:
            self.sources.append(source)


def caa_candidates(document, source):
    for entry in document.get('images', []):
        url = image_url(entry.get('image'))
        if not url:
            continue
        thumbs = entry.get('thumbnails') or {}
        types = ', '.join(entry.get('types') or []) or ('Front' if entry.get('front') else 'Unknown')
        yield Candidate(
            key='url:' + url, sources=[source], location=url, types=types, url=url,
            thumbnail_url=image_url(thumbs.get('250') or thumbs.get('small')) or '',
        )
