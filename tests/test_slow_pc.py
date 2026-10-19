"""tools/slow_pc.py: the slow-PC stand-in's own arithmetic (its runs time real checks, too slow for the suite)."""

import importlib.util
import os
import sys
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location("slow_pc", Path(__file__).resolve().parents[1] / "tools" / "slow_pc.py")
slow_pc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(slow_pc)


def test_cpu_lists_read_like_the_command_line():
    assert slow_pc.parse_cpus("2-9,14-17") == [2, 3, 4, 5, 6, 7, 8, 9, 14, 15, 16, 17]
    assert slow_pc.parse_cpus("5") == [5]


def test_a_frame_counts_as_late_when_it_misses_its_sixtieth_of_a_second():
    log = [(0.00, True, 0.0), (0.02, True, 0.01), (0.03, False, 0.02), (0.05, False, 0.04), (0.07, True, 0.05)]
    assert slow_pc.on_time(log, 0.0, 0.06) == 50.0  # two of the four frames in the window came on time
    assert slow_pc.cpu_between(log, 0.0, 0.06) == pytest.approx(0.04)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows CPU sets")
def test_the_slowest_cpus_are_distinct_cpus_of_this_pc():
    cpus = slow_pc.slowest_cpus(2)
    assert len(cpus) == len(set(cpus)) == min(2, os.cpu_count() or 1)
    assert all(0 <= cpu < (os.cpu_count() or 1) for cpu in cpus)
