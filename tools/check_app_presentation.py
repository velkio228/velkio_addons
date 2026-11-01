"""Validate local store-page assets, navigation, metadata and basic HTML safety."""
import argparse
import ast
from pathlib import Path
from urllib.parse import urlparse
from lxml import etree, html
from PIL import Image


def check(root):
    manifest = ast.literal_eval((root / '__manifest__.py').read_text())
    desc = root / 'static' / 'description'
    page = html.fromstring((desc / 'index.html').read_text())
    assert 'max-width:1320px' in page.get('style', ''), 'Missing standalone page width'
    for row in page.xpath('//*[contains(concat(" ", normalize-space(@class), " "), " row ")]'):
        assert 'display:flex' in row.get('style', ''), 'Row depends on an external stylesheet'
        assert 'flex-wrap:wrap' in row.get('style', ''), 'Row cannot wrap on narrow screens'
    for img in page.xpath('//img'):
        assert 'max-width:100%' in img.get('style', ''), 'Image lacks responsive fallback'
    ids = page.xpath('//@id')
    assert len(ids) == len(set(ids)), 'Duplicate anchors'
    assert len(page.xpath('//h1')) == 1, 'Expected one page title'
    assert not page.xpath('//script|//iframe|//style|//link'), 'Unsupported external/active content'
    assert not page.xpath('//@*[starts-with(name(), "on")]'), 'Inline event handler'
    for img in page.xpath('//img'):
        assert img.get('alt'), 'Image needs alt text'
        src = img.get('src')
        assert not urlparse(src).scheme and not src.startswith('/'), src
        with Image.open(desc / src) as image:
            image.verify()
    for anchor in page.xpath('//a'):
        href = anchor.get('href')
        if href.startswith('#'):
            assert href[1:] in ids, href
        elif href.startswith('mailto:'):
            assert '@' in href
        else:
            assert not urlparse(href).scheme, href
            assert (desc / href).is_file(), href
    assert manifest['name'].strip(), 'Missing app name'
    assert manifest['license'] in ('OPL-1', 'LGPL-3')
    for asset in manifest['images']:
        assert (root / asset).is_file(), asset
    with Image.open(desc / 'icon.png') as icon:
        assert icon.width == icon.height, 'App icon must be square'
    for view in (root / 'views').glob('*.xml'):
        etree.parse(str(view))
    print(f'{root.name}: HTML, images, anchors, manifest and XML checks passed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('modules', nargs='+', type=Path)
    args = parser.parse_args()
    for module in args.modules:
        check(module)
