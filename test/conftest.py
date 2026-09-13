"""Pytest collection config for the test suite.

The ``test/end2end/`` suite is ovoscope-driven and needs the heavy e2e stack
(``ovoscope`` + a real padatious pipeline, which pulls fann2 and needs
swig/libfann system headers). It is exercised only by the dedicated ``ovoscope``
CI job (``install_extras: 'end2end'`` + ``require_padatious``).

The lightweight ``build_tests``/``coverage`` jobs install only the ``test``
extra and scan the whole ``test/`` tree, so without ovoscope present pytest
would error importing the end2end modules. Skip that directory when ovoscope is
absent so those jobs stay green; collect it when ovoscope IS installed.
"""
from importlib.util import find_spec

collect_ignore_glob = []

if find_spec("ovoscope") is None:
    collect_ignore_glob.append("end2end/*")
