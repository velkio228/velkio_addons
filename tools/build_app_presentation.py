"""Build script-free Odoo Apps pages and copy the approved Precision artwork.

Usage: python3 tools/build_app_presentation.py --module woo|tally --output PATH
Uses only the Python standard library. Existing screenshots/workflow assets are retained.
"""
import argparse
from html import escape
from pathlib import Path
import shutil
from store_content import APPS, COMMON
from inline_store_layout import inline_layout

ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / 'artwork' / 'branding'


def para(text, cls=''):
    return f'<p class="{cls}" style="color:#625F6C;font-size:16px;line-height:1.8;">{escape(text)}</p>'


def heading(kicker, title):
    return f'<p class="mb-2" style="color:#714B67;font-size:12px;font-weight:700;letter-spacing:2px;">{escape(kicker.upper())}</p>\n<h2 class="mb-4" style="color:#282532;font-size:29px;font-weight:700;">{escape(title)}</h2>'


def section(id_, content, tint=False):
    return f'<section id="{id_}" class="p-3 p-md-4 my-3 rounded" style="background-color:{"#F6F1F6" if tint else "#FFFFFF"};">\n{content}\n</section>'


def cards(items, columns='col-md-6 col-lg-4'):
    result = '<div class="row">\n'
    for n, (title, body) in enumerate(items, 1):
        result += f'<div class="{columns} mb-3"><div class="h-100 p-4 border rounded" style="border-color:#E6DFE8;background-color:#FFFFFF;">\n<p style="color:#9A7135;font-size:13px;font-weight:700;">{n:02d}</p><h3 style="color:#282532;font-size:20px;font-weight:700;">{escape(title)}</h3>\n{para(body)}</div></div>\n'
    return result + '</div>'


def button(label, target, light=False):
    return f'<a href="{target}" class="btn px-4 py-3 m-1" style="background-color:{"#FFFFFF" if light else "#714B67"};color:{"#714B67" if light else "#FFFFFF"};border:1px solid #714B67;font-size:15px;font-weight:700;border-radius:8px;">{escape(label)}</a>'


def callout(title, body, target='#setup', label='Read the setup guide'):
    return f'<div class="row align-items-center p-3 p-md-4 my-4 rounded" style="background-color:#302236;"><div class="col-lg-8"><h3 style="color:#FFFFFF;font-size:25px;">{escape(title)}</h3><p class="mb-2" style="color:#E9DFEC;font-size:16px;line-height:1.7;">{escape(body)}</p></div><div class="col-lg-4 text-lg-right text-lg-end">{button(label,target,True)}</div></div>'


def page(kind, data, out):
    is_woo = kind == 'woo'
    sync_mode = 'Manual actions' if is_woo else 'Manual + scheduled'
    visual_id = 'screenshots' if data['screenshots'] else 'workspace'
    links = [('overview','Overview'),('features','Capabilities'),('coverage','What syncs'),('setup','Setup'),(visual_id,'Screenshots' if data['screenshots'] else 'Workspace'),('documentation','Documentation'),('faq','FAQs'),('support','Support')]
    chunks = ['<section class="oe_container" style="font-family:Arial,Helvetica,sans-serif;color:#282532;background-color:#FFFFFF;">','<div class="container py-3">']
    chunks.append(f'<div class="row align-items-center mb-3"><div class="col-sm-4"><img src="velkio_logo.png" alt="Velkio Odoo Solutions — Precision logo" width="165" class="img-fluid"/></div><div class="col-sm-8 text-sm-right text-sm-end"><span class="badge p-2 m-1" style="color:#714B67;background-color:#F6F1F6;">Odoo 19</span><span class="badge p-2 m-1" style="color:#714B67;background-color:#F6F1F6;">Community &amp; Enterprise</span></div></div>')
    overview = f'<div class="text-center mb-4"><p style="font-size:12px;letter-spacing:2px;color:#9A7135;font-weight:700;">VELKIO ODOO SOLUTIONS</p><h1 style="font-size:42px;line-height:1.15;font-weight:800;color:#282532;">{escape(data["name"])}</h1><p style="font-size:20px;line-height:1.5;color:#714B67;">{escape(data["headline"])}</p></div>'
    specs = [('19.0','Odoo version'),('CE / EE','Editions'),('Odoo.sh','Cloud deployment'),('On-premise','Self-hosted'),(data['license'],'Module license'),('Sync','Manual' if is_woo else 'Configurable')]
    overview += '<div class="row mb-4">'
    for value,label in specs:
        overview += f'<div class="col-6 col-md-4 col-lg-2 mb-2"><div class="h-100 p-3 text-center rounded" style="background-color:#302236;"><div style="color:#E5BE7E;font-size:21px;font-weight:700;">{escape(value)}</div><div style="color:#F5EFF6;font-size:13px;">{escape(label)}</div></div></div>'
    overview += '</div><div class="row align-items-center"><div class="col-lg-6 mb-4">'
    overview += '<h2 style="font-size:27px;line-height:1.3;font-weight:700;color:#282532;">'+('Bring store records into your Odoo workspace' if is_woo else 'Connect accounting records with clear ownership')+'</h2>'+para(data['intro'])
    overview += '<ul class="pl-4" style="color:#514A59;font-size:16px;line-height:1.9;">'+''.join('<li>'+escape(x)+'</li>' for x in data['chips'])+'</ul>'
    overview += button('Explore capabilities','#features')+button('Setup & requirements','#setup',True)+'</div><div class="col-lg-6 mb-4"><div class="p-3 rounded" style="background-color:#302236;"><div class="p-3 rounded" style="background-color:#FFFFFF;"><p style="color:#714B67;font-size:12px;font-weight:700;letter-spacing:1px;">YOUR OPERATIONAL WORKSPACE</p><div class="row">'
    tiles = [('Products','Names, SKUs and prices'),('Customers','Contacts imported to Odoo'),('Sales orders','New orders and their lines'),('Multiple stores','Separate connection settings'),('Mappings','Linked store and Odoo records'),('Sync logs','Review operation results')] if is_woo else [('Accounting','Ledgers, parties and taxes'),('Inventory','Items, units and locations'),('Transactions','Invoices, bills and payments'),('Ownership','Direction per record type'),('Outbound queue','Follow outgoing changes'),('Monitoring','Logs and quarantine')]
    for title,body in tiles:
        overview += f'<div class="col-sm-6 mb-3"><div class="h-100 border rounded p-3" style="background-color:#F8F5F9;"><h3 style="font-size:18px;color:#714B67;">{title}</h3><p class="mb-0" style="font-size:14px;color:#625F6C;line-height:1.5;">{body}</p></div></div>'
    overview += '</div></div></div></div></div>'
    chunks.append(section('overview',overview,True))
    chunks.append('<div class="text-center p-2 my-3 border rounded" style="background-color:#FFFFFF;">'+''.join(f'<a href="#{id_}" class="d-inline-block px-3 py-2" style="color:#714B67;font-size:14px;font-weight:700;">{label}</a>' for id_,label in links)+'</div>')
    chunks.append('<div class="my-4"><img src="banner.png" alt="'+escape(data['name']+' — '+', '.join(data['chips']))+'" class="img-fluid w-100 rounded"/></div>')
    chunks.append(section('features',heading('Connector capabilities','See how it fits your everyday work')+para('Explore the operations included in this release, from connection setup through record review.')+cards(data['features'])))
    # Direction is explicit on every category card, with no implied two-way scope.
    coverage = heading('Synchronization coverage','Which records move between your systems?')
    coverage += '<div class="row">'
    for title,direction,body in data['sync']:
        coverage += f'<div class="col-md-6 col-lg-4 mb-3"><div class="h-100 p-4 border rounded" style="background-color:#FFFFFF;"><p class="mb-3" style="font-size:12px;color:#714B67;font-weight:700;">{escape(direction)}</p><h3 style="color:#282532;font-size:22px;">{escape(title)}</h3>{para(body)}</div></div>'
    coverage += '</div><div class="p-3 border rounded" style="background-color:#FFFFFF;"><h3 style="font-size:18px;color:#714B67;">Understand the scope</h3>'+para(data['scope'],'mb-0')+'</div>'
    chunks.append(section('coverage',coverage,True))
    chunks.append(callout('Make your first connection with confidence','Check prerequisites, choose your settings and validate a small first synchronization.'))
    # Distinct detailed capability groups mirror operational categories, not unsupported reference features.
    details = heading('Operational details','A closer look at the controls you will use')+'<div class="row">'
    groups = [('Connection & store defaults',[data['features'][0][1],data['steps'][3][1]]),('Catalog & order handling',[data['features'][1][1],data['features'][3][1]]),('Visibility & record links',[data['features'][4][1],data['features'][5][1]])] if is_woo else [('Connection & onboarding',[data['steps'][2][1],data['features'][3][1]]),('Direction & ownership',[data['features'][0][1],data['steps'][4][1]]),('Queue & operational monitoring',[data['features'][4][1],data['features'][5][1]])]
    for title,bullets in groups:
        details += f'<div class="col-lg-4 mb-3"><div class="h-100 p-4 border rounded"><h3 style="font-size:21px;color:#714B67;">{escape(title)}</h3><ul class="pl-3" style="color:#625F6C;font-size:15px;line-height:1.8;">'+''.join('<li class="mb-2">'+escape(b)+'</li>' for b in bullets)+'</ul></div></div>'
    chunks.append(section('details',details+'</div>'))
    requirements = ''.join('<li class="mb-2">'+escape(r)+'</li>' for r in data['requirements'])
    setup = heading('Getting started','Prepare, connect and validate')+'<div class="p-3 p-md-4 border rounded mb-4" style="background-color:#F8F5EF;"><h3 style="font-size:21px;color:#282532;">Before installation</h3>'+para(COMMON['hosting'])+f'<ul style="color:#625F6C;font-size:16px;line-height:1.8;">{requirements}</ul></div>'+cards(data['steps'],'col-md-6')
    chunks.append(section('setup',setup))
    flow = heading('Daily operation','Follow the record from source to result')+'<div class="row">'
    for n,(label,title,body) in enumerate(data['workflow'],1):
        flow += f'<div class="col-md-6 col-lg-3 mb-3"><div class="h-100 border rounded p-3" style="background-color:#FFFFFF;"><p style="color:#9A7135;font-weight:700;font-size:12px;">{n:02d} / {label}</p><h3 style="font-size:19px;color:#282532;">{escape(title)}</h3>{para(body)}</div></div>'
    flow += '</div><img src="workflow.png" alt="'+escape('WooCommerce products import/export; customers and new orders import into Odoo.' if is_woo else 'TallyPrime record flow follows configured direction and ownership.')+'" class="img-fluid w-100 rounded border"/>'
    chunks.append(section('workflow',flow,True))
    if data['screenshots']:
        gallery = heading('Product walkthrough','Follow the workflow on screen')+para('Existing module screenshots from a demonstration environment with test records and a Tally simulator. They show the previous navigation icon. Select an image to view it at full size.')
        for n,(file,title,body) in enumerate(data['screenshots']):
            assert (out/'screenshots'/file).is_file(),file
            gallery += f'<div class="row align-items-center my-4 py-3 border-bottom"><div class="col-lg-4 {"order-lg-2" if n%2 else ""}"><p style="color:#9A7135;font-size:12px;font-weight:700;">SCREEN {n+1:02d}</p><h3 style="color:#282532;font-size:24px;">{escape(title.split(" · ",1)[-1])}</h3>{para(body)}</div><div class="col-lg-8 {"order-lg-1" if n%2 else ""}"><a href="screenshots/{file}"><img src="screenshots/{file}" alt="{escape(title)} — demonstration screenshot" class="img-fluid w-100 border rounded"/></a></div></div>'
        chunks.append(section('screenshots',gallery))
    else:
        chunks.append(section('workspace',heading('Workspace guide','Know where to go in Odoo')+cards(data['workspace'],'col-md-6')))
    docs = heading('Documentation','Your guides, in one place')+'<div class="row">'
    for title,body,target,label in [('Installation & first sync','Requirements and six practical setup steps.','#setup','Open setup guide'),('Data flow & daily use','Follow the supported synchronization sequence.','#workflow','View workflow'),('Troubleshooting','Check connections, mappings and operation results.','#troubleshooting','Find an answer')]:
        docs += f'<div class="col-md-4 mb-3"><div class="h-100 p-4 border rounded" style="background-color:#FFFFFF;"><h3 style="font-size:21px;color:#282532;">{title}</h3>{para(body)}<a href="{target}" style="color:#714B67;font-weight:700;">{label} →</a></div></div>'
    chunks.append(section('documentation',docs+'</div>',True))
    chunks.append(section('troubleshooting',heading('Troubleshooting','When an operation needs attention')+cards(data['troubleshooting'])))
    faq = heading('Questions & answers','Check the details before you install')+'<div class="row">'
    for n,(q,a) in enumerate(data['faqs'],1):
        faq += f'<div class="col-md-6 mb-3"><div class="h-100 border rounded p-4"><p style="font-size:12px;color:#9A7135;font-weight:700;">{n:02d}</p><h3 style="font-size:19px;color:#282532;">{escape(q)}</h3>{para(a)}</div></div>'
    chunks.append(section('faq',faq+'</div>'))
    support = heading('Velkio support','Get help with your connector')+cards([('Setup questions','Describe your deployment and the step you need help with.'),('Operation troubleshooting','Share the action, exact error and relevant log details.'),('Scope & configuration','Ask about supported record types, directions and configuration options.')])
    support += callout('Tell us what you need help with','Include your Odoo and module versions. Remove passwords, API keys and personal data from shared screenshots.','mailto:'+COMMON['email'],'Email Velkio support')
    support += f'<div class="row align-items-center"><div class="col-md-4"><img src="velkio_logo.png" alt="Velkio Odoo Solutions" width="180" class="img-fluid"/></div><div class="col-md-8">{para(COMMON["email"])}{para("Independent integration by Velkio Odoo Solutions. Product names belong to their respective owners.","small")}</div></div>'
    chunks.append(section('support',support,True))
    chunks.append(section('release',heading('Release information','Version '+data['version'])+para('This release includes the Velkio Precision identity, illustrated banners, setup documentation and synchronization scope. License: '+data['license']+'.')))
    chunks.extend(['</div>','</section>'])
    return '\n'.join(chunks)+'\n'


def build(kind, out):
    out.mkdir(parents=True, exist_ok=True)
    for source, targets in [
        ('velkio-precision-logo.png', ['velkio_logo.png']),
        ('velkio-precision-mark.png', ['icon.png', 'img.png', 'velkio_mark.png']),
        ('woocommerce-banner.png' if kind == 'woo' else 'tally-banner.png', ['banner.png']),
    ]:
        for target in targets:
            shutil.copy2(BRAND / source, out / target)
    (out / 'index.html').write_text(inline_layout(page(kind, APPS[kind], out)), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--module', choices=APPS, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.module, args.output)
