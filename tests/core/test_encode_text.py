"""Tests for encode_text in embedding_utils — CLIP and sentence-transformer paths.

The CLIP text encoding path (encode_text with model_type="clip") was previously
untested.  These tests cover:
  - Normal CLIP path: processor → get_text_features → normalize → list
  - BaseModelOutputWithPooling unwrapping (pooler_output variant)
  - last_hidden_state unwrapping fallback
  - Unexpected return type raises TypeError
  - Sentence-transformer path (sanity check)
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _make_torch_tensor(values: list):
    """Return a real 2-D torch tensor (shape 1 x dim) containing *values*."""
    import torch

    return torch.tensor([values], dtype=torch.float32)


def _make_clip_model(text_features_tensor):
    """Return a minimal (model, processor) pair whose get_text_features returns tensor."""
    model = MagicMock()
    model.get_text_features.return_value = text_features_tensor
    processor = MagicMock()
    processor.return_value = {}
    return model, processor


# ──────────────────────────────────────────────────────────────────────────────
# CLIP path
# ──────────────────────────────────────────────────────────────────────────────


class TestEncodeTextCLIPPath:
    def test_returns_normalized_list(self):
        import torch

        from vector_inspector.core.embedding_utils import encode_text

        raw = [3.0, 4.0]  # norm = 5.0 → normalized = [0.6, 0.8]
        tensor = _make_torch_tensor(raw)
        clip_model, processor = _make_clip_model(tensor)

        with patch.object(
            torch,
            "no_grad",
            return_value=MagicMock(__enter__=lambda _s: _s, __exit__=lambda _s, *_a: None),
        ):
            result = encode_text("a cat", (clip_model, processor), "clip")

        assert isinstance(result, list)
        assert len(result) == 2
        # Verify normalization: norm should be ~1
        norm = sum(x**2 for x in result) ** 0.5
        assert abs(norm - 1.0) < 1e-5

    def test_returns_512_dim_for_clip_model(self):
        import torch

        from vector_inspector.core.embedding_utils import encode_text

        tensor = _make_torch_tensor([0.1] * 512)
        clip_model, processor = _make_clip_model(tensor)

        with patch.object(
            torch,
            "no_grad",
            return_value=MagicMock(__enter__=lambda _s: _s, __exit__=lambda _s, *_a: None),
        ):
            result = encode_text("sunset over ocean", (clip_model, processor), "clip")

        assert len(result) == 512

    def test_processor_receives_text_input(self):
        import torch

        from vector_inspector.core.embedding_utils import encode_text

        tensor = _make_torch_tensor([1.0, 0.0])
        clip_model, processor = _make_clip_model(tensor)

        with patch.object(
            torch,
            "no_grad",
            return_value=MagicMock(__enter__=lambda _s: _s, __exit__=lambda _s, *_a: None),
        ):
            encode_text("hello world", (clip_model, processor), "clip")

        processor.assert_called_once()
        call_kwargs = processor.call_args[1]
        assert call_kwargs["text"] == ["hello world"]

    def test_unwraps_pooler_output(self):
        """CLIP variants that return BaseModelOutputWithPooling (pooler_output) are handled."""
        import torch

        from vector_inspector.core.embedding_utils import encode_text

        # Simulate BaseModelOutputWithPooling-like object.
        # MagicMock(spec=[]) is not a torch.Tensor so isinstance() returns False
        # naturally — no __mro__ manipulation needed.
        fake_output = MagicMock(spec=[])
        pooled = _make_torch_tensor([1.0, 0.0])
        fake_output.pooler_output = pooled

        clip_model = MagicMock()
        clip_model.get_text_features.return_value = fake_output
        processor = MagicMock()
        processor.return_value = {}

        with patch.object(
            torch,
            "no_grad",
            return_value=MagicMock(__enter__=lambda _s: _s, __exit__=lambda _s, *_a: None),
        ):
            result = encode_text("test", (clip_model, processor), "clip")

        assert isinstance(result, list)
        assert len(result) == 2

    def test_unwraps_last_hidden_state(self):
        """CLIP variants that return last_hidden_state (no pooler_output) are handled."""
        import torch

        from vector_inspector.core.embedding_utils import encode_text

        fake_output = MagicMock(spec=[])
        # No pooler_output — use last_hidden_state[:, 0]
        hidden = torch.zeros(1, 3, 2)  # shape: (batch, seq, dim)
        hidden[0, 0, :] = torch.tensor([1.0, 0.0])
        fake_output.pooler_output = None
        fake_output.last_hidden_state = hidden

        clip_model = MagicMock()
        clip_model.get_text_features.return_value = fake_output
        processor = MagicMock()
        processor.return_value = {}

        with patch.object(
            torch,
            "no_grad",
            return_value=MagicMock(__enter__=lambda _s: _s, __exit__=lambda _s, *_a: None),
        ):
            result = encode_text("test", (clip_model, processor), "clip")

        assert isinstance(result, list)

    def test_unexpected_return_type_raises_type_error(self):
        """Completely unexpected CLIP output raises TypeError."""
        import torch

        from vector_inspector.core.embedding_utils import encode_text

        # Return a plain object with no recognized attributes
        weird_output = object()

        clip_model = MagicMock()
        clip_model.get_text_features.return_value = weird_output
        processor = MagicMock()
        processor.return_value = {}

        with (
            patch.object(
                torch,
                "no_grad",
                return_value=MagicMock(__enter__=lambda _s: _s, __exit__=lambda _s, *_a: None),
            ),
            pytest.raises(TypeError, match="CLIP get_text_features returned unexpected type"),
        ):
            encode_text("oops", (clip_model, processor), "clip")


# ──────────────────────────────────────────────────────────────────────────────
# Sentence-transformer path (sanity check)
# ──────────────────────────────────────────────────────────────────────────────


class TestEncodeTextSentenceTransformerPath:
    def test_returns_list(self):
        from vector_inspector.core.embedding_utils import encode_text

        model = MagicMock()
        model.encode.return_value = np.array([0.1, 0.2, 0.3], dtype=np.float32)

        result = encode_text("hello", model, "sentence-transformer")

        assert isinstance(result, list)
        assert result == pytest.approx([0.1, 0.2, 0.3], abs=1e-6)

    def test_passes_text_to_encode(self):
        from vector_inspector.core.embedding_utils import encode_text

        model = MagicMock()
        model.encode.return_value = np.zeros(384, dtype=np.float32)

        encode_text("my query text", model, "sentence-transformer")

        model.encode.assert_called_once_with("my query text")
