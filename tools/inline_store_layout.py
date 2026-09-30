"""Inline layout essentials so index.html also works without Odoo's Bootstrap.

Retain Bootstrap classes for the marketplace; fluid flex bases provide a local,
responsive fallback without scripts, style tags or external stylesheets.
"""
from html import escape
from html.parser import HTMLParser

SPACE = {'0': '0', '1': '4px', '2': '8px', '3': '16px', '4': '24px', '5': '48px'}
BASES = {'2': '125px', '3': '210px', '4': '280px', '6': '420px', '8': '560px'}


class InlineLayout(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get('class', '').split()
        rules = {'box-sizing': 'border-box'}
        if tag in ('h1', 'h2', 'h3'):
            rules.update({'margin': '0 0 16px', 'line-height': '1.3'})
        if tag == 'p':
            rules.update({'margin': '0 0 16px', 'overflow-wrap': 'anywhere'})
        if tag == 'a':
            rules.update({'text-decoration': 'none'})
        if tag == 'img':
            rules.update({'max-width': '100%', 'height': 'auto', 'vertical-align': 'middle'})
        if 'oe_container' in classes:
            rules.update({'display': 'block', 'max-width': '1320px', 'width': '100%', 'margin': '0 auto', 'line-height': '1.6'})
        if 'container' in classes:
            rules.update({'width': '100%', 'margin': '0 auto', 'padding': '0 16px'})
        if 'row' in classes:
            rules.update({'display': 'flex', 'flex-wrap': 'wrap', 'margin-left': '-10px', 'margin-right': '-10px'})
        columns = [c for c in classes if c.startswith('col-')]
        if columns:
            size = columns[-1].split('-')[-1]
            basis = BASES.get(size, '260px')
            if columns[-1] == 'col-sm-6':
                basis = '180px'
            if columns == ['col-6']:
                basis = '140px'
            rules.update({'flex': f'{2 if size == "8" else 1} 1 {basis}', 'min-width': '0', 'max-width': '100%', 'padding-left': '10px', 'padding-right': '10px'})
        for cls in classes:
            mapping = {
                'align-items-center': {'align-items': 'center'},
                'text-center': {'text-align': 'center'},
                'd-inline-block': {'display': 'inline-block'},
                'h-100': {'height': '100%'},
                'w-100': {'width': '100%'},
                'rounded': {'border-radius': '10px'},
                'border': {'border': '1px solid #E6DFE8'},
                'border-bottom': {'border-bottom': '1px solid #E6DFE8'},
                'btn': {'display': 'inline-block', 'text-align': 'center', 'line-height': '1.5'},
                'badge': {'display': 'inline-block', 'font-size': '12px', 'font-weight': '700', 'line-height': '1.3', 'border-radius': '5px'},
                'small': {'font-size': '13px'},
            }
            rules.update(mapping.get(cls, {}))
            # Use unprefixed spacing as the local fallback; Bootstrap can enhance
            # breakpoint-specific spacing when this fragment is hosted in Odoo.
            bits = cls.split('-')
            if len(bits) == 2 and bits[1] in SPACE and bits[0] in ('p','px','py','pt','pb','pl','pr','m','mx','my','mt','mb','ml','mr'):
                code = bits[0]
                prop = 'padding' if code[0] == 'p' else 'margin'
                sides = {'': [''], 'x': ['-left','-right'], 'y': ['-top','-bottom'], 't': ['-top'], 'b': ['-bottom'], 'l': ['-left'], 'r': ['-right']}[code[1:]]
                for side in sides:
                    rules[prop + side] = SPACE[bits[1]]
        # Explicit design styles win over generic layout utilities.
        for declaration in attrs.get('style', '').split(';'):
            if ':' in declaration:
                key, value = declaration.split(':', 1)
                rules[key.strip()] = value.strip()
        attrs['style'] = ';'.join(f'{k}:{v}' for k, v in rules.items()) + ';'
        rendered = ' '.join(f'{key}="{escape(value or "", quote=True)}"' for key, value in attrs.items())
        self.parts.append(f'<{tag} {rendered}>')

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        self.parts.append(f'</{tag}>')

    def handle_data(self, data):
        self.parts.append(data)

    def handle_entityref(self, name):
        self.parts.append('&' + name + ';')

    def handle_charref(self, name):
        self.parts.append('&#' + name + ';')


def inline_layout(markup):
    parser = InlineLayout()
    parser.feed(markup)
    parser.close()
    return ''.join(parser.parts)
