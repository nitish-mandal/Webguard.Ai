import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location(
    "demo_pagination", Path(__file__).resolve().parents[1] / "pagination.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_first_page_contains_requested_count():
    assert module.page_items([10, 20, 30, 40], 0, 2) == [10, 20]


def test_invalid_page_rejected():
    with pytest.raises(ValueError):
        module.page_items([10], -1, 2)
