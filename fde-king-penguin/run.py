"""Reproduce the penguin figures, ciphertext snapshots and block counts."""
import argparse
from collections import Counter
import csv
from io import BytesIO
from pathlib import Path
import shutil
import struct
import subprocess
from tempfile import TemporaryDirectory
import numpy as np
from PIL import Image, ImageDraw
from demo.modes import MASKS, SECTOR0, keys, transform

ROOT = Path(__file__).resolve().parent
SECTOR = 4096
KEYS = keys("fde-king-attacks-01")
PANEL = 512
# Legacy DDS wrapper for one 64 x 64 DXT5 texture. Its bytes stay outside the sector.
HEADER = b"DDS " + struct.pack("<31I", 124, 0x81007, 64, 64, 4096, 0, 0,
    *([0]*11), 32, 4, int.from_bytes(b"DXT5", "little"), 0, 0, 0, 0, 0, 0x1000, 0, 0, 0, 0)
COLOURS = [(163, 207, 231), (42, 55, 74), (247, 220, 152),
           (206, 84, 80), (144, 113, 167), (91, 169, 143)]

class Layout:
    def __init__(self, name):
        self.name = name
        self.bc3 = name == "bc3"
        self.side = 256 if name == "rgba256" else 64
        self.cols = self.side // 4
        self.rows = self.side // 4 if self.bc3 else self.side

    def encode(self, image):
        if self.side != image.width:
            image = image.resize((self.side, self.side), Image.Resampling.LANCZOS)
        if not self.bc3:
            return image.tobytes()
        blob = BytesIO()
        image.save(blob, format="DDS", pixel_format="DXT5")
        raw = blob.getvalue()
        assert len(raw) == SECTOR + 128 and raw[:4] == b"DDS " and raw[84:88] == b"DXT5"
        return raw[128:]

    def decode(self, payload):
        if not self.bc3:
            return Image.frombytes("RGBA", (self.side, self.side), payload).convert("RGB")
        src = Image.open(BytesIO(HEADER + payload)).convert("RGBA")
        return Image.alpha_composite(Image.new("RGBA", src.size, "white"), src).convert("RGB")

    def grid(self, values):
        return Image.fromarray(np.asarray(values, dtype=np.uint8).reshape(
            self.rows, self.cols, *np.asarray(values).shape[1:])).resize((PANEL, PANEL), Image.Resampling.NEAREST)

    def guides(self, image):
        band = PANEL * 256 // (self.rows * self.cols)
        draw = ImageDraw.Draw(image)
        for y in range(band, PANEL, band):
            for x in range(0, PANEL, 10):
                draw.line((x,y,x+3,y), fill=(58,132,184), width=1)

    def marked(self, data, changed):
        im = self.decode(data).resize((PANEL,PANEL), Image.Resampling.NEAREST)
        grid = changed.reshape(self.rows,self.cols)
        draw = ImageDraw.Draw(im)
        dx,dy = PANEL//self.cols,PANEL//self.rows
        for y,x in zip(*np.where(grid)):
            x,y=int(x),int(y)
            l,t,r,b=x*dx,y*dy,(x+1)*dx-1,(y+1)*dy-1
            for sy,sx,line in [(-1,0,(l,t,r,t)),(1,0,(l,b,r,b)),(0,-1,(l,t,l,b)),(0,1,(r,t,r,b))]:
                if not (0 <= y+sy < self.rows and 0 <= x+sx < self.cols and grid[y+sy,x+sx]):
                    draw.line(line, fill=(236,52,36), width=2)
        return im

def blocks(data):
    return [data[i:i+16] for i in range(0,len(data),16)]

def xor(pair):
    a,b = (np.frombuffer(p,np.uint8).reshape(-1,16) for p in pair)
    return a ^ b

def eq(data, layout):
    bs = blocks(data)
    counts = Counter(bs)
    colours = {b: COLOURS[i] if i < len(COLOURS) else (160,160,160)
               for i,(b,n) in enumerate(counts.most_common()) if n>1}
    values = [colours.get(b,(244,244,244)) for b in bs]
    return layout.grid(values), sum(n for n in counts.values() if n > 1)

class Renderer:
    def __init__(self, work):
        self.work=work
        self.i=0

    def panel(self, image):
        self.i+=1
        filename=f"panel-{self.i:03d}.png"
        image.convert("RGB").resize((PANEL,PANEL),Image.Resampling.NEAREST).save(self.work/filename)
        return r"\includegraphics[width=\panelwidth]{"+filename+"}"

    def figure(self,name,title,rows,width=3.45):
        n=len(rows[0])
        assert all(len(row)==n for row in rows)
        body="\n".join(" & ".join(row)+r" \\[3pt]" for row in rows)
        tex=r"""\documentclass{article}
\usepackage{graphicx}
\pagestyle{empty}
\newlength{\panelwidth}
\begin{document}
\setlength{\panelwidth}{WIDTHcm}
\setbox0=\hbox{\begin{tabular}{@{\hspace{8pt}}*{NC}{c}@{\hspace{8pt}}}
\multicolumn{NC}{c}{\rule{0pt}{22pt}\Large\bfseries TITLE}\\[8pt]
ROWS
\end{tabular}}
\pdfpagewidth=\wd0 \pdfpageheight=\dimexpr\ht0+\dp0+6pt\relax
\hoffset=-1in \voffset=-1in
\shipout\box0
\end{document}""".replace("WIDTH",str(width)).replace("NC",str(n)).replace("TITLE",title).replace("ROWS",body)
        (self.work/f"{name}.tex").write_text(tex,encoding="utf-8")
        result=subprocess.run(["pdflatex","-halt-on-error","-interaction=nonstopmode",f"{name}.tex"],
                              cwd=self.work,capture_output=True,text=True)
        if result.returncode:
            raise RuntimeError(result.stdout[-5000:]+result.stderr)
        subprocess.run(["pdftoppm","-singlefile","-scale-to","1800","-png",f"{name}.pdf",name],cwd=self.work,check=True)
        return self.work/f"{name}.png"

def gif(a,b,path):
    frames=[Image.open(p).convert("RGB") for p in (a,b)]
    assert frames[0].size == frames[1].size
    for im in frames:
        im.thumbnail((960,680))
    w,h=frames[0].size
    pair=Image.new("RGB",(w,h*2),"white")
    for j,im in enumerate(frames):
        pair.paste(im,(0,j*h))
    pal=pair.quantize(256)
    f0,f1=[im.quantize(palette=pal,dither=Image.Dither.NONE) for im in frames]
    f0.save(path,save_all=True,append_images=[f1],duration=1000,loop=0,optimize=False,disposal=2)
    with Image.open(path) as gif_image:
        assert gif_image.n_frames == 2

def slug(name):
    return name.lower().replace(" ","-")

def run(layout,images,out,tex_dir):
    out.mkdir(parents=True,exist_ok=True)
    rawdir=out/"payloads"
    rawdir.mkdir(exist_ok=True)
    pt=[layout.encode(im) for im in images]
    n=len(pt[0])//16
    assert len(pt[0])==len(pt[1])==layout.rows*layout.cols*16 and n%256==0
    data={"Plaintext":pt}
    for name in ("ECB","XTS",*MASKS):
        data[name]=[transform(name,b,SECTOR,KEYS) for b in pt]
        assert [transform(name,b,SECTOR,KEYS,decrypt=True) for b in data[name]] == pt
    xors={name:xor(pair) for name,pair in data.items()}
    changed={name:x.any(axis=1) for name,x in xors.items()}
    d=changed["Plaintext"].reshape(-1,256)
    assert np.array_equal(changed["XTS"],changed["Plaintext"])
    assert np.array_equal(changed["ECB"],changed["Plaintext"])
    for name in MASKS:
        # Same prefix and same first divergence; later ciphertext may coincide again.
        for p,c in zip(d,changed[name].reshape(-1,256)):
            assert (p.any()==c.any()) and (not p.any() or np.argmax(p)==np.argmax(c))
    for name,pair in data.items():
        for j,b in enumerate(pair,1):
            (rawdir/f"{slug(name)}-{j}.bin").write_bytes(b)
    groups=["Plaintext","XTS","BLAKE3"]
    labels=["Plaintext","AES-XTS","XEX Ratchet (BLAKE3)"]
    cases=["Plaintext","ECB","XTS"]
    with TemporaryDirectory(prefix="penguin-latex-") as tmp:
        tmp=Path(tmp)
        if tex_dir:
            for name in ("pdflatex.fmt","pdftex.map"):
                p=tex_dir/name
                if p.exists():
                    shutil.copyfile(p,tmp/name)
        r=Renderer(tmp)
        titles=["Attack 1 -- ECB vs AES-XTS",
                "Attack 2 Demonstrated -- AES-XTS vs XEX Ratchet",
                "Attack 2 Difference of Two Snapshots -- AES-XTS vs XEX Ratchet",
                "Different Hashes in Attack 2"]
        eqs=[eq(data[m][1],layout) for m in cases]
        r.figure("01-ecb-xts",titles[0],[["","Plaintext","AES-ECB","AES-XTS"],
            ["Write 2",*[r.panel(layout.decode(data[m][1])) for m in cases]],
            ["Equality classes",*[r.panel(im) for im,_ in eqs]],
            ["Repeated blocks",*[f"{i:,} / {n:,}" for _,i in eqs]]])
        panels=[[r.panel(layout.marked(data[m][j],changed[m])) for m in groups] for j in (0,1)]
        r.figure("02-snapshots",titles[1],[["",*labels],["Write 1",*panels[0]],["Write 2",*panels[1]]])
        for j in (0,1):
            r.figure(f"frame-{j}",titles[1],[labels,panels[j],["",f"Write {j+1}",""]],4)
        gif(tmp/"frame-0.png",tmp/"frame-1.png",out/"blink.gif")
        def binary(m):
            im=layout.grid(changed[m].astype("uint8")*255).convert("RGB")
            layout.guides(im)
            return im
        def heat(m):
            x=np.unpackbits(xors[m],axis=1).sum(axis=1)
            return layout.grid(np.rint(x*255/128))
        r.figure("03-difference",titles[2],[["",*labels],
            ["Changed blocks",*[r.panel(binary(m)) for m in groups]],
            ["Bits changed per block",*[r.panel(heat(m)) for m in groups]],
            ["Total changed",*[f"{changed[m].sum():,} / {n:,}" for m in groups]]])
        variants=[]
        for i in (0,3):
            ms=MASKS[i:i+3]
            variants.extend([["",*ms],["Write 2",*[r.panel(layout.decode(data[m][1])) for m in ms]],
               ["Changed blocks",*[r.panel(binary(m)) for m in ms]]])
        r.figure("04-hashes",titles[3],variants,3)
        for f in tmp.glob("0*"):
            if f.suffix in (".png",".pdf"):
                shutil.copyfile(f,out/f.name)
    with (out/"block-counts.csv").open("w",newline="") as f:
        w=csv.writer(f)
        w.writerow(["scheme","total_blocks","repeated_blocks_write_2","changed_blocks","changed_sectors"])
        for m,pair in data.items():
            w.writerow([m,n,eq(pair[1],layout)[1],int(changed[m].sum()),int(changed[m].reshape(-1,256).any(axis=1).sum())])
    with (out/"sector-counts.csv").open("w",newline="") as f:
        w=csv.writer(f)
        w.writerow(["scheme","sector_address","changed_blocks","first_changed_block_zero_based"])
        for m,x in changed.items():
            for j,sector in enumerate(x.reshape(-1,256)):
                idx=np.flatnonzero(sector)
                w.writerow([m,SECTOR0+j,len(idx),int(idx[0]) if len(idx) else ""])

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path,default=ROOT/"results")
    p.add_argument("--case",choices=["all","bc3","rgba","rgba256"],default="all")
    p.add_argument("--tex-dir",type=Path,help="Optional path to a custom TeX format/font map")
    a=p.parse_args()
    if not all(shutil.which(t) for t in ("pdflatex","pdftoppm")):
        p.error("install LaTeX (pdflatex) and Poppler (pdftoppm)")
    images=[Image.open(ROOT/"assets"/f"snapshot-{i}.png").convert("RGBA") for i in (1,2)]
    px=[np.asarray(im) for im in images]
    y,x=np.where(np.any(px[0]!=px[1],axis=2))
    assert len(x)==86 and np.all(
        ((24<=x)&(x<29)&(11<=y)&(y<17)) | ((27<=x)&(x<35)&(33<=y)&(y<40)))
    for name in (["bc3","rgba"] if a.case=="all" else [a.case]):
        run(Layout(name),images,a.output/name,a.tex_dir.resolve() if a.tex_dir else None)

if __name__=="__main__":
    main()
