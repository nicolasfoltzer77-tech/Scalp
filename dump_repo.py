import os
from datetime import datetime
from pathlib import Path

IGNORE_EXTENSIONS = {'.log', '.pyc'}
IGNORE_DIRS = {'__pycache__'}


def _is_ignored(path: Path) -> bool:
    """Return True if the path should be ignored."""
    if any(part.startswith('.') for part in path.parts):
        return True
    if path.suffix in IGNORE_EXTENSIONS:
        return True
    if any(part in IGNORE_DIRS for part in path.parts):
        return True
    return False


def _build_tree(root: Path, ignore_path: Path) -> str:
    lines = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirpath = Path(dirpath)
        dirnames[:] = [d for d in dirnames if not d.startswith('.') and d not in IGNORE_DIRS]
        depth = len(dirpath.relative_to(root).parts)
        indent = '    ' * depth
        lines.append(f"{indent}{dirpath.name}/")
        for fname in sorted(filenames):
            fpath = dirpath / fname
            if fpath == ignore_path or _is_ignored(fpath):
                continue
            lines.append(f"{indent}    {fname}")
    return '\n'.join(lines)


def _iter_files(root: Path):
    for path in sorted(root.rglob('*')):
        if path.is_file() and not _is_ignored(path):
            yield path


def create_dump_file(output_path: str = 'dump.txt', root: str = '.') -> None:
    """Create a text dump of the repository tree and file contents."""
    root_path = Path(root).resolve()
    output_path = root_path / output_path
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with output_path.open('w', encoding='utf-8') as dump:
        dump.write(f"Dump created: {now}\n")
        dump.write('Repository tree:\n')
        dump.write(_build_tree(root_path, output_path))
        dump.write('\n\n')
        for file_path in _iter_files(root_path):
            rel_path = file_path.relative_to(root_path)
            if file_path == output_path:
                continue
            mod_time = datetime.fromtimestamp(file_path.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            dump.write(f"## {rel_path} (last modified: {mod_time})\n")
            try:
                with file_path.open('r', encoding='utf-8') as f:
                    dump.write(f.read())
            except Exception:
                dump.write('[unreadable file]\n')
            dump.write('\n\n')


if __name__ == '__main__':
    create_dump_file()
