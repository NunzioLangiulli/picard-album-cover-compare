# Changelog

## 1.0.1

- Fix the zero-argument disable hook required by Picard 3.0.2 and release the controller reference after cleanup.
- Fix installation with empty cover thumbnails (`object of type 'NoneType' has no len()`). Track thumbnail widgets by identity rather than invoking Picard's image-content equality. Apply the same fix to click filtering, including identical artwork in separate widgets.
- Add a lifecycle regression check using Picard's actual plugin loader and thumbnail equality with empty and populated image data.

## 1.0.0

- Extract the album cover comparison from Cover Art From Hidden Tags 1.2.0 into an independent plugin.
- Use a new plugin UUID, independent settings and the Album Cover Compare display name.
- Retain thumbnail-click access, local file drops, side-by-side previews, technical details, CAA candidates, Album Art Exchange search and explicit album cover selection.
- Preserve native save protections and session-only choices.
- Include isolated Qt tests and optional tests against actual Picard 3.0.2 components.
