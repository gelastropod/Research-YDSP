"""Run from the extracted repository root; no compiler is needed."""
import argparse
import json
import os
from pathlib import Path
import unittest
from fdebench.benchmark import measure, environment

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preset',choices=['report','smoke','full'],default='report')
    parser.add_argument('--out',default='results')
    parser.add_argument('--workers',type=int)
    parser.add_argument('--work-mib',type=float)
    parser.add_argument('--only-analyse',action='store_true')
    args=parser.parse_args()
    print('=== Runtime conditions (CPU only; no GPU/CUDA) ===',flush=True)
    print(json.dumps(environment({}),indent=2),flush=True)
    if not args.only_analyse:
        suite=unittest.defaultTestLoader.discover('tests')
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
        (out/'correctness.json').write_text(json.dumps(dict(tests=result.testsRun,failures=len(result.failures),
             errors=len(result.errors),passed=result.wasSuccessful()),indent=2)+'\n')
        if not result.wasSuccessful():raise SystemExit(1)
        cpu=len(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else (os.cpu_count() or 1)
        config=dict(preset=args.preset,disk_bytes=64*(1<<20),work_bytes=1<<20,repeats=10,
                    component_rounds=500,hash_calls=100000,max_workers=min(cpu,16),thread_bytes=256*(1<<10),
                    thread_repeats=3,within_sectors=8,read_samples=200)
        if args.preset=='smoke':
            config.update(work_bytes=8192,repeats=2,component_rounds=3,hash_calls=100,max_workers=min(cpu,2),
                          thread_bytes=8192,thread_repeats=1,within_sectors=1,read_samples=5)
        if args.preset=='full':config.update(work_bytes=64*(1<<20),thread_bytes=64*(1<<20),thread_repeats=10)
        if args.work_mib is not None:config['work_bytes']=int(args.work_mib*(1<<20))
        if args.workers is not None:config['max_workers']=args.workers
        if not 1<=config['max_workers']<=64:parser.error('workers must be 1..64')
        if not 4096<=config['work_bytes']<=config['disk_bytes'] or config['work_bytes']%4096:
            parser.error('work size must be a multiple of 4096 bytes, within 64 MiB')
        config['thread_bytes']=min(config['thread_bytes'],config['work_bytes'])
        print('=== Benchmark settings ===',flush=True)
        print(json.dumps(config,indent=2),flush=True)
        print('RQ1–3: one calling thread. RQ4: sweep 1..'+str(config['max_workers'])+' worker threads. Latency is measured, not assumed.',flush=True)
        print(f"RAM image: {config['disk_bytes']/(1<<20):g} MiB; timed working set: {config['work_bytes']/(1<<20):g} MiB; sectors: 512/4096 bytes; trials: {config['repeats']}",flush=True)
        measure(config,args.out)
    from fdebench.analyse import analyse
    analyse(args.out)

if __name__=='__main__':main()
