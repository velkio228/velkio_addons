"""Export real module folders (resolving Tally's symlink) and an installable ZIP.

Run after presentation checks. This prepares local files; it does not publish.
"""
from pathlib import Path
import shutil
import zipfile
from lxml import html

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'release' / 'odoo-apps-19.0'
MODULES = ('velkio_woocommerce_connector', 'velkio_tally_integration')


def package():
    OUT.mkdir(parents=True, exist_ok=True)
    for name in MODULES:
        source = ROOT / name
        target = OUT / name
        # Keep only current presentation assets, not superseded marketing artwork.
        desc = source / 'static' / 'description'
        page = html.fromstring((desc / 'index.html').read_text())
        assets = {node.get('src') for node in page.xpath('//img')}
        assets |= {'index.html', 'icon.png', 'img.png', 'velkio_mark.png', 'velkio_logo.png', 'workflow.png'}
        for item in source.rglob('*'):
            relative = item.relative_to(source)
            if not item.is_file() or any(x in relative.parts for x in ('__pycache__', '.git')) or item.suffix in ('.pyc', '.pyo'):
                continue
            if relative.parts[:2] == ('static', 'description') and relative.relative_to('static/description').as_posix() not in assets:
                continue
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, destination)
    shutil.copy2(ROOT / 'ODOO_APPS_RELEASE.md', OUT / 'PUBLISHING_NOTES.md')
    archive = ROOT / 'release' / 'odoo-apps-19.0.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as result:
        for file in sorted(OUT.rglob('*')):
            if file.is_file():
                result.write(file, file.relative_to(OUT))
    print(archive)


if __name__ == '__main__':
    package()
