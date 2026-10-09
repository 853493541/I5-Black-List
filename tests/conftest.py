"""Shared test setup."""

import gc

import pytest


@pytest.fixture(autouse=True)
def _free_windows():
    """Destroy each test's windows when the test ends, at a quiet moment.

    Left to the garbage collector, a closed window from an earlier test is destroyed
    whenever a collection happens to run: in the middle of a later test's Qt call, or
    after QApplication is gone at exit. Either one crashes the test run.
    """
    yield
    gc.collect()
