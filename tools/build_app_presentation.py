"""Build standalone, script-free Odoo 17 Apps pages from approved artwork."""
import argparse
from html import escape as e
from pathlib import Path
import shutil
from store_content import APPS
from inline_store_layout import inline_layout

ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / 'artwork' / 'branding'

def para(text):
    return f'<p style="font-size:16px;line-height:1.8;color:#625F6C;">{e(text)}</p>'

def heading(kicker,title):
    return f'<p style="font-size:12px;letter-spacing:2px;font-weight:700;color:#9A7135;">{e(kicker.upper())}</p><h2 style="font-size:29px;color:#282532;">{e(title)}</h2>'

def section(anchor,kicker,title,body,tint=False):
    return f'<section id="{anchor}" class="p-3 p-md-4 my-3 rounded" style="background-color:{"#F6F1F6" if tint else "#FFFFFF"};">{heading(kicker,title)}{body}</section>'

def cards(items,columns='col-md-6 col-lg-4'):
    return '<div class="row">'+''.join(f'<div class="{columns} mb-3"><div class="h-100 p-4 border rounded" style="background-color:#FFFFFF;border-color:#E6DFE8;"><p style="color:#9A7135;font-size:13px;font-weight:700;">{i:02d}</p><h3 style="font-size:21px;color:#714B67;">{e(title)}</h3>{para(body)}</div></div>' for i,(title,body) in enumerate(items,1))+'</div>'

def image(src,alt,width=None):
    return f'<img src="{src}" alt="{e(alt)}" class="img-fluid rounded {"w-100" if not width else ""}" {f"width={width}" if width else ""}/>'

def page(data,out):
    name=data['name']
    chunks=['<section class="oe_container" style="font-family:Arial,Helvetica,sans-serif;color:#282532;background-color:#FFFFFF;">','<div class="container py-3">']
    chunks.append('<div class="row align-items-center mb-3"><div class="col-sm-4">'+image('velkio_logo.png','Velkio Odoo Solutions — Precision identity',165)+'</div><div class="col-sm-8 text-sm-right"><span class="badge p-2 m-1" style="color:#714B67;background-color:#F6F1F6;">Odoo 17</span><span class="badge p-2 m-1" style="color:#714B67;background-color:#F6F1F6;">Community &amp; Enterprise</span></div></div>')
    intro=f'<div class="text-center mb-4"><p style="color:#9A7135;font-size:12px;letter-spacing:2px;">VELKIO ODOO SOLUTIONS</p><h1 style="font-size:42px;line-height:1.15;color:#282532;">{e(name)}</h1><p style="font-size:20px;color:#714B67;">{e(data["headline"])}</p></div><div class="row mb-4">'
    specs=[('17.0','Odoo version'),('CE / EE','Editions'),('Odoo.sh','Cloud hosting'),('On-premise','Self-hosted'),(data['license'],'License'),('User controls','App focus')]
    for val,label in specs:
        intro+=f'<div class="col-6 col-md-4 col-lg-2 mb-2"><div class="h-100 p-3 text-center rounded" style="background-color:#302236;"><div style="color:#E5BE7E;font-size:20px;font-weight:700;">{e(val)}</div><div style="color:#F5EFF6;font-size:13px;">{e(label)}</div></div></div>'
    intro+='</div><div class="row align-items-center"><div class="col-lg-6 mb-3"><h2 style="font-size:27px;color:#282532;">'+e(data['headline'])+'</h2>'+para(data['intro'])+'<ul style="font-size:16px;color:#625F6C;line-height:1.9;">'+''.join('<li>'+e(x)+'</li>' for x in data['chips'])+'</ul><a href="#setup" class="btn p-3" style="background-color:#714B67;color:#FFFFFF;font-weight:700;border-radius:8px;">Read the setup guide</a></div><div class="col-lg-6 mb-3"><div class="p-3 rounded" style="background-color:#302236;"><div class="p-3 rounded" style="background-color:#FFFFFF;">'+cards(data['tiles'],'col-sm-6')+'</div></div></div></div>'
    chunks.append(f'<section id="overview" class="p-3 p-md-4 my-3 rounded" style="background-color:#F6F1F6;">{intro}</section>')
    links=[('overview','Overview'),('features','Features'),('coverage','Controls & scope'),('setup','Setup'),('workflow','Workflow'),('screenshots','Walkthrough'),('documentation','Documentation'),('faq','FAQs'),('support','Support')]
    chunks.append('<nav class="text-center p-2 my-3 border rounded">'+''.join(f'<a href="#{target}" class="d-inline-block px-3 py-2" style="font-size:14px;color:#714B67;font-weight:700;">{label}</a>' for target,label in links)+'</nav>')
    chunks.append('<div class="my-4">'+image('banner.png',name+' — '+data['headline'])+'</div>')
    chunks.append(section('features','Everyday capabilities','See what the app helps you do',cards(data['features'])))
    chunks.append(section('coverage','Controls & scope','Choose the right controls for your workflow',cards(data['coverage'])+'<div class="p-3 border rounded" style="background-color:#FFFFFF;"><h3 style="font-size:20px;color:#714B67;">Understand the scope</h3>'+para(data['scope'])+'</div>',True))
    req='<div class="p-4 border rounded mb-4" style="background-color:#F8F5EF;"><h3 style="color:#282532;font-size:21px;">Before installation</h3><ul style="font-size:16px;line-height:1.8;color:#625F6C;">'+''.join('<li>'+e(x)+'</li>' for x in data['requirements'])+'</ul>'+para('Odoo Online does not support installation of custom Python addons. Choose a deployment that permits custom modules.')+'</div>'
    chunks.append(section('setup','Getting started','Install, configure and validate',req+cards(data['steps'],'col-md-6')))
    chunks.append(section('workflow','Daily operation','Follow the workflow from start to finish',cards(data['workflow'],'col-md-6 col-lg-3'),True))
    gallery=para(data['screen_note'])
    for i,(file,title,body) in enumerate(data['screens'],1):
        assert (out/file).is_file(),file
        gallery+=f'<div class="row align-items-center my-4 py-3 border-bottom"><div class="col-lg-4"><p style="color:#9A7135;font-weight:700;font-size:12px;">WALKTHROUGH {i:02d}</p><h3 style="font-size:24px;color:#282532;">{e(title)}</h3>{para(body)}</div><div class="col-lg-8"><a href="{file}">'+image(file,title+' — existing '+('illustrative UI mockup' if data['module'].endswith('access_management') else 'module demonstration image'))+'</a></div></div>'
    chunks.append(section('screenshots','Product walkthrough','Explore the workspace',gallery))
    docs=cards([('Installation','Follow the six setup steps and validate using a test account.'),('Daily workflow','Use the illustrated walkthrough alongside the workflow guide.'),('Troubleshooting','Check configuration, permissions and the affected user session.')])
    docs+='<div class="text-center">'+''.join(f'<a class="d-inline-block p-3" style="color:#714B67;font-weight:700;" href="#{target}">{label} →</a>' for target,label in [('setup','Setup guide'),('workflow','Workflow'),('troubleshooting','Troubleshooting')])+'</div>'
    chunks.append(section('documentation','Documentation','Your guides, in one place',docs,True))
    chunks.append(section('troubleshooting','Troubleshooting','When something needs attention',cards(data['troubleshooting'])))
    chunks.append(section('faq','Questions & answers','Check the details before installing',cards(data['faqs'],'col-md-6'),True))
    support=para('For setup or configuration help, include your Odoo version, module version, affected action and exact error. Remove passwords and personal data from shared images.')+'<div class="p-4 rounded my-3" style="background-color:#302236;"><h3 style="font-size:24px;color:#FFFFFF;">Get help from Velkio</h3><a href="mailto:velkio.odoosolution@gmail.com" class="btn p-3" style="background-color:#FFFFFF;color:#714B67;font-weight:700;border-radius:8px;">Email support</a></div>'+image('velkio_logo.png','Velkio Odoo Solutions',180)+para('velkio.odoosolution@gmail.com')
    chunks.append(section('support','Velkio support','Get help with your app',support))
    chunks.append(section('release','Release information','Version '+data['version'],para('Module license: '+data['license']+'. This presentation includes Precision publisher branding, a module-specific app icon, an illustrated banner and setup documentation.')))
    return inline_layout('\n'.join(chunks+['</div>','</section>'])+'\n')

def build(kind,out):
    data=APPS[kind]
    out.mkdir(parents=True,exist_ok=True)
    assets=[('velkio-precision-logo.png',['velkio_logo.png']),('velkio-precision-mark.png',['velkio_mark.png']),(kind+'-app-icon.png',['icon.png','img.png']),(kind+'-banner.png',['banner.png'])]
    for source,targets in assets:
        for target in targets:
            shutil.copy2(BRAND/source,out/target)
    (out/'index.html').write_text(page(data,out),encoding='utf-8')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--module',choices=APPS,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    build(args.module,args.output)
