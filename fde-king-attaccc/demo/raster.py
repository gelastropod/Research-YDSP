"""One 64 x 64 RGB penguin, stored as 256 row-major 4 x 4 tiles."""
import numpy as np
from collections import Counter
# Canonical legacy DDS header: 64 x 64, one mip level, DXT5, 4096-byte linear size.
import struct,io
from PIL import Image
HEADER=b"DDS "+struct.pack("<31I",124,0x81007,64,64,4096,0,0,*([0]*11),
                          32,4,int.from_bytes(b"DXT5","little"),0,0,0,0,0,0x1000,0,0,0,0)
def pack(a):
    stream=io.BytesIO()
    Image.fromarray(a).convert("RGBA").save(stream,format="DDS",pixel_format="DXT5")
    file=stream.getvalue()
    assert file[:4]==b"DDS " and file[84:88]==b"DXT5" and len(file)==4224
    return file[128:]
def image(buf):
    if len(buf)!=4096:raise ValueError("one 4 KiB texture required")
    rgba=Image.open(io.BytesIO(HEADER+buf)).convert("RGBA")
    return np.array(Image.alpha_composite(Image.new("RGBA",rgba.size,(224,224,224,255)),rgba).convert("RGB"))
def versions():
    from pathlib import Path
    from PIL import ImageDraw
    scale=12; bg=(164,218,238)
    art=Image.open(Path(__file__).resolve().parents[1]/"assets/tux-render.png").convert("RGBA")
    art=art.resize((52*scale,62*scale),Image.Resampling.LANCZOS)
    a=Image.new("RGB",(64*scale,64*scale),bg)
    a.paste(art,(6*scale,scale),art)
    data=np.asarray(a).copy()
    # Recolour warm foot pigments while retaining the vector drawing's shading.
    red,green,blue=np.moveaxis(data.astype(float),2,0)
    feet=(np.indices(red.shape)[0]>=42*scale)&(red>1.10*blue+6)&(green>.45*red)
    grey=(.10*red+.035*green).astype(np.uint8)
    for c in range(3):data[:,:,c][feet]=grey[feet]
    a=Image.fromarray(data)
    def small(im):return im.resize((64,64),Image.Resampling.LANCZOS)
    base=small(a)
    def composite_local(original,large,box):
        # Keep the antialias filter confined to the edit window.
        res=original.copy(); res.paste(small(large).crop(box),box);return res
    eye_hi=a.copy(); dr=ImageDraw.Draw(eye_hi)
    def pts(coords): return [tuple(round(v*scale) for v in p) for p in coords]
    dr.ellipse(pts([(31.0,9.9),(37.5,16.2)]),fill=(23,22,24))
    dr.arc(pts([(31.7,11.5),(36.9,14.6)]),0,180,fill=(234,232,222),width=10)
    eye=composite_local(base,eye_hi,(30,9,39,17))
    edited_hi=eye_hi.copy(); dr=ImageDraw.Draw(edited_hi)
    import math
    points=[]
    for t in np.linspace(0,2*math.pi,361):
        x=16*math.sin(t)**3
        y=13*math.cos(t)-5*math.cos(2*t)-2*math.cos(3*t)-math.cos(4*t)
        points.append((31.3+x*.52,37-y*.49))
    dr.polygon(pts(points),fill=(209,26,50))
    # A small extension of the existing right toe.
    dr.ellipse(pts([(53.4,51.9),(59.3,54.9)]),fill=(26,26,26))
    edited=composite_local(eye,edited_hi,(21,30,41,47))
    edited=composite_local(edited,edited_hi,(52,51,61,56))
    return {k:pack(np.asarray(im)) for k,im in [('base',base),('eye',eye),('edited',edited)]}
def changes(a,b):
    if len(a)!=len(b) or len(a)%16: raise ValueError("unaligned pair")
    return (np.frombuffer(a,np.uint8).reshape(-1,16)!=np.frombuffer(b,np.uint8).reshape(-1,16)).any(axis=1)
def class_map(buf):
    blocks=[buf[i:i+16] for i in range(0,len(buf),16)]
    c=Counter(blocks);lookup={b:i+1 for i,(b,n) in enumerate(c.most_common()) if n>1}
    return np.array([lookup.get(b,0) for b in blocks]).reshape(16,16),len(c),sum(n for n in c.values() if n>1)
