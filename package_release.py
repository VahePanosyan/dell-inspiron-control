"""Add dependency notices and archive only the freshly built portable directory."""
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parent
VERSION = "0.1.0"


def main():
    folder = ROOT / "dist/DellInspironControl"
    if not (folder / "DellInspironControl.exe").is_file():
        raise RuntimeError("Build the executable first")
    licenses = folder / "licenses"
    licenses.mkdir(exist_ok=True)
    for source in (ROOT / "licenses").glob("*.txt"):
        shutil.copy2(source, licenses / source.name)
    versions = {}
    for package in ("PySide6", "PySide6_Essentials", "shiboken6", "pywin32", "nvidia-ml-py", "PyInstaller"):
        dist = metadata.distribution(package)
        versions[package] = dist.version
        for entry in dist.files or []:
            parts = entry.parts
            if "licenses" not in parts or ".dist-info" not in parts[0]:
                continue
            relative = Path(*parts[parts.index("licenses") + 1:])
            target = licenses / package / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dist.locate_file(entry), target)
    import pynvml
    header = Path(pynvml.__file__).read_text(encoding="utf-8").split("#####", 2)[1]
    (licenses / "nvidia-ml-py").mkdir(exist_ok=True)
    (licenses / "nvidia-ml-py/LICENSE.txt").write_text(header, encoding="utf-8")
    (licenses / "python").mkdir(exist_ok=True)
    shutil.copy2(Path(sys.base_prefix) / "LICENSE.txt", licenses / "python/LICENSE.txt")
    for name in ("README.md", "LICENSE", "THIRD_PARTY_NOTICES.md"):
        shutil.copy2(ROOT / name, folder / name)
    shutil.copytree(ROOT / "docs", folder / "docs", dirs_exist_ok=True)
    (folder / "build-versions.json").write_text(json.dumps(versions, indent=2), encoding="utf-8")
    archive = ROOT / f"dist/DellInspironControl-v{VERSION}-windows-x64.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as result:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                result.write(path, path.relative_to(folder.parent))
    with zipfile.ZipFile(archive) as result:
        if result.testzip() is not None:
            raise RuntimeError("Archive integrity check failed")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (ROOT / "dist/SHA256SUMS.txt").write_text(f"{digest}  {archive.name}\n", encoding="ascii")
    print(f"Verified {archive.name}: {archive.stat().st_size} bytes; SHA256 {digest}")


if __name__ == "__main__":
    main()
