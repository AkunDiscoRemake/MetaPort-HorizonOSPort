# SPDX-License-Identifier: GPL-3.0-only
"""Prepare user-supplied demo branding; does not patch or certify the original APK.

Reproduce with Pillow==11.3.0. Original artwork is retained unmodified.
"""
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageOps

ROOT=Path(__file__).resolve().parents[1]/'port/branding'
NAME='MetaPort official demo by ahambolota'
SIZES={'mdpi':48,'hdpi':72,'xhdpi':96,'xxhdpi':144,'xxxhdpi':192}


def generate():
    original=ROOT/'metaport-icon-original.png'
    source=Image.open(original);source.load()
    if source.size!=(1254,1254):raise ValueError('Unexpected source image dimensions')
    source=source.convert('RGBA');res=ROOT/'android-res';files=[]
    for density,size in SIZES.items():
        path=res/f'mipmap-{density}/ic_metaport_demo.png';path.parent.mkdir(parents=True,exist_ok=True)
        source.resize((size,size),Image.Resampling.LANCZOS).save(path);files.append(path)
    # Keep the full image, with extra padding for adaptive launcher masks.
    foreground=Image.new('RGBA',(432,432),(0,0,0,0))
    art=ImageOps.contain(source,(388,388),Image.Resampling.LANCZOS)
    foreground.alpha_composite(art,((432-art.width)//2,(432-art.height)//2))
    path=res/'drawable-nodpi/metaport_demo_foreground.png';path.parent.mkdir(parents=True,exist_ok=True)
    foreground.save(path);files.append(path)
    texts={
        'mipmap-anydpi-v26/ic_metaport_demo.xml':'''<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@color/metaport_demo_icon_background" />
    <foreground android:drawable="@drawable/metaport_demo_foreground" />
</adaptive-icon>
''',
        'values/metaport_demo_branding.xml':f'''<resources>
    <string name="metaport_demo_app_name" translatable="false">{NAME}</string>
    <color name="metaport_demo_icon_background">#FFFFFF</color>
</resources>
'''}
    for name,text in texts.items():
        path=res/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text);files.append(path)
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    record={'display_name':NAME,'source_commit':'6c2481a','source_git_blob':'2006fec5c166a6924427d26fdb2afb32d394fa23',
            'source_path_in_main':'file_00000000f6dc820e80044d81d6fc2880.png',
            'original_sha256':sha(original),'original_dimensions':[1254,1254],
            'generator':'Pillow 11.3.0; Lanczos; no crop or redraw',
            'generated_files':{str(p.relative_to(ROOT)):sha(p) for p in files},
            'applied_to_original_apk':False,'functional_demo_validated':False,
            'scope':'User-requested project branding, not a claim of Meta certification'}
    (ROOT/'branding.json').write_text(json.dumps(record,indent=2)+'\n')

if __name__=='__main__':generate()
