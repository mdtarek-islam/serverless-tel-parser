# syntax=docker/dockerfile:1
# Build stage: install runtime wheels against the Lambda base image so the
# compiled libraries match its glibc. Quantise only when an fp32 model is
# present and no int8 model exists. Nothing is exported at build time.
FROM public.ecr.aws/lambda/python:3.12 AS build
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --target /opt/deps -r requirements.txt
COPY model/ ./model/
RUN mkdir -p /opt/model \
 && if [ ! -f model/glyphs_int8.onnx ] && [ -f model/glyphs_fp32.onnx ]; then \
      pip install --no-cache-dir --target /opt/quant onnx \
      && PYTHONPATH=/opt/deps:/opt/quant python -c "from onnxruntime.quantization import QuantType, quantize_dynamic; quantize_dynamic('model/glyphs_fp32.onnx', 'model/glyphs_int8.onnx', weight_type=QuantType.QInt8)"; \
    fi \
 && if [ -f model/glyphs_int8.onnx ]; then cp model/glyphs_int8.onnx /opt/model/; \
    else echo "warning: no model/glyphs_int8.onnx; the handler will return 503"; fi

# Runtime stage: base image already provides boto3.
FROM public.ecr.aws/lambda/python:3.12
COPY --from=build /opt/deps ${LAMBDA_TASK_ROOT}
COPY --from=build /opt/model ${LAMBDA_TASK_ROOT}/model
COPY src/tel_parser ${LAMBDA_TASK_ROOT}/tel_parser
ENV TEL_MODEL_PATH=/var/task/model/glyphs_int8.onnx \
    PYTHONDONTWRITEBYTECODE=1
CMD ["tel_parser.handler.handler"]
