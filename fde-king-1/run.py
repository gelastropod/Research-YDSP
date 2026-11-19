"""One results-<name> directory per command; no generated Markdown."""
import sys
sys.dont_write_bytecode=True
import argparse,json,os,re,subprocess,time,unittest
from pathlib import Path
from fdebench.engine import schemes,build
from fdebench.benchmark import environment,measure

ROOT=Path(__file__).resolve().parent

def parser():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--name','--out',default=None,help='Custom suffix; creates results-SUFFIX in the current directory')
    p.add_argument('--preset',choices=['smoke','report'],default='report')
    p.add_argument('--rqs',nargs='+',type=int,choices=[1,2,3,4],default=[1,2,3,4])
    p.add_argument('--schemes',nargs='+',default=['all'],help='Use --list-schemes for IDs')
    p.add_argument('--list-schemes',action='store_true')
    p.add_argument('--work-mib',nargs='+',type=float,default=None)
    p.add_argument('--sector-sizes',nargs='+',type=int,default=[512,4096])
    p.add_argument('--workers',nargs='+',type=int,default=None,help='Explicit counts, e.g. 1 2 4; baseline 1 is added')
    p.add_argument('--thread-kib',nargs='+',type=float,default=None)
    p.add_argument('--sessions',type=int,default=1,help='Number of fresh Python subprocesses, sequentially')
    p.add_argument('--repeats',type=int,default=None)
    p.add_argument('--thread-repeats',type=int,default=None)
    p.add_argument('--profile-rounds',type=int,default=None)
    p.add_argument('--hash-calls',type=int,default=None)
    p.add_argument('--read-samples',type=int,default=None)
    p.add_argument('--optimization-repeats',type=int,default=None)
    p.add_argument('--optimization-rounds',type=int,default=None)
    p.add_argument('--bootstrap',type=int,default=10000)
    p.add_argument('--seed',type=int,default=20261119)
    p.add_argument('--cpu',type=int,help='Pin to one allowed logical CPU, where supported; avoid for multicore experiments')
    p.add_argument('--no-plots',action='store_true')
    p.add_argument('--analyse',type=Path,help='Reanalyse an existing King 1 result directory; creates no new result folder')
    p.add_argument('--child',action='store_true',help=argparse.SUPPRESS)
    p.add_argument('--result-dir',type=Path,help=argparse.SUPPRESS)
    p.add_argument('--session-id',type=int,help=argparse.SUPPRESS)
    return p

def configuration(a,p):
    all_labels=[build_label(s,m) for s,m in schemes()]
    selected=all_labels if a.schemes==['all'] else list(dict.fromkeys(a.schemes))
    if any(s not in all_labels for s in selected):p.error('Unknown scheme. Run --list-schemes')
    smoke=a.preset=='smoke';available=len(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else os.cpu_count() or 1
    workers=sorted(set([1]+(a.workers or ([1,min(2,available)] if smoke else [1,min(2,available),min(4,available)]))))
    cfg=dict(preset=a.preset,rqs=sorted(set(a.rqs)),schemes=selected,sessions=a.sessions,
        work_mib=sorted(set(a.work_mib or ([8192/(1<<20)] if smoke else [1]))),sector_sizes=sorted(set(a.sector_sizes)),
        workers=workers,thread_kib=sorted(set(a.thread_kib or ([8] if smoke else [256]))),
        repeats=a.repeats or (2 if smoke else 10),thread_repeats=a.thread_repeats or (2 if smoke else 5),
        profile_rounds=a.profile_rounds or (3 if smoke else 500),hash_calls=a.hash_calls or (100 if smoke else 10000),
        read_samples=a.read_samples or (5 if smoke else 200),optimization_repeats=a.optimization_repeats or (2 if smoke else 10),
        optimization_rounds=a.optimization_rounds or (2 if smoke else 50),setup_repeats=3 if smoke else 20,
        within_sectors=1 if smoke else 8,bootstrap=a.bootstrap,seed=a.seed,disk_bytes=64*(1<<20))
    if not 1<=a.sessions<=100:p.error('sessions must be 1..100')
    for key in ['repeats','thread_repeats','profile_rounds','hash_calls','read_samples','optimization_repeats','optimization_rounds']:
        supplied=getattr(a,key,None)
        if supplied is not None and supplied<1:p.error(key+' must be positive')
    if not 0<=a.seed<2**32:p.error('seed must be 0..2^32-1')
    if a.bootstrap<100:p.error('bootstrap must be at least 100')
    if any(not 1<=x<=64 for x in workers):p.error('worker counts must be 1..64')
    if any(x<16 or x>65536 or x%16 for x in cfg['sector_sizes']):p.error('sector sizes must be multiples of 16, within 64 KiB')
    for mib in cfg['work_mib']:
        n=int(mib*(1<<20))
        if not 4096<=n<=64*(1<<20) or any(n%s for s in cfg['sector_sizes']):p.error('Each working set must fit 64 MiB and contain complete sectors')
    for kib in cfg['thread_kib']:
        n=int(kib*1024)
        if not 4096<=n<=64*(1<<20) or n%4096:p.error('Thread batches must be whole 4 KiB sectors, within 64 MiB')
    return cfg

def build_label(s,m):return 'xex_'+m if s=='xex' else s

def main():
    p=parser();a=p.parse_args()
    if a.child:
        cfg=json.loads((a.result_dir/'config.json').read_text())
        print(f'Fresh-process session {a.session_id}/{cfg["sessions"]}',flush=True)
        measure(cfg,a.result_dir,a.session_id);return
    if a.list_schemes:
        print('\n'.join(build_label(s,m) for s,m in schemes()));return
    if a.analyse:
        from fdebench.analyse import analyse
        analyse(a.analyse,not a.no_plots);print('Updated summaries inside',a.analyse);return
    if a.cpu is not None:
        if not hasattr(os,'sched_setaffinity'):p.error('--cpu is not supported on this OS')
        if a.cpu not in os.sched_getaffinity(0):p.error('CPU not in current affinity mask')
        os.sched_setaffinity(0,{a.cpu})
    cfg=configuration(a,p)
    print('=== Runtime conditions: CPU only, no GPU/CUDA ===',flush=True)
    env=environment(cfg);print(json.dumps(env,indent=2),flush=True)
    print('RQ1–3 use one calling thread; RQ4 uses the explicitly listed counts. Latency is measured, not assumed.',flush=True)
    print('CI bars: >=95% order-statistic launch intervals with >=6 sessions; single-session bootstrap is provisional. +/-5% is a separate practical tolerance.',flush=True)
    suffix=a.name or time.strftime('%Y%m%d-%H%M%S')
    if suffix.startswith('results-'):suffix=suffix[len('results-'):]
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}',suffix):p.error('Name must be a simple suffix (letters, digits, dot, underscore, hyphen)')
    out=Path.cwd()/('results-'+suffix)
    if out.exists():p.error(f'{out.name} already exists; choose a new name to preserve old results')
    out.mkdir();(out/'[RAW]').mkdir()
    (out/'config.json').write_text(json.dumps(cfg,indent=2)+'\n',encoding='utf-8')
    (out/'environment.json').write_text(json.dumps(env,indent=2)+'\n',encoding='utf-8')
    status={'state':'testing','sessions_completed':0}
    def save_status(): (out/'status.json').write_text(json.dumps(status,indent=2)+'\n',encoding='utf-8')
    save_status()
    import io
    capture=io.StringIO();suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
    result=unittest.TextTestRunner(stream=capture,verbosity=2).run(suite)
    print(capture.getvalue(),flush=True);(out/'correctness.txt').write_text(capture.getvalue(),encoding='utf-8')
    if not result.wasSuccessful():status['state']='tests_failed';save_status();raise SystemExit(1)
    child=None
    try:
        status['state']='measuring';save_status()
        with (out/'run.log').open('w',encoding='utf-8') as log:
            log.write(json.dumps(env,indent=2)+'\n')
            for i in range(1,cfg['sessions']+1):
                cmd=[sys.executable,str(ROOT/'run.py'),'--child','--result-dir',str(out),'--session-id',str(i)]
                child=subprocess.Popen(cmd,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',bufsize=1)
                for line in child.stdout:
                    print(f'[session {i}] '+line,end='',flush=True);log.write(line);log.flush()
                code=child.wait()
                if code:raise RuntimeError(f'Session {i} failed, exit code {code}; see run.log')
                status['sessions_completed']=i;save_status()
        status['state']='analysing';save_status()
        from fdebench.analyse import analyse
        analyse(out,not a.no_plots)
        status['state']='complete';save_status();print('Complete:',out,flush=True)
    except BaseException as exc:
        if child is not None and child.poll() is None:child.terminate();child.wait()
        status['state']='interrupted' if isinstance(exc,KeyboardInterrupt) else 'failed'
        status['error']=str(exc);save_status();raise

if __name__=='__main__':main()
