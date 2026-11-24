"""Local FFmpeg pipeline. Only the transport module opens network connections."""
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid

from PIL import Image

from riff import MAX_INPUT, add_pack, inspect, read

VISUAL = {".mp4": "mov", ".mov": "mov", ".webm": "matroska", ".gif": "gif",
          ".webp": "webp_pipe", ".png": "png_pipe", ".jpg": "jpeg_pipe", ".jpeg": "jpeg_pipe"}
SOUND = {".mp3": "mp3", ".wav": "wav", ".ogg": "ogg", ".opus": "ogg",
         ".m4a": "mov", ".flac": "flac", ".mp4": "mov", ".mov": "mov", ".webm": "matroska"}
STILL = {".png", ".jpg", ".jpeg"}


@dataclass
class Edit:
    start: float = 0
    duration: float = 6.867
    audio_start: float | None = None
    delay: float = 0
    db: float = 0
    normalize: bool = False
    fade_in: float = 0
    fade_out: float = 0
    size: int = 256
    fps: int = 15
    quality: int = 78
    budget: int = 500_000
    loop: int = 0
    crop: tuple[int, int, int, int] | None = None
    static: bool = False

    def validate(self):
        numbers = [self.start, self.duration, self.delay, self.db, self.fade_in, self.fade_out]
        if self.audio_start is not None:
            numbers.append(self.audio_start)
        if not all(math.isfinite(v) for v in numbers):
            raise ValueError("Los ajustes deben ser números finitos")
        if not 1/30 <= self.duration <= 30 or not 0 <= self.start <= 43200:
            raise ValueError("Rango visual fuera del límite local")
        if self.audio_start is not None and not 0 <= self.audio_start <= 43200:
            raise ValueError("Inicio de audio fuera del límite local")
        if not -30 <= self.delay <= 30 or not -60 <= self.db <= 18:
            raise ValueError("Desfase o volumen fuera del límite local")
        if min(self.fade_in, self.fade_out) < 0 or self.fade_in+self.fade_out > self.duration:
            raise ValueError("Fundidos fuera del intervalo")
        if not (64 <= self.size <= 1024 and 1 <= self.fps <= 30 and 10 <= self.quality <= 100
                and 1024 <= self.budget <= 8*1024**2 and 0 <= self.loop <= 65535):
            raise ValueError("Resolución, FPS, calidad, tamaño o bucle fuera del límite local")
        if self.crop is not None and (len(self.crop) != 4 or min(self.crop[:2]) < 1
                                      or min(self.crop[2:]) < 0 or max(self.crop) > 16384):
            raise ValueError("Recorte esperado en formato ancho:alto:x:y")


class Engine:
    def __init__(self, ffmpeg="ffmpeg", ffprobe="ffprobe"):
        self.ffmpeg = ffmpeg
        self.ffprobe = ffprobe

    @staticmethod
    def run(args, timeout=150, *, cwd=None):
        try:
            result = subprocess.run(args, stdin=subprocess.DEVNULL, capture_output=True,
                                    timeout=timeout, cwd=cwd, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except FileNotFoundError as error:
            raise ValueError(f"No se encontró {Path(args[0]).name}") from error
        except subprocess.TimeoutExpired as error:
            raise ValueError("El procesamiento excedió el tiempo límite") from error
        if result.returncode:
            raise ValueError("El archivo o los ajustes no pudieron procesarse con " + Path(args[0]).name)
        return result.stdout

    @staticmethod
    def input_path(path, formats):
        path = Path(path).resolve(strict=True)
        if not path.is_file() or not 0 < path.stat().st_size <= MAX_INPUT or path.suffix.lower() not in formats:
            raise ValueError("Formato o tamaño de entrada fuera de los límites locales")
        return path

    @staticmethod
    def source(path, demux):
        return ["-protocol_whitelist", "file", "-f", demux, "-i", str(path)]

    def probe(self, path, demux):
        return json.loads(self.run([self.ffprobe, "-v", "error", "-show_entries",
                                    "stream=codec_type,codec_name,width,height,duration:format=duration",
                                    "-of", "json", *self.source(path, demux)], timeout=30))

    def ff(self, args, *, cwd=None):
        return self.run([self.ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error",
                         "-filter_threads", "2", "-y", *args], cwd=cwd)

    @staticmethod
    def duration(probe, stream):
        for value in (stream.get("duration"), probe.get("format", {}).get("duration")):
            try:
                seconds = float(value)
                if math.isfinite(seconds) and seconds > 0:
                    return seconds
            except (TypeError, ValueError):
                pass
        return None

    def convert(self, visual, sound, output, edit, progress=lambda _text: None):
        edit.validate()
        visual = self.input_path(visual, VISUAL)
        sound = self.input_path(sound, SOUND) if sound else None
        output = Path(output).resolve()
        if output.exists():
            raise ValueError("La carpeta de salida ya existe")
        if not output.parent.is_dir():
            raise ValueError("No existe la carpeta padre de salida")
        with tempfile.TemporaryDirectory(prefix=".sound-sticker-", dir=output.parent) as temp:
            stage = Path(temp)
            package = stage / "sticker"
            package.mkdir()
            path = package / "sticker.webp"
            progress("Analizando medios")
            source, animated, duration, embedded = self.visual_source(visual, stage, edit)
            progress("Procesando imagen")
            self.convert_visual(source, animated, duration, path, stage, edit)
            report = read(path)
            if report["animated"]:
                duration = report["duration_ms"] / 1000
            if sound or embedded:
                progress("Procesando audio")
                audio = package / "audio.ogg"
                self.convert_audio(sound or visual, visual, audio, duration, edit)
                audio_probe = self.probe(audio, "ogg")
                codec = audio_probe["streams"][0]["codec_name"]
                audio_seconds = self.duration(audio_probe, audio_probe["streams"][0])
                if codec != "opus" or audio_seconds is None:
                    raise ValueError("Salida de audio incompatible")
                report["audioSeconds"] = audio_seconds
            else:
                report["audioSeconds"] = None
            (package / "metadata.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            os.rename(package, output)
        return report

    def visual_source(self, path, stage, edit):
        suffix = path.suffix.lower()
        animated = suffix not in STILL
        duration = edit.duration
        embedded = False
        if suffix == ".webp":
            report = read(path)
            width, height = report["width"], report["height"]
            animated = report["animated"]
            available = report["duration_ms"]/1000 if animated else None
            source = self.source(path, VISUAL[suffix])
            if animated:
                if width*height > 24_000_000:
                    raise ValueError("Lienzo WebP demasiado grande")
                source = self.webp_frames(path, stage, report, edit)
        else:
            source = self.source(path, VISUAL[suffix])
            probe = self.probe(path, VISUAL[suffix])
            streams = probe.get("streams", [])
            video = next((item for item in streams if item["codec_type"] == "video"), None)
            if not video:
                raise ValueError("El archivo no contiene imagen")
            width, height = video["width"], video["height"]
            available = self.duration(probe, video) if animated else None
            embedded = any(item["codec_type"] == "audio" for item in streams)
        if width*height > 24_000_000:
            raise ValueError("Lienzo de entrada demasiado grande")
        if edit.crop:
            w, h, x, y = edit.crop
            if x + w > width or y + h > height:
                raise ValueError("El recorte supera la imagen de entrada")
        if available is not None:
            duration = min(duration, available - edit.start)
        if duration <= 0:
            raise ValueError("El inicio seleccionado supera la duración")
        return source, animated and not edit.static, duration, embedded

    @staticmethod
    def webp_frames(path, stage, report, edit):
        # libwebp composites animation frames. FFmpeg consumes generated local PNGs.
        lines = ["ffconcat version 1.0"]
        elapsed = 0
        end = edit.start + edit.duration
        pixels = 0
        with Image.open(path) as image:
            for i, frame in enumerate(report["frames"]):
                frame_end = elapsed + max(frame["ms"], 1)/1000
                if elapsed >= end:
                    break
                # Keep the original time axis without writing the skipped prefix.
                if frame_end > edit.start:
                    spent = frame_end - max(elapsed, edit.start)
                    pixels += image.width * image.height
                    if pixels > 100_000_000:
                        raise ValueError("La animación WebP supera el límite de decodificación")
                    image.seek(i)
                    name = f"frame-{i}.png"
                    image.convert("RGBA").save(stage / name)
                    lines.extend([f"file {name}", "option framerate 1000", f"duration {spent:.6f}"])
                elapsed = frame_end
        if len(lines) == 1:
            raise ValueError("No hay fotogramas en el rango solicitado")
        lines.extend([f"file {name}", "option framerate 1000"])
        (stage / "frames.txt").write_text("\n".join(lines) + "\n", encoding="ascii")
        return ["-protocol_whitelist", "file", "-f", "concat", "-safe", "0", "-i", str(stage / "frames.txt")]

    def convert_visual(self, source, animated, duration, path, stage, edit):
        select = ["-ss", str(edit.start)] if edit.start and "concat" not in source else []
        info = {
            "sticker-pack-id": str(uuid.uuid4()), "sticker-pack-name": "Sound Sticker Creator",
            "sticker-pack-publisher": "", "emojis": [], "is-from-user-created-pack": 1
        }
        crop = ["crop=" + ":".join(map(str, edit.crop)) + ":exact=1"] if edit.crop else []
        canvas = [f"scale={edit.size}:{edit.size}:force_original_aspect_ratio=decrease",
                  "setsar=1", "format=rgba",
                  f"pad={edit.size}:{edit.size}:(ow-iw)/2:(oh-ih)/2:color=black@0"]
        qualities = sorted({edit.quality, max(10, edit.quality - 12), max(10, edit.quality - 26),
                            max(10, edit.quality - 44), 10}, reverse=True)
        for quality in qualities:
            filters = ([f"fps={edit.fps}"] if animated else []) + crop + canvas
            limit = ["-t", str(duration), "-loop", str(edit.loop)] if animated else ["-frames:v", "1"]
            self.ff([*source, *select, "-map", "0:v:0", "-an", "-vf", ",".join(filters),
                     *limit, "-c:v", "libwebp", "-threads", "2", "-compression_level", "5",
                     "-quality", str(quality), str(path)], cwd=stage)
            data = add_pack(path.read_bytes(), info)
            if len(data) <= edit.budget:
                path.write_bytes(data)
                return
        raise ValueError("No se alcanzó el tamaño objetivo. Reduce la resolución, los FPS o la duración.")

    def convert_audio(self, audio, visual, output, duration, edit):
        start = edit.audio_start
        if start is None:
            start = edit.start if audio == visual else 0
        start += max(0, -edit.delay)
        filters = []
        if edit.normalize:
            filters += ["loudnorm=I=-16:TP=-1.5:LRA=11"]
        filters += [f"volume={edit.db}dB"]
        if edit.delay > 0:
            filters += [f"adelay={round(edit.delay*1000)}:all=1"]
        filters += ["apad", f"atrim=duration={duration:.6f}"]
        if edit.fade_in:
            filters += [f"afade=t=in:d={min(edit.fade_in, duration):.6f}"]
        if edit.fade_out:
            fade = min(edit.fade_out, duration)
            filters += [f"afade=t=out:st={duration-fade:.6f}:d={fade:.6f}"]
        self.ff(["-ss", str(start), *self.source(audio, SOUND[audio.suffix.lower()]), "-map", "0:a:0",
                 "-vn", "-af", ",".join(filters), "-t", str(duration), "-ar", "48000",
                 "-ac", "1", "-c:a", "libopus", "-b:a", "48k", "-map_metadata", "-1", str(output)])

    def waveform(self, path):
        raw = self.ff([*self.source(path, "ogg"), "-map", "0:a:0",
                       "-ar", "1000", "-ac", "1", "-f", "s8", "-"])
        block = max(1, (len(raw) + 159)//160)
        return [max(abs(v if v < 128 else v-256) for v in raw[i:i+block])/128
                for i in range(0, len(raw), block)]
