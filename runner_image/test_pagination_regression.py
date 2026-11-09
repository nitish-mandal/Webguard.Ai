"""Trusted independent checks. This module is run ONLY in the isolated Linux image."""

import importlib.util

import pytest

spec = importlib.util.spec_from_file_location('verified_target', '/scratch/work/pagination.py')
target = importlib.util.module_from_spec(spec)
spec.loader.exec_module(target)


def test_full_first():
    assert target.page_items([1, 2, 3, 4], 0, 2) == [1, 2]


def test_full_second():
    assert target.page_items([1, 2, 3, 4], 1, 2) == [3, 4]


def test_page_size_one():
    assert target.page_items([7, 8], 1, 1) == [8]


def test_partial():
    assert target.page_items([1, 2, 3, 4, 5], 1, 3) == [4, 5]


def test_beyond_end():
    assert target.page_items([1, 2], 3, 2) == []


def test_empty():
    assert target.page_items([], 0, 2) == []


def test_negative_page():
    with pytest.raises(ValueError):
        target.page_items([1, 2], -1, 2)


def test_zero_size():
    with pytest.raises(ValueError):
        target.page_items([1, 2], 0, 0)


def test_negative_size():
    with pytest.raises(ValueError):
        target.page_items([1, 2], 0, -1)
