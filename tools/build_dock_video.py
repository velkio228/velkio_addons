from pathlib import Path
import base64,struct
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
out=Path(__file__).resolve().parents[1]/'velkio_odoo_dock/static/description'
slides=[('banner.png','Velkio Odoo Dock — your apps, your workspace, your way'),('screenshot_workspace_dark.png','Your company logo, live clock and personal greeting'),('screenshot_workspace_light.png','A clear workspace in light and dark mode'),('screenshot_overview.png','Browse apps and recent work from Show Applications'),('screenshot_search.png','Search your accessible apps, menus and recent records'),('screenshot_appearance.png','Choose a position, style, icon size and accent colour'),('screenshot_behaviour.png','Personalise auto-hide, badges, shortcuts and history'),('screenshot_pin_apps.png','Pin your everyday apps — then drag to reorder')]
frames=[{'src':'data:image/png;base64,'+base64.b64encode((out/f).read_bytes()).decode(),'caption':t} for f,t in slides]
o=Options();o.add_argument('-headless');o.binary_location='/snap/firefox/current/usr/lib/firefox/firefox'
d=webdriver.Firefox(options=o,service=Service('/snap/firefox/current/usr/lib/firefox/geckodriver',log_output='/tmp/dock-video-gecko.log'));d.set_script_timeout(90)
try:
    d.get('about:blank')
    result=d.execute_async_script('''
      const frames=arguments[0], done=arguments[arguments.length-1];
      (async()=>{
        const images=await Promise.all(frames.map(f=>new Promise((resolve,reject)=>{const i=new Image();i.onload=()=>resolve(i);i.onerror=reject;i.src=f.src;})));
        const canvas=document.createElement('canvas');canvas.width=1920;canvas.height=1080;document.body.appendChild(canvas);
        const ctx=canvas.getContext('2d');const chunks=[];
        const recorder=new MediaRecorder(canvas.captureStream(15),{mimeType:'video/webm;codecs=vp8',videoBitsPerSecond:2200000});
        recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data)};
        recorder.onstop=()=>{const reader=new FileReader();reader.onload=()=>done({video:reader.result.split(',')[1],type:recorder.mimeType});reader.readAsDataURL(new Blob(chunks,{type:recorder.mimeType}));};
        const start=performance.now(), dwell=4000;
        function draw(){const elapsed=performance.now()-start,index=Math.min(images.length-1,Math.floor(elapsed/dwell)), image=images[index];
          ctx.fillStyle='#18131f';ctx.fillRect(0,0,1920,1080);
          const scale=Math.min(1920/image.width,990/image.height), width=image.width*scale,height=image.height*scale;
          ctx.drawImage(image,(1920-width)/2,(990-height)/2,width,height);
          ctx.fillStyle='#302236';ctx.fillRect(0,990,1920,90);ctx.fillStyle='#ffffff';ctx.font='500 30px Arial';ctx.textAlign='center';ctx.fillText(frames[index].caption,960,1030);
          ctx.fillStyle='#e5be7e';ctx.fillRect(0,1070,1920*Math.min(1,elapsed/(dwell*images.length)),10);
          if(elapsed<dwell*images.length){requestAnimationFrame(draw)}else{recorder.stop();}
        }
        recorder.start();draw();
      })().catch(e=>done({error:String(e)}));
    ''',frames)
    assert 'video' in result,result
    data=bytearray(base64.b64decode(result['video']))
    # Firefox MediaRecorder writes a zero duration. Fill the existing float slot
    # without shifting container offsets so native controls can seek normally.
    offset=data.find(bytes.fromhex('448988'),0,300)
    assert offset>=0, 'Expected a WebM duration slot'
    data[offset+3:offset+11]=struct.pack('>d',len(slides)*4000.0)
    (out/'demo.webm').write_bytes(data)
    assert data[:4]==bytes.fromhex('1a45dfa3')
    print('Created 32-second captioned WebM walkthrough:',len(data),'bytes',result['type'])
finally:
    d.quit()
