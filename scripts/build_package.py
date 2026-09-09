"""Build the allowlisted runtime package without deleting existing files."""
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
resources = root.joinpath('package-resources.txt').read_text().splitlines()
if resources != ['assets']:
    raise SystemExit('Unexpected runtime resource manifest')
destination = root / 'dist' / 'z-files-folders'
expected = {'SKILL.md', 'assets/batch-log.csv'}
if destination.exists():
    actual = {p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file()}
    if actual - expected:
        raise SystemExit('Unexpected files in dist; inspect before rebuilding')
for relative in sorted(expected):
    source = root / relative
    target = destination / relative
    if source.is_symlink() or target.is_symlink():
        raise SystemExit('Symlink is not a package resource')
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
print(destination)
