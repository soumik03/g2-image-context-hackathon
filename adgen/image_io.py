"""Local image handling: reference input, output decoding, size enforcement, saving."""

import base64
import binascii
import hashlib
import io
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from adgen.errors import FinalizationError, OutputProcessingError, SpecError

REFERENCE_MIME_TYPES = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}
FORMAT_EXTENSIONS = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}


@dataclass(frozen=True)
class ReferenceImage:
    raw: bytes  # original file bytes, sent to Gemini unmodified
    mime_type: str
    sha256: str
    size: tuple[int, int]

    def to_input_part(self) -> dict:
        """Explicit multimodal image input for the Interactions API."""
        return {
            "type": "image",
            "mime_type": self.mime_type,
            "data": base64.b64encode(self.raw).decode("ascii"),
        }


def load_reference_image(path: Path) -> ReferenceImage:
    """Read and validate the reference image before any API call."""
    try:
        raw = Path(path).read_bytes()
    except OSError as e:
        raise SpecError(f"Cannot read reference image {path}: {e}") from None
    try:
        with Image.open(io.BytesIO(raw)) as img:
            fmt, size = img.format, img.size
            img.verify()
    except (UnidentifiedImageError, OSError, SyntaxError) as e:
        raise SpecError(f"Reference image is not a valid image: {path} ({e})") from None
    if fmt not in REFERENCE_MIME_TYPES:
        raise SpecError(
            f"Unsupported reference image format {fmt!r}; use one of {sorted(REFERENCE_MIME_TYPES)}."
        )
    return ReferenceImage(
        raw=raw,
        mime_type=REFERENCE_MIME_TYPES[fmt],
        sha256=hashlib.sha256(raw).hexdigest(),
        size=size,
    )


@dataclass(frozen=True)
class ProcessedImage:
    data: bytes  # bytes to save
    format: str  # Pillow format name, e.g. "JPEG"
    raw_size: tuple[int, int]
    saved_size: tuple[int, int]
    downscaled: bool

    @property
    def extension(self) -> str:
        return FORMAT_EXTENSIONS.get(self.format, "." + self.format.lower())


def decode_base64_image(data: str) -> bytes:
    try:
        return base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError, TypeError) as e:
        raise OutputProcessingError(f"Returned image data is not valid base64: {e}") from None


def enforce_long_edge(raw: bytes, max_long_edge: int) -> ProcessedImage:
    """Decode the image; if its long edge exceeds the limit, resize proportionally.

    Images already within the limit are returned byte-for-byte unchanged.
    """
    try:
        with Image.open(io.BytesIO(raw)) as img:
            img.load()
            fmt, (w, h) = img.format, img.size
            if max(w, h) <= max_long_edge:
                return ProcessedImage(raw, fmt, (w, h), (w, h), downscaled=False)
            scale = max_long_edge / max(w, h)
            new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
            resized = img.resize(new_size, Image.Resampling.LANCZOS)
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as e:
        raise OutputProcessingError(f"Returned image could not be decoded: {e}") from None

    buf = io.BytesIO()
    save_kwargs = {"quality": 95} if fmt in ("JPEG", "WEBP") else {}
    try:
        resized.save(buf, format=fmt, **save_kwargs)
    except (OSError, ValueError, KeyError) as e:
        raise OutputProcessingError(f"Resized image could not be encoded as {fmt}: {e}") from None
    return ProcessedImage(buf.getvalue(), fmt, (w, h), new_size, downscaled=True)


_rename = os.replace  # module-level hook so tests can simulate a locked directory


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finalize_dir(tmp_dir: Path, target_dir: Path) -> str:
    """Move a completed temp directory into place. Returns the method used: "rename" or "copy".

    A directory rename can fail on Windows when OneDrive, antivirus or an indexer holds a handle
    (WinError 5). Fallback: create target_dir, copy every file and verify its SHA-256, then remove
    the temp directory (best effort). If the fallback also fails, raise FinalizationError and keep
    the temp directory with all completed artifacts. No step is retried.
    """
    tmp_dir, target_dir = Path(tmp_dir), Path(target_dir)
    try:
        _rename(tmp_dir, target_dir)
        return "rename"
    except OSError as e:
        rename_error = f"{type(e).__name__}: {e}"
    try:
        target_dir.mkdir(exist_ok=False)
        for src in sorted(tmp_dir.iterdir()):
            if not src.is_file():
                raise OSError(f"unexpected non-file entry {src.name}")
            dst = target_dir / src.name
            shutil.copyfile(src, dst)
            if _file_sha256(dst) != _file_sha256(src):
                raise OSError(f"copy verification failed for {src.name}")
    except OSError as e:
        raise FinalizationError(
            f"Could not finalize {target_dir.name}: rename failed ({rename_error}); copy fallback failed "
            f"({type(e).__name__}: {e}). Completed artifacts are preserved in {tmp_dir.name}."
        ) from None
    shutil.rmtree(tmp_dir, ignore_errors=True)  # leftovers are harmless; the verified copy is authoritative
    return "copy"


def save_run(run_dir: Path, image: ProcessedImage, metadata: dict) -> tuple[Path, Path]:
    """Write image + metadata into a temp dir, then move it into place (finalize_dir).

    A successful run directory therefore always contains both files. A write failure leaves no run
    directory behind; a finalization failure raises FinalizationError and keeps the temp directory.
    """
    run_dir = Path(run_dir)
    if run_dir.exists():
        raise OutputProcessingError(f"Output directory already exists: {run_dir}")
    tmp_dir = run_dir.with_name(run_dir.name + ".tmp")
    image_name = "ad" + image.extension
    try:
        tmp_dir.mkdir(parents=True, exist_ok=False)
        (tmp_dir / image_name).write_bytes(image.data)
        (tmp_dir / "metadata.json").write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise OutputProcessingError(f"Could not save output to {run_dir}: {e}") from None
    finalize_dir(tmp_dir, run_dir)
    return run_dir / image_name, run_dir / "metadata.json"
