"""Export the glyph classifier to ONNX with a dynamic batch, then quantise.

Usage::

    python -m tel_parser.model.export_onnx --weights model/glyphs.pt \
        --fp32 model/glyphs_fp32.onnx --int8 model/glyphs_int8.onnx

Dynamic int8 quantisation stores weights as int8 and quantises
activations at run time. It needs no calibration set.
"""

from __future__ import annotations

import argparse
from typing import Any

from . import GLYPH_SIZE

INPUT_NAME = "glyphs"
OUTPUT_NAME = "logits"


def export(model: Any, out_path: str) -> None:
    """Write an fp32 ONNX graph whose batch dimension is dynamic."""
    import torch

    model.eval()
    example = torch.zeros(2, 1, GLYPH_SIZE, GLYPH_SIZE)
    torch.onnx.export(
        model,
        (example,),
        out_path,
        input_names=[INPUT_NAME],
        output_names=[OUTPUT_NAME],
        dynamic_shapes=({0: "batch"},),
        dynamo=True,
        external_data=False,
    )


def quantise(fp32_path: str, int8_path: str) -> None:
    """Apply dynamic int8 weight quantisation."""
    from onnxruntime.quantization import QuantType, quantize_dynamic

    quantize_dynamic(fp32_path, int8_path, weight_type=QuantType.QInt8)


def main() -> None:
    import torch

    from .net import build_model

    parser = argparse.ArgumentParser(description="Export and quantise the glyph classifier.")
    parser.add_argument("--weights", required=True)
    parser.add_argument("--fp32", default="model/glyphs_fp32.onnx")
    parser.add_argument("--int8", default="model/glyphs_int8.onnx")
    args = parser.parse_args()

    model = build_model()
    model.load_state_dict(torch.load(args.weights, map_location="cpu", weights_only=True))
    export(model, args.fp32)
    quantise(args.fp32, args.int8)
    print(f"wrote {args.fp32} and {args.int8}")


if __name__ == "__main__":
    main()
