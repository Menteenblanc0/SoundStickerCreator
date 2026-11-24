"""Build portable Windows x64 and NSIS installer from pinned runtimes on Linux."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from zipfile import ZipFile, ZIP_DEFLATED, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
PYTHON_URL = ("https://github.com/astral-sh/python-build-standalone/releases/download/"
              "20261123/cpython-3.12.16%2B20261123-x86_64-pc-windows-msvc-install_only_stripped.tar.gz")
NODE_URL = "https://nodejs.org/dist/v24.22.3/node-v24.22.3-win-x64.zip"
PYTHON_SHA = "75988f49393727d7e53b673d50088e7f809a629dd37cb59da3756479bc6ea5c1"
NODE_SHA = "e612af99f626ab415ea225af6bce5c971feb448cb5cae250bb1c3fa50c5f7d9f"
ARCHIVE_TIME = (2026, 11, 24, 0, 0, 0)


def digest(file):
    with file.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def verified(url, checksum, path):
    if path.is_file() and digest(path) == checksum:
        return path
    partial = path.with_suffix(".partial")
    with urllib.request.urlopen(url, timeout=60) as response, partial.open("wb") as target:
        shutil.copyfileobj(response, target)
    if digest(partial) != checksum:
        partial.unlink()
        raise ValueError("SHA-256 inválido en " + path.name)
    partial.replace(path)
    return path


def copy_sources(stage):
    for name in ("app.py", "media.py", "desktop.py", "riff.py", "LICENSE", "README.md", "THIRD_PARTY_NOTICES.md"):
        shutil.copy2(ROOT/name, stage/name)
    shutil.copytree(ROOT/"docs", stage/"docs")
    transport = stage/"transport"
    transport.mkdir()
    for pattern in ("*.mjs", "*.json"):
        for file in (ROOT/"transport").glob(pattern):
            if not file.name.endswith(".test.mjs"):
                shutil.copy2(file, transport/file.name)
    subprocess.run(["npm", "ci", "--omit=optional", "--ignore-scripts"], cwd=transport, check=True)


def package(output, cache, go, makensis):
    cache.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    python_tar = verified(PYTHON_URL, PYTHON_SHA, cache/"python-win.tar.gz")
    node_zip = verified(NODE_URL, NODE_SHA, cache/"node-win.zip")
    with tempfile.TemporaryDirectory(prefix="sticker-build-") as scratch:
        tmp = Path(scratch)
        stage = tmp/"SoundStickerCreator"
        stage.mkdir()
        tools = stage/"tools"
        tools.mkdir()
        with tarfile.open(python_tar) as archive:
            archive.extractall(stage, filter="data")
        (stage/"python").rename(stage/"runtime")
        with ZipFile(node_zip) as archive:
            for source, name in (("node.exe", "node.exe"), ("LICENSE", "NODE-LICENSE")):
                (tools/name).write_bytes(archive.read("node-v24.22.3-win-x64/"+source))
        wheels = stage/"runtime"/"Lib"/"site-packages"
        command = [sys.executable, "-m", "pip", "install", "--require-hashes", "--no-deps",
                   "--only-binary=:all:", "--platform", "win_amd64", "--python-version", "3.12",
                   "--no-compile", "--target", str(wheels), "-r", str(ROOT/"packaging/wheels-win-amd64.txt")]
        subprocess.run(command, check=True)
        copy_sources(stage)
        goroot = Path(subprocess.check_output([go, "env", "GOROOT"], text=True).strip())
        shutil.copy2(goroot/"LICENSE", tools/"GO-LICENSE")
        subprocess.run([go, "build", "-trimpath", "-ldflags=-H=windowsgui -s -w -buildid=",
                        "-o", str(stage/"Sound Sticker Creator.exe"), str(ROOT/"packaging/launcher_windows.go")],
                       check=True, env={**os.environ, "GOOS": "windows", "GOARCH": "amd64", "CGO_ENABLED": "0"})

        portable = output/"SoundStickerCreator-0.1.0-win-x64-portable.zip"
        installer = output/"SoundStickerCreator-0.1.0-win-x64-setup.exe"
        with ZipFile(portable, "w", compression=ZIP_DEFLATED) as archive:
            for file in sorted(stage.rglob("*")):
                if file.is_file():
                    entry = ZipInfo(file.relative_to(tmp).as_posix(), ARCHIVE_TIME)
                    entry.compress_type = ZIP_DEFLATED
                    with file.open("rb") as source, archive.open(entry, "w") as dest:
                        shutil.copyfileobj(source, dest)
        subprocess.run([makensis, "-V2", "-DOUTPUT="+str(installer), "-DSTAGE="+str(stage),
                        str(ROOT/"packaging/installer.nsi")], check=True)
        portable.chmod(0o644)
        installer.chmod(0o644)
        (output/"SHA256SUMS.txt").write_text(
            "".join(f"{digest(path)}  {path.name}\n" for path in (portable, installer)),
            encoding="ascii")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT/"dist")
    parser.add_argument("--cache", type=Path, default=ROOT/"build")
    parser.add_argument("--go", default="go")
    parser.add_argument("--makensis", default="makensis")
    args = parser.parse_args()
    package(args.output.resolve(), args.cache.resolve(), args.go, args.makensis)
