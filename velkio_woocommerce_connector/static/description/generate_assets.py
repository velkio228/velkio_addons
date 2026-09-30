"""Regenerate the shared Velkio presentation from the repository checkout."""
from pathlib import Path
import runpy
import sys

if __name__ == '__main__':
    root = Path(__file__).resolve().parents[3]
    generator = root / 'tools' / 'build_app_presentation.py'
    if not generator.is_file():
        raise SystemExit('Run this generator from the velkio_addons source checkout.')
    sys.path.insert(0, str(generator.parent))
    sys.argv = [str(generator), '--module', 'woo', '--output', str(Path(__file__).resolve().parent)]
    runpy.run_path(str(generator), run_name='__main__')
