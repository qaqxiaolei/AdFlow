"""
Move MP4 ``moov`` atom before ``mdat`` (faststart) for progressive mobile playback.

Does not re-encode. If the file is already faststart or not a relocatable MP4,
returns False and leaves the file unchanged.
"""

from __future__ import annotations

import os
import shutil
import struct
import tempfile
from typing import BinaryIO


def _read_atom_header(fh: BinaryIO) -> tuple[int, bytes, int] | None:
    """Return (header_size, atom_type, atom_size) or None at EOF."""
    start = fh.tell()
    header = fh.read(8)
    if len(header) < 8:
        return None
    size, atom_type = struct.unpack(">I4s", header)
    header_size = 8
    if size == 1:
        ext = fh.read(8)
        if len(ext) < 8:
            return None
        size = struct.unpack(">Q", ext)[0]
        header_size = 16
    elif size == 0:
        fh.seek(0, os.SEEK_END)
        size = fh.tell() - start
        fh.seek(start + 8)
    return header_size, atom_type, size


def _iter_top_level_atoms(path: str) -> list[tuple[bytes, int, int]]:
    """List (type, offset, size) for top-level atoms."""
    atoms: list[tuple[bytes, int, int]] = []
    with open(path, "rb") as fh:
        file_size = fh.seek(0, os.SEEK_END)
        fh.seek(0)
        while fh.tell() < file_size:
            offset = fh.tell()
            parsed = _read_atom_header(fh)
            if parsed is None:
                break
            header_size, atom_type, size = parsed
            if size < header_size:
                break
            atoms.append((atom_type, offset, size))
            fh.seek(offset + size)
    return atoms


def _patch_chunk_offsets(moov: bytearray, delta: int) -> None:
    """Walk moov children and add delta to stco/co64 entries."""
    stack = [(8, len(moov))]  # skip outer moov header
    while stack:
        start, end = stack.pop()
        i = start
        while i + 8 <= end:
            size = struct.unpack(">I", moov[i : i + 4])[0]
            atom_type = bytes(moov[i + 4 : i + 8])
            if size < 8 or i + size > end:
                break
            if atom_type == b"stco" and size >= 16:
                count = struct.unpack(">I", moov[i + 12 : i + 16])[0]
                pos = i + 16
                for _ in range(count):
                    if pos + 4 > i + size:
                        break
                    offset = struct.unpack(">I", moov[pos : pos + 4])[0]
                    moov[pos : pos + 4] = struct.pack(
                        ">I", (offset + delta) & 0xFFFFFFFF
                    )
                    pos += 4
            elif atom_type == b"co64" and size >= 16:
                count = struct.unpack(">I", moov[i + 12 : i + 16])[0]
                pos = i + 16
                for _ in range(count):
                    if pos + 8 > i + size:
                        break
                    offset = struct.unpack(">Q", moov[pos : pos + 8])[0]
                    moov[pos : pos + 8] = struct.pack(">Q", offset + delta)
                    pos += 8
            elif atom_type in (
                b"trak",
                b"mdia",
                b"minf",
                b"stbl",
                b"udta",
                b"meta",
                b"moov",
            ):
                stack.append((i + 8, i + size))
            i += size


def _is_mp4_decodable(file_path: str) -> bool:
    """Return True if ffmpeg can decode at least one video frame."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return True
    import subprocess

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


def apply_mp4_faststart(file_path: str) -> bool:
    """
    Rewrite ``file_path`` so ``moov`` comes before ``mdat``.

    Returns True if the file was rewritten; False if skipped or failed.
    Only uses ffmpeg — the pure-Python relocator corrupts MP4s that contain
    uuid/free atoms between moov and mdat (common from Seedance / Lavf).
    """
    if not file_path or not os.path.isfile(file_path):
        return False

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print(f"[faststart] skipped (ffmpeg not installed): {file_path}")
        return False

    backup_path = file_path + ".pre_faststart.bak"
    out_path = file_path + ".faststart.tmp.mp4"
    try:
        import subprocess

        shutil.copy2(file_path, backup_path)
        proc = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                file_path,
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                out_path,
            ],
            capture_output=True,
            check=False,
            timeout=300,
        )
        if (
            proc.returncode == 0
            and os.path.isfile(out_path)
            and os.path.getsize(out_path) > 1024
        ):
            os.replace(out_path, file_path)
            if not _is_mp4_decodable(file_path):
                shutil.copy2(backup_path, file_path)
                print(f"[faststart] output not decodable, restored backup: {file_path}")
                return False
            print(f"[faststart] ffmpeg rewritten: {file_path}")
            return True
        if os.path.exists(out_path):
            os.remove(out_path)
        err_tail = ""
        if proc.stderr:
            err_tail = proc.stderr[-400:].decode("utf-8", errors="replace")
        print(
            "[faststart] ffmpeg failed, keeping original file: "
            f"{err_tail or proc.returncode}"
        )
    except Exception as exc:
        if os.path.exists(out_path):
            try:
                os.remove(out_path)
            except OSError:
                pass
        if os.path.isfile(backup_path):
            shutil.copy2(backup_path, file_path)
        print(f"[faststart] error, keeping/restored original: {exc}")
    finally:
        if os.path.exists(backup_path):
            try:
                os.remove(backup_path)
            except OSError:
                pass

    return False


def _apply_mp4_faststart_python(file_path: str) -> bool:
    atoms = _iter_top_level_atoms(file_path)
    if not atoms:
        return False

    moov_atom = next((a for a in atoms if a[0] == b"moov"), None)
    mdat_atom = next((a for a in atoms if a[0] == b"mdat"), None)
    if moov_atom is None or mdat_atom is None:
        return False

    # Already faststart
    if moov_atom[1] < mdat_atom[1]:
        print(f"[faststart] already ok: {file_path}")
        return False

    with open(file_path, "rb") as fh:
        pieces: list[tuple[bytes, bytes]] = []
        for atom_type, offset, size in atoms:
            fh.seek(offset)
            pieces.append((atom_type, fh.read(size)))

    # New order: ftyp (if any), moov, then remaining atoms in original order
    ftyp_bytes = next((data for t, data in pieces if t == b"ftyp"), b"")
    moov_bytes = bytearray(next(data for t, data in pieces if t == b"moov"))
    rest = [data for t, data in pieces if t not in (b"ftyp", b"moov")]

    old_mdat_offset = mdat_atom[1]
    new_mdat_offset = len(ftyp_bytes) + len(moov_bytes)
    delta = new_mdat_offset - old_mdat_offset
    if delta != 0:
        _patch_chunk_offsets(moov_bytes, delta)

    dir_name = os.path.dirname(file_path) or "."
    fd, tmp_path = tempfile.mkstemp(suffix=".mp4", dir=dir_name)
    try:
        with os.fdopen(fd, "wb") as out:
            if ftyp_bytes:
                out.write(ftyp_bytes)
            out.write(moov_bytes)
            for data in rest:
                out.write(data)
        os.replace(tmp_path, file_path)
        print(f"[faststart] python rewritten: {file_path}")
        return True
    except Exception:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


def _probe_video_codec(file_path: str) -> str:
    try:
        from pymediainfo import MediaInfo

        media_info = MediaInfo.parse(file_path)
        for track in media_info.tracks:
            if track.track_type == "Video":
                return str(track.format or track.codec_id or "").lower()
    except Exception as exc:
        print(f"[codec] probe failed ({file_path}): {exc}")
    return ""


def transcode_mp4_to_h264(file_path: str) -> bool:
    """非 H.264 或微信难播的编码，转码为 H.264 + AAC（需 ffmpeg）。"""
    if not file_path or not os.path.isfile(file_path):
        return False
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False

    import subprocess

    tmp_path = file_path + ".h264.tmp.mp4"
    try:
        proc = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                file_path,
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
                "23",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-movflags",
                "+faststart",
                tmp_path,
            ],
            capture_output=True,
            check=False,
            timeout=600,
        )
        if (
            proc.returncode == 0
            and os.path.isfile(tmp_path)
            and os.path.getsize(tmp_path) > 1024
        ):
            os.replace(tmp_path, file_path)
            print(f"[transcode] h264 rewritten: {file_path}")
            return True
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        err = proc.stderr[-400:].decode("utf-8", errors="replace") if proc.stderr else ""
        print(f"[transcode] ffmpeg failed: {err or proc.returncode}")
    except Exception as exc:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        print(f"[transcode] error: {exc}")
    return False


def ensure_mobile_playable_mp4(file_path: str) -> None:
    """faststart + 必要时转 H.264，提升微信 / iOS 内联播放成功率。"""
    if not file_path or not os.path.isfile(file_path):
        return
    size = os.path.getsize(file_path)
    if size < 1024:
        raise ValueError(f"视频文件过小（{size} bytes），可能下载不完整")

    original_backup = file_path + ".pre_process.bak"
    shutil.copy2(file_path, original_backup)
    try:
        apply_mp4_faststart(file_path)

        codec = _probe_video_codec(file_path)
        print(f"[codec] {file_path}: {codec or 'unknown'}")
        needs_transcode = not codec or (
            "avc" not in codec
            and "h264" not in codec
            and "avc1" not in codec
        )
        if needs_transcode:
            if not transcode_mp4_to_h264(file_path):
                print(
                    "[transcode] skipped — install ffmpeg for HEVC/other codec support"
                )
            else:
                apply_mp4_faststart(file_path)

        if not _is_mp4_decodable(file_path):
            print("[video] not decodable after postprocess, re-transcoding from backup")
            shutil.copy2(original_backup, file_path)
            if transcode_mp4_to_h264(file_path):
                apply_mp4_faststart(file_path)
            elif not _is_mp4_decodable(file_path):
                shutil.copy2(original_backup, file_path)
                raise ValueError("视频后处理失败，文件无法播放（请确认服务器已安装 ffmpeg）")
    finally:
        if os.path.exists(original_backup):
            try:
                os.remove(original_backup)
            except OSError:
                pass


def extract_video_poster(video_path: str, poster_path: str) -> bool:
    """Extract one JPEG poster frame for mobile preview (requires ffmpeg)."""
    if not os.path.isfile(video_path):
        return False
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    import subprocess

    result = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-ss",
            "1.5",
            "-i",
            video_path,
            "-frames:v",
            "1",
            "-update",
            "1",
            "-q:v",
            "5",
            poster_path,
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode == 0 and os.path.isfile(poster_path):
        print(f"[poster] extracted: {poster_path}")
        return True
    if result.stderr:
        print(f"[poster] ffmpeg failed: {result.stderr[-400:]}")
    return False
