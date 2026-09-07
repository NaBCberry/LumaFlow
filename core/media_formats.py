from pathlib import Path


VIDEO_EXTENSIONS = (
    ".mp4",
    ".avi",
    ".mov",
    ".mkv",
    ".wmv",
    ".flv",
    ".webm",
    ".m4v",
    ".mpg",
    ".mpeg",
    ".ts",
    ".mts",
    ".m2ts",
)

AUDIO_EXTENSIONS = (
    ".mp3",
    ".wav",
    ".flac",
    ".m4a",
    ".aac",
    ".ogg",
    ".opus",
    ".wma",
    ".aiff",
    ".aif",
    ".alac",
)

SUPPORTED_MEDIA_EXTENSIONS = VIDEO_EXTENSIONS + AUDIO_EXTENSIONS


def is_audio_file(file_path: str) -> bool:
    return Path(file_path).suffix.lower() in AUDIO_EXTENSIONS
