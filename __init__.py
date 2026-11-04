"""Independent album cover comparison for MusicBrainz Picard."""

_review = None


def enable(api):
    """Register the independent album artwork comparison interface."""
    global _review
    from .options import CoverReviewOptions, DEFAULTS
    from .review_controller import CompareCovers, ReviewController
    for name, value in DEFAULTS.items():
        api.plugin_config.register_option(name, value)
    api.register_options_page(CoverReviewOptions)
    _review = ReviewController(api)
    api.register_album_action(CompareCovers)
    api.register_track_action(CompareCovers)
    api.register_file_action(CompareCovers)
    api.register_file_pre_save_processor(before_save, priority=-1000)
    api.register_album_post_removal_processor(album_removed)


def before_save(api, file):
    if _review is not None:
        _review.before_save(file)


def album_removed(api, album):
    if _review is not None:
        _review.remove_album(album)


def disable():
    """Release resources using Picard's zero-argument lifecycle hook."""
    global _review
    if _review is not None:
        _review.disable()
        _review = None
