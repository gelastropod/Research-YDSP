from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.colors import ListedColormap
from PIL import Image
from .modes import MASKS
from .raster import image,class_map,changes

INK="#182d39"; NOTE="#43616e"; RED="#e54b2f"; GREEN="#136b63"
plt.rcParams.update({"font.family":"DejaVu Sans","text.color":INK,"axes.titlecolor":INK})
def canvas(w,h,title,sub):
    f=plt.figure(figsize=(w,h),facecolor="white")
    f.text(.045,.955,title,weight='bold',size=21,va='top')
    f.text(.045,.876,sub,size=11,va='top',color=NOTE)
    return f
def panel(f,rect,buf,title,classes=False):
    a=f.add_axes(rect)
    if classes:
        a.imshow(buf,interpolation='nearest',cmap=ListedColormap(["#e9eeee","#c4d4d5","#264752","#fff9e3","#f3ab48","#435d6e"]),vmin=0,vmax=5)
    else:a.imshow(image(buf),cmap='gray',vmin=0,vmax=255,interpolation='nearest')
    a.set_title(title,fontsize=12,weight='bold',pad=6)
    a.set_xticks([]);a.set_yticks([])
    for sp in a.spines.values():sp.set_color('#acbabe')
    return a
def save(f,p):f.savefig(p,dpi=180);plt.close(f)
def control(out,v,enc):
    f=canvas(11,7,'One penguin, six keyed masks','Each panel contains one 4 KiB sector. All six XEX variants encrypt the same pixels at the same address.')
    for i,(name,data) in enumerate([('Plaintext',v['base']),('AES-XTS',enc['XTS']['base'])]+[('XEX · '+k,enc[k]['base']) for k in MASKS]):
        panel(f,[.045+(i%4)*.239,.46-(i//4)*.348,.20,.28],data,name)
    f.text(.045,.037,'All panels use the same BC3 texture decoder. One 4 × 4 square occupies one 16-byte block.',size=10,color=NOTE)
    save(f,out/'01-mask-control.png')
def one_write(out,large):
    f=canvas(11,7.5,'One write: ECB preserves the penguin','Top: decoded BC3 textures. Bottom: repeated 16-byte values, coloured by frequency rank.')
    for i,(name,buf) in enumerate(large.items()):
        x=.08+i*.314
        panel(f,[x,.453,.235,.303],buf,{'Plaintext':'Plaintext','ECB':'AES-ECB','XTS':'AES-XTS'}[name])
        cm,d,r=class_map(buf)
        panel(f,[x,.082,.235,.303],cm,f'{r} / 256 tiles repeat',True)
    f.text(.045,.023,'Near-white in the XTS equality view means no repeated block. It is not a blank ciphertext.',size=10,color=NOTE)
    save(f,out/'02-one-snapshot.png')
def boundary(bits):
    mask=bits.reshape(16,16); edges=[]
    for y,x in zip(*np.where(mask)):
        l,t=4*x-.5,4*y-.5
        for dy,dx,p,q in [(-1,0,(l,t),(l+4,t)),(1,0,(l,t+4),(l+4,t+4)),(0,-1,(l,t),(l,t+4)),(0,1,(l+4,t),(l+4,t+4))]:
            if not (0<=y+dy<16 and 0<=x+dx<16 and mask[y+dy,x+dx]):edges.append([p,q])
    return edges

def outline(ax,bits):
    edges=boundary(bits)
    for color,width in [('white',3.8),(RED,2.2)]:
        ax.add_collection(LineCollection(edges,colors=color,linewidths=width,clip_on=False,zorder=5))
def two_write(out,v,enc):
    f=canvas(12,8.5,'Two writes: where did the penguin change?',
        'Red outlines enclose changed 16-byte tiles on Write 2. The ciphertext texture remains visible inside each outline.')
    sources=[v,enc['XTS'],enc['BLAKE3']]
    for j,(name,source) in enumerate(zip(['Plaintext','AES-XTS','XEX · BLAKE3'],sources)):
        for row,variant in enumerate(['base','edited']):
            ax=panel(f,[.093+.303*j,.454-.349*row,.243,.306],source[variant],name if not row else '')
            if j==0:ax.set_ylabel('WRITE '+str(row+1),fontsize=11,color=NOTE,labelpad=11,weight='bold')
            if row:
                bits=changes(source['base'],source['edited']);outline(ax,bits)
                ax.set_xlabel(['Eye blink, belly heart, foot marking',f'{bits.sum()} tiles in three regions',f'{bits.sum()} changed tiles: one suffix'][j],fontsize=10,color=INK,labelpad=8)
    f.text(.045,.026,'The eye-only control gave the same XEX outline as all three edits in this run. XTS separately outlines the belly and foot.' if
           np.array_equal(changes(sources[2]['base'],sources[2]['eye']),changes(sources[2]['base'],sources[2]['edited'])) else
           'Comparison uses full ciphertext block equality at the same address.',fontsize=11,color=GREEN)
    save(f,out/'03-two-snapshots.png')
    # Blink comparator: fixed outlines from corresponding block comparisons, over registered raw images.
    from PIL import ImageDraw,ImageFont
    frames=[]
    font=ImageFont.truetype(matplotlib.font_manager.findfont('DejaVu Sans'),20)
    for variant,w in [('base',1),('edited',2)]:
        im=Image.new('RGB',(842,340),'white');d=ImageDraw.Draw(im)
        d.text((12,5),f'Write {w}     |     Watch the eye, belly and foot',font=font,fill=INK)
        for i,(s,n) in enumerate(zip(sources,['Plaintext','AES-XTS','XEX · BLAKE3'])):
            im.paste(Image.fromarray(image(s[variant])).resize((256,256),Image.Resampling.NEAREST),(12+280*i,45))
            segments=boundary(changes(s['base'],s['edited']))
            for colour,width in [('white',5),(RED,3)]:
                for a,b in segments:
                    pts=[(round(12+280*i+4*(x+.5)),round(45+4*(y+.5))) for x,y in (a,b)]
                    d.line(pts,fill=colour,width=width)
            d.text((12+280*i,307),n,font=font,fill=INK)
        frames.append(im)
    # A single GIF palette prevents unchanged ciphertext from flickering on quantization.
    sheet=Image.new("RGB",(842,680))
    for i,frame in enumerate(frames): sheet.paste(frame,(0,340*i))
    palette=sheet.quantize(colors=256)
    frames=[im.quantize(palette=palette,dither=Image.Dither.NONE) for im in frames]
    frames[0].save(out/'blink.gif',save_all=True,append_images=frames[1:],duration=1050,loop=0,disposal=2,optimize=False)
    # Verify what the GIF viewer actually sees, for each of its 256 tile interiors.
    with Image.open(out/'blink.gif') as im:
        if im.n_frames!=2: raise AssertionError("missing blink frame")
        frame_a=np.array(im.convert("RGB"))
        im.seek(1)
        frame_b=np.array(im.convert("RGB"))
    for i,source in enumerate(sources):
        x=12+280*i
        changed=np.any(frame_a[45:301,x:x+256]!=frame_b[45:301,x:x+256],axis=2)
        tile_interiors=changed.reshape(16,16,16,16)[:,3:13,:,3:13].any(axis=(1,3)).ravel()
        if not np.array_equal(tile_interiors,changes(source['base'],source['edited'])):
            raise AssertionError("GIF pixels disagree with full-block comparison")
