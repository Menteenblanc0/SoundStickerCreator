"""CLI and desktop entry points."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from media import Edit, Engine
from riff import read

ROOT = Path(__file__).resolve().parent
APP_HOME = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else ROOT


def tool(name):
    suffix = ".exe" if os.name == "nt" else ""
    bundled = APP_HOME / "tools" / (name + suffix)
    return str(bundled) if bundled.is_file() else name


def transport_args(action, package=None, dest=None):
    command = [tool("node"), str(APP_HOME / "transport" / "cli.mjs"), action, "--test-account"]
    if action == "send":
        command += ["--sticker", str(package/"sticker.webp"), "--audio", str(package/"audio.ogg"),
                    "--metadata", str(package/"metadata.json")]
        command += ["--self"] if dest == "self" else ["--to", dest]
    return command


def send_package(package, dest):
    if not (package/"audio.ogg").is_file():
        raise ValueError("Selecciona una fuente de audio para enviar un sticker sonoro.")
    with tempfile.TemporaryDirectory(prefix="sound-sticker-transport-") as scratch:
        env = {**os.environ, "TMPDIR": scratch, "TEMP": scratch, "TMP": scratch}
        return subprocess.run(transport_args("send", package, dest), env=env, check=False).returncode


def cli(argv):
    parser = argparse.ArgumentParser(prog="sound-sticker")
    parser.add_argument("--ffmpeg", default=tool("ffmpeg"))
    parser.add_argument("--ffprobe", default=tool("ffprobe"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("gui")
    analyze = commands.add_parser("inspect")
    analyze.add_argument("webp", type=Path)
    receive = commands.add_parser("receive")
    receive.add_argument("--test-account", action="store_true", required=True)
    receive.add_argument("--measure", action="store_true")
    for name in ("convert", "send"):
        cmd = commands.add_parser(name)
        source = cmd.add_mutually_exclusive_group(required=True)
        source.add_argument("--video", type=Path)
        source.add_argument("--image", type=Path)
        cmd.add_argument("--audio", type=Path)
        if name == "convert":
            cmd.add_argument("--output", type=Path, required=True)
        else:
            dest = cmd.add_mutually_exclusive_group(required=True)
            dest.add_argument("--to")
            dest.add_argument("--self", action="store_true")
            cmd.add_argument("--test-account", action="store_true", required=True)
        default = Edit()
        for option in ("start", "duration", "delay", "db", "fade_in", "fade_out", "audio_start"):
            cmd.add_argument("--"+option.replace("_", "-"), type=float, default=getattr(default, option))
        for option in ("size", "fps", "quality", "budget", "loop"):
            cmd.add_argument("--"+option, type=int, default=getattr(default, option))
        cmd.add_argument("--crop", type=lambda spec: tuple(map(int, spec.split(":"))))
        for option in ("normalize", "static"):
            cmd.add_argument("--"+option, action="store_true")
    args = parser.parse_args(argv)
    engine = Engine(args.ffmpeg, args.ffprobe)
    if args.command == "gui":
        from desktop import open_editor
        open_editor(engine)
    elif args.command == "inspect":
        print(json.dumps(read(args.webp), indent=2, ensure_ascii=False))
    elif args.command == "receive":
        with tempfile.TemporaryDirectory(prefix="sound-sticker-transport-") as scratch:
            env = {**os.environ, "TMPDIR": scratch, "TEMP": scratch, "TMP": scratch}
            command = transport_args("receive") + (["--measure"] if args.measure else [])
            return subprocess.run(command, env=env, check=False).returncode
    else:
        edit = Edit(**{key: getattr(args, key) for key in Edit.__dataclass_fields__})
        visual = args.video or args.image
        progress = lambda line: print(line, file=sys.stderr, flush=True)
        if args.command == "convert":
            report = engine.convert(visual, args.audio, args.output, edit, progress)
            print(json.dumps(report, indent=2))
        else:
            with tempfile.TemporaryDirectory(prefix="sound-sticker-") as temp:
                package = Path(temp) / "package"
                engine.convert(visual, args.audio, package, edit, progress)
                return send_package(package, "self" if args.self else args.to)
    return 0


def main():
    try:
        return cli(sys.argv[1:] or ["gui"])
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
