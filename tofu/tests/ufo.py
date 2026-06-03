import pytest


def import_ufo():
    try:
        import gi
    except ImportError:
        return None

    try:
        gi.require_version('Ufo', '0.0')
    except ValueError:
        try:
            gi.require_version('Ufo', '1.0')
        except ValueError:
            return None

    try:
        from gi.repository import Ufo
    except ImportError:
        return None

    return Ufo


def ufo_available():
    return import_ufo() is not None


def require_ufo():
    ufo = import_ufo()
    if ufo is None:
        pytest.skip("UFO GI bindings are not available", allow_module_level=True)

    return ufo
