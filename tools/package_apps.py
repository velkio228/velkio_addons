"""Export every Velkio module as real files and build an installable ZIP per Odoo version.

Run from anywhere: python3 tools/package_apps.py
Prepares local files only; it does not publish or push anything.
"""
from pathlib import Path
import ast
import shutil
import zipfile
from lxml import html

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {'__pycache__', '.git', 'release', 'tools', 'artwork'}
BASE_ASSETS = {'index.html', 'icon.png', 'img.png', 'velkio_mark.png', 'velkio_logo.png', 'workflow.png'}


def modules():
    return sorted(p for p in ROOT.iterdir() if p.name not in SKIP_DIRS and (p / '__manifest__.py').is_file())


def wanted_assets(source):
    desc = source / 'static' / 'description'
    page = html.fromstring((desc / 'index.html').read_text())
    keep = set(BASE_ASSETS)
    keep |= {n.get('src') for n in page.xpath('//img|//video|//source') if n.get('src')}
    keep |= {n.get('poster') for n in page.xpath('//video') if n.get('poster')}
    keep |= {n.get('href') for n in page.xpath('//a') if n.get('href') and not n.get('href').startswith(('#', 'mailto:'))}
    manifest = ast.literal_eval((source / '__manifest__.py').read_text())
    keep |= {Path(i).relative_to('static/description').as_posix() for i in manifest.get('images', []) if i.startswith('static/description/')}
    return keep


def package():
    first = ast.literal_eval((modules()[0] / '__manifest__.py').read_text())
    series = '.'.join(first['version'].split('.')[:2])
    out = ROOT / 'release' / f'odoo-apps-{series}'
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for source in modules():
        keep = wanted_assets(source)
        for item in source.rglob('*'):
            rel = item.relative_to(source)
            if not item.is_file() or any(x in rel.parts for x in SKIP_DIRS) or item.suffix in ('.pyc', '.pyo'):
                continue
            if rel.parts[:2] == ('static', 'description') and rel.relative_to('static/description').as_posix() not in keep:
                continue
            dest = out / source.name / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest)
    for note in ('ODOO_APPS_RELEASE.md', 'README.md'):
        if (ROOT / note).is_file():
            shutil.copy2(ROOT / note, out / ('PUBLISHING_NOTES.md' if note.startswith('ODOO') else 'README.md'))
            break
    archive = ROOT / 'release' / f'odoo-apps-{series}.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for f in sorted(out.rglob('*')):
            if f.is_file():
                z.write(f, f.relative_to(out))
    print(archive, [m.name for m in modules()])


if __name__ == '__main__':
    package()
