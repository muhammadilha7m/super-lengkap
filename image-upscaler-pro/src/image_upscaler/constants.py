"""Application-wide constants."""

from __future__ import annotations

APP_NAME = "Image Upscaler Pro"
APP_SHORT_NAME = "ImageUpscalerPro"
APP_VERSION = "1.0.0"

SUPPORTED_INPUT_EXTS = (
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
    ".tiff",
    ".tif",
)

OUTPUT_FORMATS = ("PNG", "JPEG", "WEBP")
OUTPUT_FORMAT_EXT = {
    "PNG": ".png",
    "JPEG": ".jpg",
    "WEBP": ".webp",
}

SCALE_PRESETS = (2, 3, 4)
DEFAULT_SCALE = 4
DEFAULT_OUTPUT_FORMAT = "PNG"
DEFAULT_JPEG_QUALITY = 95
DEFAULT_WEBP_QUALITY = 95

ENGINE_REALESRGAN = "Real-ESRGAN (AI)"
ENGINE_LANCZOS = "Lanczos (Cepat)"
ENGINE_CHOICES = (ENGINE_REALESRGAN, ENGINE_LANCZOS)
DEFAULT_ENGINE = ENGINE_LANCZOS

REALESRGAN_MODELS = (
    "realesrgan-x4plus",
    "realesrgan-x4plus-anime",
    "realesr-animevideov3",
)
DEFAULT_REALESRGAN_MODEL = "realesrgan-x4plus"

SUFFIX_TEMPLATE = "_upscaled_{scale}x"

CONFLICT_MODES = ("skip", "overwrite", "rename")
DEFAULT_CONFLICT_MODE = "rename"

JOB_STATUS_PENDING = "pending"
JOB_STATUS_RUNNING = "running"
JOB_STATUS_DONE = "done"
JOB_STATUS_FAILED = "failed"
JOB_STATUS_SKIPPED = "skipped"
JOB_STATUS_CANCELLED = "cancelled"

UI_MIN_WIDTH = 1380
UI_MIN_HEIGHT = 760
UI_DEFAULT_WIDTH = 1500
UI_DEFAULT_HEIGHT = 820
