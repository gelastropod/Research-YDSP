"""One 64 x 64 grey image, stored as 256 row-major 4 x 4 tiles."""
import numpy as np
from collections import Counter
PALETTE={'.':224,'#':29,'w':248,'e':32,'b':132}
SPRITE=[
'................','......####......','.....######.....','....########....',
'....#wwwwww#....','....#wewwew#....','....#wwbbww#....','...###wwww###...',
'..###wwwwww###..','.###wwwwwwww###.','..##wwwwwwww##..','...#wwwwwwww#...',
'....#wwwwww#....','.....######.....','...bbbb..bbbb...','..bbbbb..bbbbb..']
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
    a=np.array([[PALETTE[c] for c in row] for row in SPRITE],dtype=np.uint8).repeat(4,0).repeat(4,1)
    eye=a.copy();eye[20:24,36:40]=248;eye[22,36:40]=90 # blink
    edited=eye.copy()
    for j,row in enumerate(("11011","11111","01110","00100")):
        for i,bit in enumerate(row):
            if bit=="1": edited[32+4*j:36+4*j,20+4*i:24+4*i]=82
    edited[56:60,40:44]=248 # white marking on right foot
    return dict(base=pack(a),eye=pack(eye),edited=pack(edited))
def changes(a,b):
    if len(a)!=len(b) or len(a)%16: raise ValueError("unaligned pair")
    return (np.frombuffer(a,np.uint8).reshape(-1,16)!=np.frombuffer(b,np.uint8).reshape(-1,16)).any(axis=1)
def class_map(buf):
    blocks=[buf[i:i+16] for i in range(0,len(buf),16)]
    c=Counter(blocks);lookup={b:i+1 for i,(b,n) in enumerate(c.most_common()) if n>1}
    return np.array([lookup.get(b,0) for b in blocks]).reshape(16,16),len(c),sum(n for n in c.values() if n>1)
