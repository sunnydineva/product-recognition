"""Offline contract tests; no model downloads or product images required."""

from io import BytesIO
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dinov2_encoder as encoder


class EncoderTests(unittest.TestCase):
    def test_jpeg_and_png_are_decoded_as_rgb(self):
        for image_format, mode in [("JPEG", "L"), ("PNG", "RGBA")]:
            with self.subTest(format=image_format):
                data = BytesIO()
                Image.new(mode, (8, 8)).save(data, format=image_format)
                image = encoder._read_image(data.getvalue())
                self.assertEqual(image.mode, "RGB")
                self.assertEqual(image.size, (8, 8))

    def test_invalid_images_raise_clear_error(self):
        data = BytesIO()
        Image.new("RGB", (8, 8)).save(data, format="GIF")
        for source in [b"broken image", data.getvalue(), "/missing/image.jpg"]:
            with self.subTest(source=source):
                with self.assertRaises(encoder.InvalidImageError):
                    encoder._read_image(source)

    def test_embedding_contract_and_model_reuse(self):
        class Model(torch.nn.Module):
            config = SimpleNamespace(hidden_size=3)

            def forward(self, **kwargs):
                self_test.assertFalse(self.training)
                self_test.assertFalse(torch.is_grad_enabled())
                return SimpleNamespace(
                    last_hidden_state=torch.tensor([[[3., 4., 0.], [0., 0., 1.]]])
                )

        self_test = self
        data = BytesIO()
        Image.new("RGB", (8, 8)).save(data, format="PNG")
        with patch.object(encoder.AutoModel, "from_pretrained", return_value=Model()) as load, \
             patch.object(encoder.AutoImageProcessor, "from_pretrained", return_value=lambda **kw: {}), \
             patch.object(encoder, "_encoder", None):
            shared = encoder.get_encoder()
            self.assertIs(shared, encoder.get_encoder())
            for _ in range(2):
                vector = shared.encode(data.getvalue())
                self.assertEqual(vector.shape, (3,))
                self.assertEqual(vector.dtype, np.float32)
                self.assertTrue(vector.flags.c_contiguous)
                np.testing.assert_allclose(vector, [0.6, 0.8, 0.], atol=1e-6)
            load.assert_called_once()


if __name__ == "__main__":
    unittest.main()
