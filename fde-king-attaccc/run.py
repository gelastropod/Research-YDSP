"""Generate the three figures, raw lossless rasters, and the audit CSVs."""
import argparse,csv,json
from pathlib import Path
from PIL import Image
import numpy as np
from demo.modes import MASKS,NAMES,keys,transform,SECTOR0
from demo.raster import HEADER,versions,image,changes,class_map
from demo.figures import control,one_write,two_write

def indices(mask):
    return [int(i) for i in np.flatnonzero(mask)]
def first_by_sector(bools,unit):
    size=unit//16
    return {str(SECTOR0+i//size):indices(bools[i:i+size])[0] for i in range(0,len(bools),size) if bools[i:i+size].any()}
def csvwrite(path,entries):
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=entries[0]);w.writeheader();w.writerows(entries)
def main(out,seed):
    for sub in ("figure","evidence","rasters"): (out/sub).mkdir(parents=True,exist_ok=True)
    k=keys(seed);v=versions()
    def png(file,buf,side):
        (out/"rasters"/(file+".dds")).write_bytes(HEADER+buf)
        Image.fromarray(image(buf)).save(out/"rasters"/(file+".png"))
    for label,buf in v.items():png("small-plain-"+label,buf,64)
    comparisons=[];large={"Plaintext":v["edited"]}
    for name in ("ECB","XTS"):
        ciphertext=transform(name,large["Plaintext"],4096,k)
        if transform(name,ciphertext,4096,k,decrypt=True)!=large["Plaintext"]:raise AssertionError("sector round trip")
        large[name]=ciphertext
    stats=[]
    for name,buf in large.items():
        png("one-"+name,buf,64)
        classes,d,r=class_map(buf)
        if name=="Plaintext": ground=classes
        if name=="ECB" and not np.array_equal(classes,ground):raise AssertionError("ECB equality classes changed")
        stats.append(dict(mode=name,total_blocks=256,distinct_blocks=d,blocks_in_repeated_classes=r))
    csvwrite(out/"evidence"/"one-write.csv",stats)
    for unit in (4096,):
        encrypted={}
        for name in NAMES:
            enc=encrypted[name]={label:transform(name,buf,unit,k) for label,buf in v.items()}
            for label,buf in enc.items():
                if transform(name,buf,unit,k,decrypt=True)!=v[label]: raise AssertionError((name,unit,label))
                png(f"small-{unit}-{name}-{label}",buf,64)
            for a,b,title in [("base","base","unchanged"),("base","eye","eye only"),("base","edited","eye, belly and foot"),("eye","edited","belly and foot after eye")]:
                ca=enc[a]; cb=enc[b] if a!=b else transform(name,v[b],unit,k)
                pd=changes(v[a],v[b]);cd=changes(ca,cb)
                if name in ("ECB","XTS") and not np.array_equal(pd,cd):raise AssertionError("position equality")
                if first_by_sector(pd,unit)!=first_by_sector(cd,unit):raise AssertionError("prefix identity")
                suffix=np.zeros_like(pd)
                size=unit//16
                for off in range(0,len(pd),size):
                    local=indices(pd[off:off+size])
                    if local:suffix[off+local[0]:off+size]=True
                comparisons.append(dict(unit_bytes=unit,mode=name,comparison=title,
                     plaintext_changed=json.dumps(indices(pd)),ciphertext_changed=json.dumps(indices(cd)),
                     changed_count=int(cd.sum()),first_in_sector_local=json.dumps(first_by_sector(cd,unit)),
                     unchanged_at_or_after_first=(json.dumps(indices(suffix & ~cd)) if name in MASKS else "")))
        if unit==4096:
            control(out/"figure",v,encrypted);two_write(out/"figure",v,encrypted)
    one_write(out/"figure",large)
    csvwrite(out/"evidence"/"two-writes.csv",comparisons)
    (out/"evidence"/"fixture.json").write_text(json.dumps(dict(public_seed=seed,first_sector=SECTOR0,units=[4096],checks="round trips, independent identical rewrites, common-prefix identity, ECB/XTS equality maps"),indent=2)+"\n")
    print("Wrote three figures, a verified two-frame GIF, DDS/PNG pairs and 32 comparison rows.")
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,default=Path(__file__).resolve().parent)
    p.add_argument("--seed",default="fde-king-attacks-01",help="public fixture key seed")
    a=p.parse_args();main(a.out,a.seed)
