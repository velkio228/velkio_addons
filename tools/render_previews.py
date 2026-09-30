"""Capture the actual standalone HTML pages in Firefox, without extra CSS."""
from pathlib import Path
import subprocess
from store_content import APPS
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'release'/'previews'
out.mkdir(parents=True,exist_ok=True)
profile=Path('/tmp/velkio17-firefox-profile')
profile.mkdir(exist_ok=True)
for key,data in APPS.items():
    page=ROOT/data['module']/'static'/'description'/'index.html'
    for label,size in [('desktop','1440,1100'),('mobile','390,1100')]:
        dest=out/f'{key}-{label}.png'
        result=subprocess.run(['/snap/firefox/current/usr/lib/firefox/firefox','--headless','--no-remote','--profile',str(profile),'--screenshot',str(dest),'--window-size',size,page.as_uri()],capture_output=True,text=True,timeout=25)
        assert result.returncode==0,result.stderr
        print(dest)
