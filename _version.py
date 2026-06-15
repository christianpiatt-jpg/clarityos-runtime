"""Single source of truth for the ClarityOS backend version (CL-13).

The /health endpoint, the ``/`` service manifest, and the version-lock tests
all import ``__version__`` from here, so a release bump is a one-line change and
the locks can never silently drift again (OPFOR-6 / the 4.23→4.25 lock drift
that motivated this module).
"""
__version__ = "4.26"
