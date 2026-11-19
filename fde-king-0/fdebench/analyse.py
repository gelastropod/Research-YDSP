"""Build clean figures, summary CSVs, and a concise README from the actual run."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

LABELS={'ecb_bulk':'AES-ECB · bulk', 'xts_manual_soft':'AES-XTS · manual, AES-NI off',
        'xts_manual_ni':'AES-XTS · manual, AES-NI enabled','xts_library':'AES-XTS · OpenSSL, full sector',
        'xex_kmac128':'XEX · KMAC128','xex_blake3':'XEX · keyed BLAKE3',
        'xex_blake2s':'XEX · keyed BLAKE2s','xex_blake2b':'XEX · keyed BLAKE2b',
        'xex_siphash128':'XEX · SipHash-2-4-128','lrw_poly':'LRW-Polynomial',
        'cbc_mac':'AES-MAC-CBC'}
COLORS={s:('#8468a5' if s=='lrw_poly' else '#d18432' if s=='cbc_mac' else '#227c79' if s.startswith('xex_') else '#385a82') for s in LABELS}

def name(s):return LABELS.get(s,s)
def short(s):return name(s).replace('XEX · ','').replace('AES-XTS · ','XTS ').replace('AES-ECB · bulk','ECB')

def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+[
        '| '+' | '.join(map(str,row))+' |' for row in rows])

def save(fig,path):
    fig.savefig(path,dpi=180,bbox_inches='tight',facecolor='white');plt.close(fig)

def style(ax):
    ax.spines[['top','right']].set_visible(False)
    ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True)

def analyse(outdir='results'):
    out=Path(outdir);figdir=out.parent/('figures' if out.name=='results' else out.name+'_figures')
    figdir.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.titlesize':12,
                         'axes.labelsize':10,'figure.facecolor':'white'})
    env=json.loads((out/'environment.json').read_text());cfg=env['config']
    raw=pd.read_csv(out/'throughput_raw.csv')
    group=raw.groupby(['scheme','sector_size','direction'])
    summary=group.agg(mib_s=('mib_s','median'),ns_sector=('ns_sector','median'),ns_byte=('ns_byte','median'),
                      throughput_q25=('mib_s',lambda x:x.quantile(.25)),throughput_q75=('mib_s',lambda x:x.quantile(.75))).reset_index()
    summary.sort_values(['sector_size','direction','mib_s'],ascending=[True,True,False]).to_csv(out/'throughput_summary.csv',index=False)
    enc=summary.query('sector_size==4096 and direction=="encrypt"').set_index('scheme').sort_values('mib_s',ascending=False)
    dec=summary.query('sector_size==4096 and direction=="decrypt"').set_index('scheme')
    order=list(enc.index)
    fastest_xex=next(s for s in order if s.startswith('xex_'))
    candidates=[s for s in order if s.startswith('xex_')]
    fastest_hash=max(candidates,key=lambda s:enc.loc[s,'mib_s'])

    # RQ2: fastest at top; four panels retain both sector sizes and directions.
    fig,axes=plt.subplots(2,2,figsize=(16,12),sharey=True)
    for row,size in enumerate((512,4096)):
        for col,direction in enumerate(('encrypt','decrypt')):
            ax=axes[row,col];view=summary.query('sector_size==@size and direction==@direction').set_index('scheme').reindex(order)
            vals=view.mib_s.to_numpy();lo=vals-view.throughput_q25.to_numpy();hi=view.throughput_q75.to_numpy()-vals
            y=np.arange(len(order));ax.barh(y,vals,color=[COLORS[s] for s in order],xerr=np.maximum(0,np.array([lo,hi])),capsize=2)
            ax.set_xscale('log');ax.set_yticks(y,[name(s) for s in order]);ax.set_ylim(len(order)-.4,-.6)
            ax.set_xlabel('MiB/s · logarithmic scale');ax.set_title(f'{size}-byte sectors · {direction}')
            for yy,v in zip(y,vals):ax.text(v*1.07,yy,f'{v:,.2f}',va='center',fontsize=8)
            ax.set_xlim(max(.01,min(vals)*.7),max(vals)*3);style(ax)
    fig.suptitle('RQ2  Sector throughput · median and interquartile range',fontsize=16)
    fig.tight_layout();save(fig,figdir/'rq2_throughput.png')

    # RQ1: internal library stages are explicitly opaque rather than invented.
    comp=pd.read_csv(out/'components.csv');ce=comp.query('direction=="encrypt"').set_index('scheme').reindex(order)
    parts=[('seed_ns','Sector seed'),('mask_ns','Mask / tweak'),('data_ns','Data path'),('other_ns','Loop / timers'),('library_ns','Opaque library call')]
    palette=['#93b5c6','#227c79','#385a82','#d6d6d6','#55565e']
    fig,ax=plt.subplots(figsize=(12,7));left=np.zeros(len(order))
    for (key,label),color in zip(parts,palette):
        v=ce[key].to_numpy()/ce.wall_ns.to_numpy()*100
        ax.barh(np.arange(len(order)),v,left=left,label=label,color=color);left+=v
    ax.set_yticks(np.arange(len(order)),[name(s) for s in order]);ax.invert_yaxis();ax.set_xlim(0,100)
    ax.set_xlabel('Share of instrumented Python time (%)');ax.set_title('RQ1  Encryption component cost · 4096-byte sectors')
    ax.legend(loc='upper center',bbox_to_anchor=(.5,-.12),ncol=3,frameon=False);style(ax);save(fig,figdir/'rq1_components.png')

    hashes=pd.read_csv(out/'hash_raw.csv')
    hs=hashes.groupby(['mask','dependent']).agg(ns_call=('ns_call','median'),q25=('ns_call',lambda x:x.quantile(.25)),q75=('ns_call',lambda x:x.quantile(.75))).reset_index()
    hs['calls_s']=1e9/hs.ns_call;hs.to_csv(out/'hash_summary.csv',index=False)
    hd=hs[hs.dependent].set_index('mask').sort_values('ns_call')
    hi=hs[~hs.dependent].set_index('mask')
    fig,ax=plt.subplots(figsize=(11,6));y=np.arange(len(hd))
    for shift,dependent,color,label in [(-.18,False,'#385a82','Independent inputs'),(.18,True,'#227c79','Output fed into next input')]:
        v=hs[hs.dependent==dependent].set_index('mask').reindex(hd.index)
        ax.barh(y+shift,v.ns_call,height=.32,color=color,label=label,
                xerr=np.maximum(0,np.array([v.ns_call-v.q25,v.q75-v.ns_call])),capsize=2)
    ax.set_yticks(y,[short(mask_label(s)) for s in hd.index]);ax.invert_yaxis();ax.set_xscale('log')
    ax.set_xlabel('ns per 48-byte input / 16-byte output · logarithmic scale')
    ax.set_title('RQ3  Mask function cost · median and interquartile range');ax.legend(frameon=False);style(ax)
    save(fig,figdir/'rq3_hash_cost.png')

    reads=pd.read_csv(out/'random_access_raw.csv')
    rs=reads.groupby(['scheme','block']).agg(ns_read=('elapsed_ns','median'),ciphertext_bytes_required=('ciphertext_bytes_required','first')).reset_index()
    rs.to_csv(out/'random_access_summary.csv',index=False)
    selected=list(dict.fromkeys(['ecb_bulk','xts_manual_ni','xts_library',fastest_hash,'xex_blake3','cbc_mac','lrw_poly']))
    fig,ax=plt.subplots(figsize=(11,5))
    for s in selected:
        v=rs[rs.scheme==s];ax.plot(v.block,v.ns_read/1000,marker='o',label=short(s))
    ax.set_yscale('log');ax.set_xlabel('Requested intra-sector block (one-based)');ax.set_ylabel('Median µs per read · log scale')
    ax.set_xticks(sorted(rs.block.unique()))
    read_min=min(rs[rs.scheme.isin(selected)].ns_read)/1000
    read_max=max(rs[rs.scheme.isin(selected)].ns_read)/1000
    ticks=[v for p in range(-3,6) for m in (1,2,5) if read_min/1.2 <= (v:=m*10.0**p) <= read_max*1.2]
    if ticks:ax.set_yticks(ticks,[f'{v:g}' for v in ticks])
    ax.set_title('RQ4  Direct reads from an already available 4096-byte ciphertext sector')
    ax.legend(loc='upper center',bbox_to_anchor=(.5,-.16),ncol=2,frameon=False);style(ax);save(fig,figdir/'rq4_random_access.png')

    threads=pd.read_csv(out/'thread_raw.csv')
    ts=threads.groupby(['scheme','direction','workers']).mib_s.median().reset_index()
    base=ts[ts.workers==1][['scheme','direction','mib_s']].rename(columns={'mib_s':'baseline'})
    ts=ts.merge(base,on=['scheme','direction']);ts['speedup']=ts.mib_s/ts.baseline;ts['efficiency']=ts.speedup/ts.workers
    ts.to_csv(out/'thread_summary.csv',index=False)
    fig,axes=plt.subplots(1,2,figsize=(14,5),sharey=True)
    for ax,direction in zip(axes,('encrypt','decrypt')):
        for s in selected:
            v=ts[(ts.scheme==s)&(ts.direction==direction)]
            line,=ax.plot(v.workers,v.speedup,marker='o',markersize=4,label=short(s))
            trials=threads[(threads.scheme==s)&(threads.direction==direction)].groupby('workers').mib_s
            qlo=trials.quantile(.25).reindex(v.workers).to_numpy()/v.baseline.to_numpy()
            qhi=trials.quantile(.75).reindex(v.workers).to_numpy()/v.baseline.to_numpy()
            ax.fill_between(v.workers,qlo,qhi,color=line.get_color(),alpha=.08)
        ax.axhline(1,color='#888888',ls='--',lw=1)
        ax.set_xlabel('Threads');ax.set_title(direction.capitalize());ax.set_xticks(sorted(ts.workers.unique()));style(ax)
    axes[0].set_ylabel('Speedup relative to one thread');axes[1].legend(loc='upper left',bbox_to_anchor=(1.02,1),frameon=False)
    fig.suptitle('RQ4  Parallel processing of independent sectors',fontsize=14);fig.tight_layout();save(fig,figdir/'rq4_thread_scaling.png')

    within=pd.read_csv(out/'within_sector_raw.csv')
    ws=within.groupby(['scheme','workers']).ns_sector.median().reset_index()
    wb=ws[ws.workers==1][['scheme','ns_sector']].rename(columns={'ns_sector':'baseline'})
    ws=ws.merge(wb,on='scheme');ws['speedup']=ws.baseline/ws.ns_sector
    ws.to_csv(out/'within_sector_summary.csv',index=False)
    fig,ax=plt.subplots(figsize=(10,4.7))
    for s in selected:
        v=ws[ws.scheme==s]
        if len(v):ax.plot(v.workers,v.speedup,marker='o',label=short(s))
    ax.axhline(1,color='#888888',ls='--',lw=1);ax.set_xticks(sorted(ws.workers.unique()))
    ax.set_xlabel('Threads within one sector');ax.set_ylabel('Decryption speedup');ax.set_title('RQ4  Splitting a single 4096-byte sector among threads')
    ax.legend(loc='upper left',bbox_to_anchor=(1.02,1),frameon=False);style(ax);save(fig,figdir/'rq4_within_sector.png')

    write_report(out,figdir,env,summary,comp,hs,rs,ts,ws)

def mask_label(s):return s if s in ('cbc_mac','lrw_poly') else 'xex_'+s

def write_report(out,figdir,env,summary,comp,hs,rs,ts,ws):
    enc=summary.query('sector_size==4096 and direction=="encrypt"').set_index('scheme').sort_values('mib_s',ascending=False)
    dec=summary.query('sector_size==4096 and direction=="decrypt"').set_index('scheme')
    opt=pd.read_csv(out/'optimization_raw.csv').groupby(['scheme','direction','implementation']).ns_sector.median().unstack('implementation')
    opt['speedup']=opt.reference/opt.optimized;opt.to_csv(out/'optimization_summary.csv')
    c=comp.query('direction=="encrypt"').set_index('scheme')
    fastest=max([x for x in enc.index if x.startswith('xex_')],key=lambda x:enc.loc[x,'mib_s'])
    chosen=['xts_manual_ni',fastest,'cbc_mac','lrw_poly']
    t1=table(['Construction','Seed','Mask/tweak','Data path','Other'],[[short(s)]+[f'{100*c.loc[s,k]/c.loc[s,"wall_ns"]:.1f}%' for k in ('seed_ns','mask_ns','data_ns','other_ns')] for s in chosen])
    t2=table(['Construction','Enc MiB/s','Dec MiB/s','Enc ns/sector','Enc ns/byte'],[[name(s),f'{enc.loc[s,"mib_s"]:.2f}',f'{dec.loc[s,"mib_s"]:.2f}',f'{enc.loc[s,"ns_sector"]:,.0f}',f'{enc.loc[s,"ns_byte"]:.2f}'] for s in enc.index])
    ho=hs[hs.dependent].sort_values('ns_call')
    t3=table(['Mask','Dependent ns/call','Enc MiB/s','Dec MiB/s'],[[short(mask_label(r['mask'])),f'{r["ns_call"]:,.0f}',f'{enc.loc[mask_label(r["mask"]),"mib_s"]:.2f}',f'{dec.loc[mask_label(r["mask"]),"mib_s"]:.2f}'] for _,r in ho.iterrows()])
    t_opt=table(['Construction','Encryption speedup','Decryption speedup'],[[short(s),f'{opt.loc[(s,"encrypt"),"speedup"]:.2f}×',f'{opt.loc[(s,"decrypt"),"speedup"]:.2f}×'] for s in chosen])
    t4rows=[]
    maxw=int(ts.workers.max())
    for s in sorted(chosen,key=lambda x:rs[rs.scheme==x].ns_read.median()):
        v=ts[(ts.scheme==s)&(ts.direction=='decrypt')];best=v.loc[v.speedup.idxmax()];last=v[v.workers==maxw].iloc[0]
        t4rows.append([short(s),f'{rs[rs.scheme==s].ns_read.median()/1000:.2f}',f'{int(best.workers)} / {best.speedup:.2f}×',f'{last.speedup:.2f}× / {last.efficiency*100:.1f}%'])
    t4=table(['Construction','Read µs','Best threads / speedup',f'{maxw} threads: speedup / efficiency'],t4rows)
    for key,val in [('rq1',t1),('rq2',t2),('rq3',t3),('rq4',t4),('optimization',t_opt)]:
        (out/(key+'_table.md')).write_text(val+'\n',encoding='utf-8')
    cfg=env['config'];f=figdir.name
    b2=enc.loc[fastest,'mib_s'];cbce=enc.loc['cbc_mac','mib_s'];cbcd=dec.loc['cbc_mac','mib_s'];b2d=dec.loc[fastest,'mib_s']
    bestdec=ts[(ts.scheme==fastest)&(ts.direction=='decrypt')].sort_values('speedup',ascending=False).iloc[0]
    enc_gain=opt.loc[(fastest,'encrypt'),'speedup']
    text=f'''# FDE King 0

## 1. Methodology and research questions

- **RQ1 component cost:** {cfg['component_rounds']} encryptions and decryptions of a 4096-byte sector, instrumenting seed, mask and data work separately from throughput.
- **RQ2 throughput/latency:** 512- and 4096-byte sectors, {cfg['repeats']} trials of {cfg['work_bytes']/(1<<20):g} MiB each after warm-up; report medians and interquartile ranges. A 64 MiB RAM image is allocated; the report preset uses its first 1 MiB. No disk I/O is timed.
- **RQ3 mask choice:** {cfg['repeats']} batches of {cfg['hash_calls']:,} independent or feedback calls, each mapping 48 bytes to 16 bytes. Standalone CBC-MAC evaluates all three stages; sector timings include valid prefix reuse and batching.
- **RQ4 direct reads/parallel recovery:** {cfg['read_samples']} reads at each of six block positions; {cfg['thread_repeats']} trials with every thread count from 1 to {maxw}, over {cfg['thread_bytes']//1024} KiB. Also split a sector among threads and trace recovery after a ciphertext-bit error.
- **Optimization check:** interleaved reference/optimized runs, five trials of 50 sectors per direction in the report preset; both must produce identical bytes. Speedup = reference time / optimized time. Reference code is the literal block loop, with CBC sector-seed reuse; both paths share the same mask adapters, so these speedups isolate scheduling changes.
- `MiB/s = bytes × 10⁹ / (2²⁰ × elapsed_ns)`; `ns/byte = elapsed_ns / bytes`; `ns/sector = elapsed_ns / sectors`. Thread speedup = throughput(t) / throughput(1); efficiency = speedup / t. CPU cycles are not estimated.

## 2. Environment and assumptions

| Variable | This measured run |
| --- | --- |
| OS | {env['platform']} |
| CPU | {env['cpu_model']} |
| Available logical CPUs / affinity | {env['logical_cpus']} / {env['affinity_cpus']} |
| Execution | CPU only; no GPU, CUDA or GPU libraries |
| Python | CPython {env['python'].split()[0]}; GIL enabled: {env['gil_enabled']} |
| Threads | RQ1–3: one calling thread; RQ4: 1–{maxw} worker threads |
| Acceleration | AES-NI available: {env['aes_ni_available']}; CLMUL (field multiplication) available: {env['clmul_available']} |
| Backend | {env['openssl']} |
| Timer | perf_counter_ns; nominal resolution {env['timer_resolution_ns']:g} ns, not a latency guarantee |
| Host controls | CPU quota: {env['cpu_quota']}; turbo, frequency, power mode and background load are not controlled |

- CPU model, OS, Python/backend versions, hardware acceleration, available CPUs, working-set size and power/load conditions can change results. Changing terminals alone should not change the algorithm, but may select a different Python environment. Windows/macOS instructions and CI are supplied; only Linux was executed here.
- The program prints these runtime conditions immediately, then prints the selected batch sizes and worker counts. Full details are saved in `results/environment.json` and the supplied run in `benchmark.log`.
- **Implementation choices:** AES-256 data keys; AES-256 mask/tweak keys for CBC-MAC/XTS. AES-NI is requested for AES operations except the explicit XTS AES-NI-off control; libraries select their native CPU paths. All profiles take a 64-byte key container `K1 || K2`; LRW and SipHash use the first 16 bytes of K1, leaving its other 16 unused. LRW requires that field key to be nonzero. Public deterministic keys are benchmark fixtures; `example.py` uses a random key.
- Sectors and block indices are zero-extended to 16-byte big-endian fields; code indices start at zero. Feedback starts at 16 zero bytes. Complete AES blocks only, without padding/stealing or authentication tags.
- For every feedback construction, `C_j = AES_K2(P_j XOR delta_j) XOR delta_j`. Hash-based **XEX** uses only KMAC128, keyed BLAKE2s/BLAKE2b/BLAKE3 and SipHash-2-4-128. **AES-MAC-CBC** and **LRW-Polynomial** are separate construction names, sharing this outer data transformation.
- CBC-MAC uses the document's three AES stages. LRW uses exactly `((S·a XOR I_j)·a XOR C_prev)·a`, modulo x¹²⁸+x⁷+x²+x+1. A tested bit-order conversion allows native GHASH multiplication with an expanded key reused per worker; the pinned private interface is isolated in `masks.py`. This is the feedback LRW-polynomial proposal, not a claim that it is standardized LRW or proven secure.

## 3. Run in a terminal

1. Extract the ZIP and open `fde-king-0` in VS Code. Install Python 3.12.
2. Create a virtual environment: `python -m venv .venv` (Windows: `py -3.12 -m venv .venv`).
3. Activate: Linux/macOS `source .venv/bin/activate`; Windows PowerShell `.venv\\Scripts\\Activate.ps1`. Alternatively call that environment's Python directly.
4. Install: `python -m pip install -r requirements.txt`.
5. Run: `python run.py --preset report`. Outputs: raw/summary CSVs in `results/`, six PNGs in `figures/`, and regenerated README tables. `--workers N` changes the maximum thread count.
6. Quick check: `python run.py --preset smoke --out smoke_results`. Full 64 MiB passes: `python run.py --preset full --out full_results`, substantially slower. Full preset was not run for the supplied report.
7. Select a hash by changing one line, `DEFAULT_MASK = 'blake3'`, in `fdebench/engine.py`, or call `Engine('xex', 'blake2s', key=your_64_byte_key)`. Separate constructions use `Engine('cbc_mac', key=...)` and `Engine('lrw_poly', key=...)`. Benchmarks always run every registered profile. Tests: `python -m unittest discover -s tests -v`.

## 4. Results and interpretation

### RQ1 Component cost and optimization

{t1}

Shares include Python/native wrapper work and instrumentation, not isolated CPU-instruction costs. Opaque whole-sector library stages are not subdivided. Internal clocks alter execution cost; throughput uses uninstrumented runs.

{t_opt}

- XTS generates its tweaks explicitly, then batches data AES and XORs. AES-NI-off/on controls use the same scheduling; OpenSSL whole-sector XTS remains a separate control.
- AES-MAC-CBC prepares `E(S)` and all `E(I_j XOR E(S))` before the feedback loop. Encryption still needs one mask AES call and one data AES call per block, plus setup batches. Decryption needs only **four native AES calls per sector**: seed, batched middle stage, batched final stage, and batched data decryption. The mathematical AES work remains **3n+1 block evaluations**.
- The fastest hash profile has **{enc_gain:.2f}×** encryption speedup in the paired check; values below one mean a slowdown, so these changes do not improve every path. Hash-based XEX and LRW batch data AES during decryption. LRW also reuses its expanded multiplication key. No previous sector's plaintext, ciphertext or mask results are cached to improve timings.

![Component cost]({f}/rq1_components.png)

### RQ2 Raw throughput and latency

4096-byte sectors, descending encryption throughput.

{t2}

The fastest hash-based XEX profile is **{short(fastest)} at {b2:.2f} MiB/s**. AES-MAC-CBC reaches **{cbce:.2f} MiB/s encryption and {cbcd:.2f} MiB/s decryption**. Compared with {short(fastest)}, its encryption throughput is {cbce/b2:.2f}× and its decryption throughput is {cbcd/b2d:.2f}×. Encryption remains sequential, while decryption benefits from batching. Native AES throughput cannot be inferred from individual Python call timings. Compare optimization speedups within this run; the previous archive ran on a different host.

![Throughput]({f}/rq2_throughput.png)

### RQ3 Hash and mask choice

Fastest standalone feedback call first. These calls include input assembly and wrappers; independent versus feedback loops do not isolate a dependency penalty.

{t3}

A standalone mask-call ranking does not determine complete-sector decryption speed: CBC-MAC's independent stages can be batched, whereas the current hash adapters still make one Python/native hash call per block. The table therefore reports both mask cost and complete encryption/decryption. Performance is not a security ranking; polynomial hashing is not a general cryptographic hash/PRF.

![Mask cost]({f}/rq3_hash_cost.png)

### RQ4 Random access and parallel recovery

{t4}

Read latency is the median of six position-specific medians, with ciphertext already in RAM. Hash-XEX, AES-MAC-CBC and LRW need only C_j and its preceding ciphertext block, or C_j alone at the first position. Manual XTS derives a requested tweak directly; its Python field multiplication has overhead. The OpenSSL control decrypts the whole sector because this public API has no offset-block interface.

For **{short(fastest)}**, best inter-sector decryption speedup is **{bestdec.speedup:.2f}× at {int(bestdec.workers)} worker(s)**. This measures CPython threads and native-call scheduling, not an algorithmic limit. Thread curves show medians and interquartile bands normalized to the one-thread median; with few trials, small gains and irregular spikes should be rerun before treating them as stable scaling. Encryption is sequential within each feedback sector; decryption ranges are independent.

Changing one bit in ciphertext block 32 damaged plaintext blocks 32–33 in the tested feedback constructions, then recovery occurred at block 34; ECB/XTS damaged only block 32. None authenticates the alteration or prevents whole-sector rollback.

![Direct reads]({f}/rq4_random_access.png)
![Thread scaling]({f}/rq4_thread_scaling.png)
![Within-sector recovery]({f}/rq4_within_sector.png)

## 5. Further considerations

- Repeat on other CPUs/OSs and power modes with the printed conditions, package versions and batch sizes retained. Shared-host noise and different native backends can change close rankings.
- A compiled whole-sector implementation can further reduce per-block dispatch. Compare processes or native multicore execution before concluding that extra cores cannot help.
- Evaluate security separately for the exact feedback constructions; neither an AES-based mask nor fast polynomial multiplication alone establishes a security proof.

Implementation reference: [PyCryptodome buffer and native cipher APIs](https://www.pycryptodome.org/src/cipher/cipher). Construction formulas follow the supplied 18 November document.
'''
    (out.parent/('README.md' if out.name=='results' else out.name+'_README.md')).write_text(text,encoding='utf-8')
    print('Wrote summary CSVs, six figures and README',flush=True)
