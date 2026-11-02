"""Settings from the environment and the cold start recorder."""

from __future__ import annotations

from tel_parser import cold_start
from tel_parser.config import Settings


def test_settings_from_env_reads_values():
    env = {"TEL_MODEL_PATH": "/m.onnx", "TEL_TABLE_NAME": "stats", "TEL_MAX_IMAGE_BYTES": "1234"}
    settings = Settings.from_env(env)
    assert settings.model_path == "/m.onnx"
    assert settings.table_name == "stats"
    assert settings.max_image_bytes == 1234


def test_settings_defaults():
    settings = Settings.from_env({})
    assert settings.table_name == ""
    assert settings.max_image_bytes > 0


def test_init_recorded_once_and_cold_flag_flips():
    recorder = cold_start.ColdStartRecorder()
    first = recorder.mark_init_complete()
    assert first >= 0.0
    assert recorder.mark_init_complete() == first
    assert recorder.take_cold_flag() is True
    assert recorder.take_cold_flag() is False
