"""Tests for array_utils.has_embedding."""

from vector_inspector.utils.array_utils import has_embedding


def test_none_returns_false():
    assert has_embedding(None) is False


def test_empty_list_returns_false():
    assert has_embedding([]) is False


def test_nonempty_list_returns_true():
    assert has_embedding([0.1, 0.2]) is True


def test_single_zero_element_returns_true():
    assert has_embedding([0.0]) is True


def test_fallback_object_without_len_truthy():
    """Object with no __len__ falls through to bool() → True."""

    class NoLen:
        pass

    assert has_embedding(NoLen()) is True


def test_fallback_integer_zero_returns_false():
    """int has no __len__; bool(0) is False so returns False."""
    assert has_embedding(0) is False


def test_fallback_bool_raises_valueerror_returns_true():
    """Object whose bool() raises ValueError → fallback returns True."""

    class Ambiguous:
        def __bool__(self):
            raise ValueError("ambiguous truth")

    assert has_embedding(Ambiguous()) is True


def test_len_raises_exception_falls_through_to_bool():
    """Object with __len__ that raises → except branch hit; bool() used instead."""

    class RaisesLen:
        def __len__(self):
            raise RuntimeError("no len")

        def __bool__(self):
            return True

    assert has_embedding(RaisesLen()) is True
