"""Burn a persistent 「AI生成」 badge onto a finished MP4 before upload."""

from __future__ import annotations

import os
import shutil
import subprocess

_BADGE_PATH = os.path.join(
    os.path.dirname(__file__), "assets", "ai_generated_badge.png"
)


def apply_ai_generated_label(file_path: str) -> None:
    """Overlay the AI-generated badge on the full duration of ``file_path``."""
    if not file_path or not os.path.isfile(file_path):
        raise ValueError("视频后处理失败，找不到待标记的视频文件")
    if not os.path.isfile(_BADGE_PATH):
        raise ValueError("视频后处理失败，缺少 AI 生成标记素材")

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise ValueError(
            "视频后处理失败，未能写入 AI 生成标记（请确认服务器已安装 ffmpeg）"
        )

    width, height = _video_size(file_path)
    short_side = min(width, height) or 720
    badge_h = max(48, int(short_side * 0.072))
    if badge_h % 2:
        badge_h += 1
    margin = max(24, int(short_side * 0.04))

    tmp_path = file_path + ".ai_label.tmp.mp4"
    backup_path = file_path + ".pre_label.bak"
    shutil.copy2(file_path, backup_path)
    try:
        proc = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                file_path,
                "-i",
                _BADGE_PATH,
                "-filter_complex",
                (
                    f"[1:v]scale=-1:{badge_h}:flags=lanczos,format=rgba[badge];"
                    f"[0:v][badge]overlay={margin}:{margin}[v]"
                ),
                "-map",
                "[v]",
                "-map",
                "0:a?",
                "-c:v",
                "libx264",
                "-profile:v",
                "main",
                "-level",
                "4.0",
                "-pix_fmt",
                "yuv420p",
                "-preset",
                "veryfast",
                "-crf",
                "20",
                "-c:a",
                "copy",
                "-movflags",
                "+faststart",
                tmp_path,
            ],
            capture_output=True,
            check=False,
            timeout=600,
        )
        if (
            proc.returncode != 0
            or not os.path.isfile(tmp_path)
            or os.path.getsize(tmp_path) < 1024
        ):
            err = (
                proc.stderr[-400:].decode("utf-8", errors="replace")
                if proc.stderr
                else ""
            )
            raise ValueError(
                f"视频后处理失败，未能写入 AI 生成标记：{err or proc.returncode}"
            )

        os.replace(tmp_path, file_path)
        if not _is_decodable(ffmpeg, file_path):
            shutil.copy2(backup_path, file_path)
            raise ValueError("视频后处理失败，AI 生成标记写入后视频无法播放")
        print(
            f"[ai-label] applied {badge_h}px badge at ({margin},{margin}) "
            f"on {width}x{height}: {file_path}"
        )
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        if os.path.exists(backup_path):
            try:
                os.remove(backup_path)
            except OSError:
                pass


def _video_size(file_path: str) -> tuple[int, int]:
    from pymediainfo import MediaInfo

    info = MediaInfo.parse(file_path)
    for track in info.tracks:
        if track.track_type == "Video":
            width = int(track.width or 0)
            height = int(track.height or 0)
            if width and height:
                return width, height
    raise ValueError("视频后处理失败，无法读取视频尺寸")


def _is_decodable(ffmpeg: str, file_path: str) -> bool:
    proc = subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-i",
            file_path,
            "-frames:v",
            "1",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        check=False,
        timeout=120,
    )
    return proc.returncode == 0
