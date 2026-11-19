"""Write CSV summaries, a plain-text README, and plots inside one result folder."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from .statistics import summarize,paired_ratio

LABELS={'ecb_bulk':'AES-ECB · bulk','xts_library':'AES-XTS · OpenSSL whole-sector',
 'xts_manual_ni':'AES-XTS · manual, AES-NI requested','xts_manual_soft':'AES-XTS · manual, AES-NI off',
 'xex_blake2s':'XEX · keyed BLAKE2s','xex_blake2b':'XEX · keyed BLAKE2b','xex_blake3':'XEX · keyed BLAKE3',
 'xex_siphash128':'XEX · SipHash-2-4-128','xex_kmac128':'XEX · KMAC128','cbc_mac':'AES-MAC-CBC',
 'lrw_horner':'LRW-Horner','lrw_precompute':'LRW-precompute'}
def label(x):return LABELS.get(x,x)
def raw(out,name):
    files=sorted((out/'[RAW]').glob(f'session-*-{name}.csv'))
    return pd.concat([pd.read_csv(p) for p in files],ignore_index=True) if files else pd.DataFrame()

def analyse(out,plots=True):
    out=Path(out);cfg=json.loads((out/'config.json').read_text());rng=np.random.default_rng(cfg['seed']);draws=cfg['bootstrap']
    summaries={};notes=[]
    p=raw(out,'profile')
    if not p.empty:
        p['data_ns']=p.data_ns+p.library_ns
        parts=['seed_ns','mask_ns','data_ns','other_ns'];long=p.melt(id_vars=['session','scheme','direction','repeat','wall_ns'],value_vars=parts,var_name='component',value_name='ns')
        long['percent']=100*long.ns/long.wall_ns
        keys=['scheme','direction','component']
        sums=summarize(long,keys,'percent',rng,draws)
        opaque=(sums.scheme=='xts_library')&sums.component.isin(['seed_ns','mask_ns'])
        sums['measured_separately']=~opaque
        sums.loc[opaque,['median','ci_low','ci_high']]=np.nan
        sums.to_csv(out/'component_share_summary.csv',index=False);summaries['components']=sums
        summarize(long,keys,'ns',rng,draws).to_csv(out/'component_time_summary.csv',index=False)
        setup=raw(out,'setup');summary=summarize(setup,['scheme'],'setup_ns',rng,draws)
        summary=summary.merge(setup.groupby('scheme').table_payload_bytes.max().reset_index(),on='scheme')
        summary.to_csv(out/'setup_summary.csv',index=False)
        opt=raw(out,'optimization')
        # Preserve the reference/candidate pairing at each trial before statistics.
        pairs=opt.pivot(index=['session','scheme','direction','repeat'],columns='implementation',values='ns_sector').reset_index()
        pairs['speedup']=pairs.reference/pairs.candidate
        o=summarize(pairs,['scheme','direction'],'speedup',rng,draws);o.to_csv(out/'optimization_summary.csv',index=False);summaries['optimization']=o
    t=raw(out,'throughput')
    if not t.empty:
        keys=['scheme','work_mib','sector_size','direction']
        s=summarize(t,keys,'mib_s',rng,draws).sort_values(['work_mib','sector_size','direction','median'],ascending=[True,True,True,False])
        s['ns_sector']=s.sector_size*1e9/((1<<20)*s['median']);s['ns_byte']=1e9/((1<<20)*s['median'])
        s.to_csv(out/'throughput_summary.csv',index=False);summaries['throughput']=s
        ratio=paired_ratio(t,['work_mib','sector_size','direction'],'mib_s','scheme','lrw_precompute','lrw_horner',rng,draws)
        if not ratio.empty:ratio.to_csv(out/'lrw_comparison.csv',index=False);summaries['lrw']=ratio
        ratio=paired_ratio(t,['scheme','work_mib','sector_size'],'mib_s','direction','decrypt','encrypt',rng,draws)
        if not ratio.empty:ratio.to_csv(out/'direction_comparison.csv',index=False)
        for reference in sorted(t.work_mib.unique())[:-1]:
            ratio=paired_ratio(t,['scheme','sector_size','direction'],'mib_s','work_mib',max(t.work_mib),reference,rng,draws)
            if not ratio.empty:ratio.to_csv(out/f'workload_{max(t.work_mib):g}_over_{reference:g}_comparison.csv',index=False)
    h=raw(out,'mask')
    if not h.empty:
        s=summarize(h,['scheme','dependent'],'ns_call',rng,draws).sort_values(['dependent','median'])
        s.to_csv(out/'mask_summary.csv',index=False);summaries['mask']=s
    r=raw(out,'reads')
    if not r.empty:
        s=summarize(r,['scheme','block'],'elapsed_ns',rng,draws)
        s=s.merge(r.groupby(['scheme','block']).ciphertext_bytes.first().reset_index(),on=['scheme','block'])
        s.to_csv(out/'random_read_summary.csv',index=False);summaries['reads']=s
    threads=raw(out,'threads')
    if not threads.empty:
        s=summarize(threads,['scheme','thread_kib','direction','workers'],'mib_s',rng,draws)
        ratios=[]
        for worker in sorted(threads.workers.unique()):
            ratio=paired_ratio(threads,['scheme','thread_kib','direction'],'mib_s','workers',worker,1,rng,draws)
            if worker==1:
                ratio['ratio']=1.;ratio['ci_low']=np.nan;ratio['ci_high']=np.nan;ratio['coverage_lower_bound']=np.nan;ratio['within_five_percent']=np.nan;ratio['ci_scope']='baseline_identity_not_an_estimate'
            ratio['workers']=worker;ratios.append(ratio)
        ratios=pd.concat(ratios,ignore_index=True).rename(columns={'ratio':'speedup','ci_low':'speedup_ci_low','ci_high':'speedup_ci_high','ci_scope':'speedup_ci_scope','sessions':'speedup_sessions','coverage_lower_bound':'speedup_coverage_lower_bound','within_five_percent':'speedup_within_five_percent'})
        s=s.merge(ratios,on=['scheme','thread_kib','direction','workers']);s['efficiency']=s.speedup/s.workers
        s.to_csv(out/'thread_summary.csv',index=False);summaries['threads']=s
    within=raw(out,'within')
    if not within.empty:
        s=summarize(within,['scheme','workers'],'ns_sector',rng,draws);s.to_csv(out/'within_sector_summary.csv',index=False);summaries['within']=s
    # No markdown file is generated. No files are written to the project parent.
    env=json.loads((out/'environment.json').read_text())
    lines=['FDE King 1 run summary',f"Requested fresh-process sessions: {cfg['sessions']}",
        f"CPU: {env['cpu_model']}; logical CPUs: {env['logical_cpus']}; affinity: {env['affinity']}",
        f"OS: {env['platform']}; Python: {env['python'].split()[0]}; GIL: {env['gil_enabled']}",
        f"Backend: {env['openssl']}; AES-NI available: {env['aes_ni_available']}; CLMUL available: {env['clmul_available']}",
        f"RQ1-3 calling threads: 1; RQ4 worker counts: {cfg['workers']}; thread batches KiB: {cfg['thread_kib']}",
        f"Working sets MiB: {cfg['work_mib']}; sector sizes: {cfg['sector_sizes']}; throughput trials/condition/launch: {cfg['repeats']}",
        f"RQs: {cfg['rqs']}; schemes: {', '.join(cfg['schemes'])}",
        'Point estimates: median of per-launch medians. Multi-launch error bars: conservative pointwise >=95% order-statistic CIs.',
        'Six or more launches: binomial order-statistic intervals (paired launch ratios for comparisons); requires independent, comparable launches.',
        'Single launch: circular adjacent-pair bootstrap of batches; these CIs exclude between-launch variation.',
        'Two to five launches: finite distribution-free two-sided 95% median intervals are unavailable; error bars are omitted. Six launches give at least 96.875% coverage under the stated assumptions.',
        'The number of profiling rows or hash calls is not the number of independent machine launches.',
        'The shaded +/-5% band on ratio plots is a practical tolerance, not an error bar.',
        'Baseline thread speedup is 1 by definition; no CI is claimed for that identity.',
        'LRW precompute and Horner are algebraically identical, use the same key, and are tested for identical ciphertext.',
        'LRW precompute: initial table payload 4096 bytes (256 positions); grows for longer sectors. Setup and payload are reported.',
        'RQ3 prebuilt independent inputs exclude input assembly; feedback includes assembly. CBC is a full three-stage call.',
        'RQ3 LRW precompute full-context call recomputes the sector term; sector encryption/decryption amortizes it once per sector.',
        'RQ1 records one row per instrumented 4096-byte sector; clock calls perturb this path. Throughput is uninstrumented.',
        'Key/context and thread-pool setup excluded from steady-state throughput. OpenSSL per-sector context creation remains included.',
        'RAM only, no disk I/O; CPU only, no GPU/CUDA. No estimated cycle counts.',
        'These measurements do not prove cryptographic security.',
        'Raw per-session CSVs and environment snapshots: [RAW]/. Figures: [FIGURES]/.',
        'Check status.json for completion; summary CSVs state actual session and sample counts even for partial analysis.']
    if 'throughput' in summaries:
        lines+=['','Throughput (MiB/s):']
        for _,row in summaries['throughput'].iterrows():
            lines.append(f"{row.work_mib:g} MiB; {int(row.sector_size)} B; {row.direction}; {label(row.scheme)}: {row['median']:.3f} [{row.ci_low:.3f}, {row.ci_high:.3f}]")
    (out/'README.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    if plots:figures(out,summaries)
    import hashlib
    manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')}
    (out/'analysis_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    return summaries

def figures(out,summaries):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter,NullLocator
    target=out/'[FIGURES]';target.mkdir(exist_ok=True)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.titlesize':11})
    def style(ax):
        ax.spines[['top','right']].set_visible(False);ax.grid(alpha=.15);ax.set_axisbelow(True)
    def save(fig,name):
        fig.text(.5,.005,'Medians; >=95% launch CIs where available. Single launch: provisional bootstrap. 2-5 launches: CI unavailable.',ha='center',fontsize=8)
        fig.savefig(target/name,dpi=160,bbox_inches='tight',facecolor='white');plt.close(fig)
    def errors(v,point='median',low='ci_low',high='ci_high'):
        return np.maximum(0,np.nan_to_num(np.array([v[point]-v[low],v[high]-v[point]]),nan=0.))
    colors=lambda names:['#8a63a3' if s=='lrw_precompute' else '#ba8dba' if s=='lrw_horner' else '#d08732' if s=='cbc_mac' else '#227c79' if s.startswith('xex') else '#385a82' for s in names]
    def bars(ax,v,title,xlabel,log=False):
        v=v.sort_values('median',ascending=not log)
        if log:
            ax.errorbar(v['median'],range(len(v)),xerr=errors(v),fmt='none',ecolor='#555555',capsize=3)
            ax.scatter(v['median'],range(len(v)),c=colors(v.scheme),s=30,zorder=3)
        else:
            ax.barh(range(len(v)),v['median'],xerr=errors(v),color=colors(v.scheme),capsize=2)
        ax.set_yticks(range(len(v)),[label(s) for s in v.scheme]);ax.invert_yaxis();
        if len(v):ax.set_ylim(len(v)-.5,-.5)
        ax.set_title(title);ax.set_xlabel(xlabel)
        if log:
            ax.set_xscale('log')
            lo=float(np.nanmin(np.r_[v['median'],v.ci_low]))*.85
            hi=float(np.nanmax(np.r_[v['median'],v.ci_high]))*1.15
            if hi<=lo:hi=lo*2
            ax.set_xlim(lo,hi);ax.set_xticks(np.geomspace(lo,hi,5))
            ax.xaxis.set_minor_locator(NullLocator())
            ax.xaxis.set_major_formatter(FuncFormatter(lambda x,pos:f'{x:,.0f}' if x>=100 else f'{x:.2f}'))
        style(ax)
    if 'components' in summaries:
        c=summaries['components'];fig,axes=plt.subplots(1,2,figsize=(15,max(3.5,.42*len(c.scheme.unique())+1.5)))
        for ax,part in zip(axes,['mask_ns','data_ns']):
            v=c[(c.direction=='encrypt')&(c.component==part)&c.measured_separately]
            bars(ax,v,('Mask / tweak (OpenSSL stages unavailable)' if 'xts_library' in c.scheme.values else 'Mask / tweak') if part=='mask_ns' else 'Data path / opaque library','Median share of instrumented sector time (%)');ax.set_xlim(0,100)
        fig.suptitle('RQ1 Encryption component shares');fig.tight_layout(rect=[0,.035,1,.96]);save(fig,'rq1_components.png')
    if 'optimization' in summaries:
        fig,axes=plt.subplots(1,2,figsize=(15,max(3.5,.42*len(summaries['optimization'].scheme.unique())+1.5)))
        for ax,d in zip(axes,['encrypt','decrypt']):bars(ax,summaries['optimization'].query('direction==@d'),d,'Candidate / reference speedup (log scale)',True);ax.axvline(1,color='grey',ls='--')
        fig.suptitle('RQ1 Paired optimization check');fig.tight_layout(rect=[0,.035,1,.96]);save(fig,'rq1_optimization.png')
    if 'throughput' in summaries:
        t=summaries['throughput']
        for work in sorted(t.work_mib.unique()):
            sizes=sorted(t.sector_size.unique());fig,axes=plt.subplots(len(sizes),2,figsize=(16,max(3.2,.42*len(t.scheme.unique())+1.5)*len(sizes)),squeeze=False)
            for i,size in enumerate(sizes):
                for ax,d in zip(axes[i],['encrypt','decrypt']):bars(ax,t.query('work_mib==@work and sector_size==@size and direction==@d'),f'{int(size)}-byte sectors · {d}','MiB/s (log scale)',True)
            fig.suptitle(f'RQ2 Throughput · {work:g} MiB working set');fig.tight_layout(rect=[0,.025,1,.97]);save(fig,f'rq2_throughput_{work:g}mib.png')
    if 'lrw' in summaries:
        x=summaries['lrw'];fig,ax=plt.subplots(figsize=(10,5));v=x.copy();v['median']=v.ratio
        ax.barh(range(len(v)),v.ratio,xerr=errors(v),color='#8a63a3',capsize=3)
        ax.set_yticks(range(len(v)),[f'{r.work_mib:g} MiB / {int(r.sector_size)} B / {r.direction}' for _,r in v.iterrows()]);ax.invert_yaxis()
        ax.axvspan(.95,1.05,alpha=.15,color='grey',label='±5% practical band');ax.axvline(1,color='grey',ls='--');ax.legend(loc='upper left',bbox_to_anchor=(1.02,1),frameon=False)
        ax.set_xlabel('LRW-precompute / LRW-Horner throughput');ax.set_title('Same formula, shared key: precompute versus Horner');style(ax);fig.tight_layout(rect=[0,.04,1,1]);save(fig,'lrw_comparison.png')
    if 'mask' in summaries:
        fig,ax=plt.subplots(figsize=(12,max(3.5,.42*len(summaries['mask'].scheme.unique())+1.5)));v=summaries['mask'];v=v[v.dependent]
        bars(ax,v,'RQ3 Full-context mask cost · output feedback','ns per 48-byte context (log scale)',True)
        ax.invert_yaxis();fig.tight_layout(rect=[0,.04,1,1]);save(fig,'rq3_masks.png')
    if 'reads' in summaries:
        fig,ax=plt.subplots(figsize=(12,6))
        for s,v in summaries['reads'].groupby('scheme'):
            v=v.sort_values('block');ax.errorbar(v.block,v['median']/1000,yerr=errors(v)/1000,marker='o',markersize=3,label=label(s),capsize=2)
        ax.set_yscale('log');ax.set_xticks([1,32,64,128,192,256]);ax.set_xlabel('Requested block (one-based)');ax.set_ylabel('µs per warm read (log scale)');ax.set_title('RQ4 Direct reads' + ('; OpenSSL control processes the whole sector' if 'xts_library' in summaries['reads'].scheme.values else ' from ciphertext in RAM'))
        ax.legend(loc='upper left',bbox_to_anchor=(1.02,1),fontsize=8,frameon=False);style(ax);fig.tight_layout(rect=[0,.04,1,1]);save(fig,'rq4_reads.png')
    if 'threads' in summaries:
        t=summaries['threads']
        for kib in sorted(t.thread_kib.unique()):
            fig,axes=plt.subplots(1,2,figsize=(15,5),sharey=True)
            for ax,d in zip(axes,['encrypt','decrypt']):
                for s,v in t.query('thread_kib==@kib and direction==@d').groupby('scheme'):
                    v=v.sort_values('workers');line,=ax.plot(v.workers,v.speedup,marker='o',markersize=3,label=label(s))
                    lo=v.speedup_ci_low.fillna(v.speedup);hi=v.speedup_ci_high.fillna(v.speedup)
                    ax.fill_between(v.workers,lo,hi,color=line.get_color(),alpha=.08)
                ax.axhline(1,color='grey',ls='--');ax.set_title(d);ax.set_xlabel('Worker threads');ax.set_xticks(sorted(t.workers.unique()));style(ax)
            axes[0].set_ylabel('Throughput / one-worker throughput');axes[1].legend(loc='upper left',bbox_to_anchor=(1.02,1),fontsize=8,frameon=False)
            fig.suptitle(f'RQ4 Inter-sector thread scaling · {kib:g} KiB');fig.tight_layout(rect=[0,.04,1,.94]);save(fig,f'rq4_threads_{kib:g}kib.png')
    if 'within' in summaries:
        # Plot latency rather than an artificial CI around the baseline identity.
        fig,ax=plt.subplots(figsize=(12,5))
        for s,v in summaries['within'].groupby('scheme'):
            v=v.sort_values('workers');ax.errorbar(v.workers,v['median']/1000,yerr=errors(v)/1000,marker='o',label=label(s),capsize=2)
        ax.set_yscale('log');ax.set_xticks(sorted(summaries['within'].workers.unique()));ax.set_xlabel('Threads within one sector');ax.set_ylabel('µs per sector (log scale)');ax.set_title('RQ4 Within-sector decryption · dispatch and joins included')
        ax.legend(loc='upper left',bbox_to_anchor=(1.02,1),fontsize=8,frameon=False);style(ax);fig.tight_layout(rect=[0,.04,1,1]);save(fig,'rq4_within.png')
