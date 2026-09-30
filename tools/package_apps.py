"""Export the two Odoo 17 modules with current presentation assets."""
import ast
from pathlib import Path
import shutil
import zipfile
from lxml import html
from store_content import APPS

ROOT=Path(__file__).resolve().parents[1]

def package():
    out=ROOT/'release'/'odoo-apps-17.0'
    files=[]
    for data in APPS.values():
        source=ROOT/data['module']
        desc=source/'static'/'description'
        manifest=ast.literal_eval((source/'__manifest__.py').read_text())
        page=html.fromstring((desc/'index.html').read_text())
        assets={x.get('src') for x in page.xpath('//img')}
        assets|={'index.html','icon.png','img.png','velkio_logo.png','velkio_mark.png'}
        assets|={x.removeprefix('static/description/') for x in manifest['images']}
        for item in sorted(source.rglob('*')):
            relative=item.relative_to(source)
            if not item.is_file() or '__pycache__' in relative.parts or item.suffix in ('.pyc','.pyo'):
                continue
            if relative.parts[:2]==('static','description') and relative.relative_to('static/description').as_posix() not in assets:
                continue
            dest=out/data['module']/relative
            dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(item,dest)
            files.append(dest)
    notes=out/'PUBLISHING_NOTES.md'
    shutil.copy2(ROOT/'ODOO_APPS_RELEASE.md',notes)
    files.append(notes)
    archive=ROOT/'release'/'odoo-apps-17.0.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for file in files:
            z.write(file,file.relative_to(out))
    print(archive)

if __name__=='__main__':
    package()
