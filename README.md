# Album Cover Compare

Compare album covers from your music files, local folders and the Cover Art Archive in one window, then choose which image to use in MusicBrainz Picard.

**Version:** 1.0.1 · **Author:** Borunzio · **License:** MIT

**Compatibility target:** MusicBrainz Picard 3.0.2

## Why use it?

An album may already contain a good embedded cover, while Picard finds a different image online. Album Cover Compare brings those choices together so you can inspect them before saving. You can also drop in a cover you downloaded yourself, compare any two candidates side by side, and inspect the original at 100%.

**Selecting or adding a candidate does not change your files.** Applying a cover updates Picard's pending metadata; writing it to your audio files still requires **Save** in Picard.

## Features

- Open the comparison by clicking either artwork thumbnail in Picard, or use the album, track or file context menu.
- Compare embedded artwork, current Picard artwork, local images and Cover Art Archive candidates.
- Find supported images beside matched audio files regardless of their filenames.
- Drag and drop local images into the comparison, or add them with a file picker.
- Compare two images side by side and change the reference image at any time.
- Inspect original dimensions, megapixels, image format, file size and source location.
- Open a scrollable view of the original image at 100%.
- Search Album Art Exchange in your browser using the album artist and title.
- Apply a selected original image as the album's front cover while retaining non-front artwork in Picard's metadata.
- Respect Picard's existing embedding and artwork replacement settings.

## Requirements

- MusicBrainz Picard **3.0.2**, using its version 3 plugin system. Picard 2.x is not supported.
- An album matched in Picard, with its audio files attached.
- Internet access and valid release identifiers for Cover Art Archive retrieval. Embedded and local images can be compared offline.

Image support depends on the formats available in your Picard installation. The plugin uses internal Picard interfaces, so compatibility with other Picard versions must be checked separately.

**No other plugin is required.** Album Cover Compare works independently of Cover Art From Hidden Tags, Keep Only Tags and the regular artwork provider queue.

## Installation

### From GitHub

Once this repository is published:

1. Open **Options → Plugins → Install Plugin** in Picard.
2. Choose the repository URL installation option and paste this GitHub repository's URL.
3. Select the **v1.0.1** release tag when choosing a reference.
4. Complete installation, enable the plugin and restart Picard.

Use a release tag for a versioned installation. Installing from `main` can make Picard display the branch name instead of a release version. If the release tag is missing, the repository owner must publish it first.

### From a local Git repository

Choose **Local repository** in the installation dialog, select this repository's root folder, and select **v1.0.1**. Keep the `.git` directory: a folder extracted from GitHub's **Download ZIP** is not a Git repository.

For updates, select the newer published release reference and restart Picard. Plugin settings remain associated with the same plugin identity.

## Quick start

1. Match an album in Picard and select the album or one of its matched tracks/files.
2. Click either thumbnail in Picard's cover-art panel. Alternatively, right-click the album, track or file and choose **Plugins → Compare album covers…**.
3. Select a candidate from the list. It appears beside the reference image, initially embedded artwork when available.
4. To compare another pair, select an image and click **Set as reference**, then select the other image.
5. Drop a local image into the window or choose **Add local images…** if your preferred cover is missing.
6. Inspect the technical details and, if useful, choose **View original at 100%…**.
7. Click **Use selected cover for this album** to apply your choice in Picard.
8. Review the result and **Save** in Picard when ready.

The click shortcut opens one matched album at a time. Ambiguous selections retain Picard's existing click behavior, and right-click menus remain available. Adding a candidate or setting a reference does not apply it.

## Available sources

| Source | What it includes |
| --- | --- |
| Embedded artwork | Original images from all matched audio files, including different covers within the same album. Identical image content is grouped. |
| Current Picard artwork | Images already present in Picard's album, track or file metadata, including artwork downloaded by other enabled providers. |
| Local album folders | Supported image files directly beside the matched audio files, regardless of filename. For multi-disc albums, each folder containing matched files is checked. |
| Manually added images | Local files added by drag and drop or the file picker. |
| Cover Art Archive release | Images associated with the matched MusicBrainz release. |
| Cover Art Archive release group | Images returned by the release group's Cover Art Archive endpoint. |

Local discovery does not recursively search subfolders or parent folders. Images elsewhere can be added manually. It does not change the filename expression used by Picard's regular Local Files provider.

Use the source filter to narrow the list. **Refresh sources** rescans for candidates without discarding images already available in the current review. A failed online source does not remove embedded or local candidates.

### Online images and original quality

The comparison queries the Cover Art Archive independently of Picard's normal provider queue, allowing you to see alternatives even when Picard has already found a front cover. It retrieves candidates for the matched release and its release group; it does not search every edition of an album.

Remote thumbnails are previews. Selecting a remote candidate downloads its original before it can be applied. Original dimensions are shown when available, rather than presenting thumbnail dimensions as the original's. Closing the window cancels outstanding comparison requests.

The plugin does not resize or re-encode CAA originals. Larger dimensions alone do not guarantee a better cover: use the previews and original view to assess image quality. There is no automatic ranking or automatic selection of the largest image.

### Album Art Exchange

**Search Album Art Exchange ↗** opens a browser search using the album artist and album title. Download your preferred cover yourself, then drag the local file into the comparison window.

This is a search shortcut, not an Album Art Exchange downloader. It does not log in, scrape results or bypass the site's access requirements. Search availability depends on the website.

### Other providers and hidden identifiers

Artwork already downloaded by providers such as fanart.tv can appear under current Picard artwork. The plugin does not perform its own fanart.tv search.

For CAA requests, the plugin first uses identifiers from the matched album, then standard metadata IDs, then hidden Keep Only Tags IDs when available. It does not restore identifiers into writable audio tags. Keep Only Tags and Cover Art From Hidden Tags are optional.

## Options

Open **Options → Plugins → Album Cover Compare**. The page displays the plugin version and author.

| Option | Default | Effect |
| --- | --- | --- |
| Open album cover comparison when clicking an artwork thumbnail | Enabled | Opens the comparison from Picard's cover-art panel. Disable it to retain the normal thumbnail click behavior and use the context menu instead. |
| Retrieve Cover Art Archive candidates when opening or refreshing the comparison | Enabled | Fetches release and release-group candidates for the comparison. |
| Find all supported images in the matched audio files' folders, regardless of name | Enabled | Includes images beside matched audio files without a filename constraint. |

These settings apply to the comparison window. They do not configure or disable Picard's regular artwork providers. Manual image addition remains available when automatic local discovery is disabled.

## Applying and saving covers

**Use selected cover for this album** sets the selected image as **front** on the album, tracks and matched files in Picard. This applies even if the candidate was originally labelled as another artwork type. Existing non-front artwork is retained in Picard's metadata, and original file metadata is not changed by the comparison itself.

The selected front cover is remembered for the loaded album and reasserted before saving its matched files. Removing the album or disabling the plugin clears this remembered choice. Manually added paths and choices are session-only; they are not restored after restarting Picard. Disabling the plugin does not undo metadata changes already applied.

Picard's save settings determine what is written:

| Picard setting | Effect on saving |
| --- | --- |
| Save cover images to tags | Must be enabled to embed the chosen cover in audio files. |
| Never replace cover images with smaller ones | Can preserve an existing larger image of the same type in an individual file. |
| Protection for existing artwork types | Can keep an existing front cover instead of replacing it. |
| Export artwork and remove images from tags | Can leave audio files without embedded artwork; disable removal if you want to keep covers embedded. |

The comparison window shows a notice about relevant save restrictions. It does not override these protections, so the chosen cover may not replace every file's existing artwork. This plugin does not provide bulk extraction or resizing.

## Troubleshooting

| Problem | What to check |
| --- | --- |
| Installation fails with `object of type 'NoneType' has no len()` in `CoverArtThumbnail.__eq__` | Install **v1.0.1** or newer. Version 1.0.1 fixes the thumbnail comparison that triggered this error. |
| Clicking artwork opens MusicBrainz | Enable the thumbnail-click option and select one matched album. You can also use the context-menu action. |
| A local image is missing | Enable local discovery and check that the image is directly beside a matched audio file. Otherwise add it manually. |
| CAA candidates are missing | Check Internet access, release identifiers and the CAA option. Local comparison remains available. |
| Original dimensions are unknown or Apply is unavailable | Select the candidate and wait for the original to load. Failed downloads and unsupported originals cannot be applied. |
| The existing embedded cover remains after saving | Check Picard's embedding, protected artwork type and larger-image settings. |
| Picard shows `main` as the version | Install a published release tag rather than the branch. |

For a bug report, include the plugin and Picard versions, operating system, reproduction steps and the relevant **View Error/Debug Log** excerpt. On Windows, open the log with **Ctrl+G** after reproducing the issue. Remove personal information from paths before sharing. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Migration from Cover Art From Hidden Tags 1.2.0

The comparison interface originally appeared in the combined Cover Art From Hidden Tags 1.2.0 plugin. It is now maintained separately.

1. Update Cover Art From Hidden Tags to **1.2.1** or a later provider-only version.
2. Install Album Cover Compare separately and restart Picard.
3. Review this plugin's options; they use separate settings and start with the defaults above.

Do not run the combined 1.2.0 plugin alongside Album Cover Compare, because both handle artwork clicks. Keep the provider-only plugin enabled if you need its hidden-ID CAA providers. Session-only choices from the combined plugin are not migrated.

## Development and validation

The implementation and compatibility tests target the official Picard **3.0.2** source. The 1.0.1 checks comprise **18 passing tests**:

| Test file | Coverage |
| --- | --- |
| `tests/test_review.py` | 13 tests using real Qt widgets, synthetic images and a simulated Picard host/web service: local discovery, drops, comparison, source errors, downloads, click handling and album choices. |
| `tests/test_picard_compatibility.py` | 4 tests using actual Picard metadata, images, cover setters and save filters with simulated album/file containers. |
| `tests/test_lifecycle.py` | 1 lifecycle test using Picard's loader and thumbnail equality implementation, including empty artwork, distinct widgets with identical content, repeated attachment and disable cleanup. |

Run each test file in a separate process:

```sh
python -B tests/test_review.py
python -B tests/test_picard_compatibility.py
python -B tests/test_lifecycle.py
```

The UI tests require Python 3.12+ and PyQt6. The compatibility and lifecycle tests additionally require the Picard 3.0.2 source and its dependencies on Python's import path. Tests do not download live artwork or write audio files. Set `COVER_REVIEW_SCREENSHOT` to a PNG path to capture the synthetic UI fixture.

Automated checks do not establish end-to-end validation in the installed application. Live installation, remote downloads and saving disposable audio copies remain manual checks, including behavior with native artwork protections enabled and disabled.

For contributions and publication instructions, see [CONTRIBUTING.md](CONTRIBUTING.md). Release changes are listed in [CHANGELOG.md](CHANGELOG.md).

## License

Copyright Borunzio. Released under the [MIT License](LICENSE).

This is an independent community plugin, not an official MusicBrainz Picard component. Imported Picard components retain their upstream licensing terms.
