"""Measurements are raw rows; summaries and interpretation are generated separately."""
import csv
import hashlib
import importlib.metadata
import json
import os
import platform
import statistics
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import perf_counter_ns

from Crypto.Util import _cpu_features
from cryptography.hazmat.backends.openssl.backend import backend
from .engine import Engine, ReferenceEngine, Cost, build, schemes
from .masks import NAMES, make_mask

MIB=1 << 20

def dump(path, rows):
    if not rows: return
    with Path(path).open('w', newline='', encoding='utf-8') as f:
        w=csv.DictWriter(f, fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def environment(config):
    cpu=platform.processor() or os.environ.get('PROCESSOR_IDENTIFIER','not exposed by host')
    if Path('/proc/cpuinfo').exists():
        for line in Path('/proc/cpuinfo').read_text().splitlines():
            if line.lower().startswith('model name'):
                cpu=line.partition(':')[2].strip();break
    return dict(python=sys.version,platform=platform.platform(),cpu_model=cpu,
                logical_cpus=os.cpu_count(),affinity_cpus=len(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else None,
                aes_ni_available=bool(_cpu_features.have_aes_ni()),
                clmul_available=bool(_cpu_features.have_clmul()),openssl=backend.openssl_version_text(),
                packages={x:importlib.metadata.version(x) for x in ('cryptography','pycryptodome','blake3','PyNaCl','matplotlib','numpy','pandas')},
                config=config,clock='time.perf_counter_ns',cycle_counter='not measured',
                key_fixture='public deterministic benchmark keys; not production secrets', execution='CPU only; no GPU/CUDA code', gil_enabled=getattr(sys,'_is_gil_enabled',lambda:True)(), timer_resolution_ns=__import__('time').get_clock_info('perf_counter').resolution*1e9, cpu_quota=Path('/sys/fs/cgroup/cpu.max').read_text().strip() if Path('/sys/fs/cgroup/cpu.max').exists() else 'not exposed', power_clock_policy='not controlled; shared-host scheduling/turbo can vary')

def pass_sectors(engine, source, sector_size, decrypt=False):
    sink=0
    for offset in range(0,len(source),sector_size):
        result=engine.crypt(source[offset:offset+sector_size],offset//sector_size,decrypt)
        sink ^= result[-1]
    return sink

def fixture_cipher(engine, plain, sector_size):
    out=bytearray(len(plain))
    for offset in range(0,len(plain),sector_size):
        out[offset:offset+sector_size]=engine.encrypt(plain[offset:offset+sector_size],offset//sector_size)
    return bytes(out)

def measure(config, outdir):
    outdir=Path(outdir);outdir.mkdir(parents=True,exist_ok=True)
    (outdir/'environment.json').write_text(json.dumps(environment(config),indent=2)+'\n')
    # The report samples a specified working set from the allocated 64-MiB image.
    disk=bytearray(hashlib.shake_256(b'fde-xex benchmark image v1').digest(config['disk_bytes']))
    plain=bytes(memoryview(disk)[:config['work_bytes']])
    specs=schemes()
    throughput=[];components=[];setup=[]
    for scheme,mask in specs:
        engine=Engine(scheme,mask);label=engine.label
        print('RQ1/2',label,flush=True)
        for repeat in range(20):
            tick=perf_counter_ns();Engine(scheme,mask)
            setup.append(dict(scheme=label,repeat=repeat,setup_ns=perf_counter_ns()-tick))
        for sector_size in (512,4096):
            ciphertext=fixture_cipher(engine,plain,sector_size)
            for decrypt in (False,True):
                direction='decrypt' if decrypt else 'encrypt'
                source=ciphertext if decrypt else plain
                # One complete warm-up of the measured working set.
                pass_sectors(engine,source,sector_size,decrypt)
                for repeat in range(config['repeats']):
                    tick=perf_counter_ns();sink=pass_sectors(engine,source,sector_size,decrypt);elapsed=perf_counter_ns()-tick
                    throughput.append(dict(scheme=label,sector_size=sector_size,direction=direction,repeat=repeat,
                        bytes=len(source),sectors=len(source)//sector_size,elapsed_ns=elapsed,
                        mib_s=len(source)*1e9/(MIB*elapsed),ns_sector=elapsed/(len(source)//sector_size),
                        ns_byte=elapsed/len(source),sink=sink))
                dump(outdir/'throughput_raw.csv',throughput)
                if sector_size==4096:
                    sample=source[:4096];stats=Cost()
                    tick=perf_counter_ns()
                    for _ in range(config['component_rounds']):engine.crypt(sample,0,decrypt)
                    bare=(perf_counter_ns()-tick)/config['component_rounds']
                    for _ in range(config['component_rounds']):
                        engine.crypt(sample,0,decrypt,stats)
                    rows=dict(scheme=label,direction=direction,rounds=config['component_rounds'],**vars(stats))
                    rows['other_ns']=max(0,stats.wall_ns-stats.seed_ns-stats.mask_ns-stats.data_ns-stats.library_ns)
                    rows['uninstrumented_ns_sector']=bare
                    rows['instrumentation_ratio']=stats.wall_ns/config['component_rounds']/rows['uninstrumented_ns_sector']
                    components.append(rows)
        dump(outdir/'components.csv',components);dump(outdir/'setup_raw.csv',setup)
    print('RQ3 hashes',flush=True)
    hash_rows=[];key=hashlib.sha256(b'primitive-mask-key').digest();prefix=bytes(32)
    for name in NAMES:
        h=make_mask(name,key);h(bytes(48))
        for dependent in (False,True):
            for repeat in range(config['repeats']):
                state=bytes(16);sink=0;tick=perf_counter_ns()
                for i in range(config['hash_calls']):
                    context=prefix+state if dependent else prefix+(i&65535).to_bytes(16,'big')
                    value=h(context);sink ^= value[-1]
                    if dependent: state=value
                elapsed=perf_counter_ns()-tick
                hash_rows.append(dict(mask=name,dependent=dependent,repeat=repeat,calls=config['hash_calls'],
                    elapsed_ns=elapsed,ns_call=elapsed/config['hash_calls'],ns_input_byte=elapsed/config['hash_calls']/48,sink=sink))
        dump(outdir/'hash_raw.csv',hash_rows)
    optimization(specs,outdir,config)
    random_access(specs,outdir,config)
    thread_scaling(specs,plain,outdir,config)
    recovery(specs,outdir)
    print('Benchmark complete',flush=True)

def random_access(specs,outdir,config):
    rows=[];p=hashlib.shake_256(b'random access').digest(4096)
    for scheme,mask in specs:
        e=Engine(scheme,mask);c=e.encrypt(p,19)
        for j in (0,31,63,127,191,255):
            for _ in range(10):e.decrypt_block(c,19,j)
            for repeat in range(config['read_samples']):
                tick=perf_counter_ns();result=e.decrypt_block(c,19,j);elapsed=perf_counter_ns()-tick
                if result!=p[16*j:16*(j+1)]:raise AssertionError('Random read incorrect')
                read_bytes=4096 if scheme=='xts_library' else (16 if scheme not in ('xex','cbc_mac','lrw_poly') or j==0 else 32)
                rows.append(dict(scheme=e.label,block=j+1,repeat=repeat,elapsed_ns=elapsed,ciphertext_bytes_required=read_bytes))
    dump(outdir/'random_access_raw.csv',rows)

def make_pool(label,workers):
    local=threading.local();barrier=threading.Barrier(workers)
    pool=ThreadPoolExecutor(max_workers=workers)
    def warm():
        local.engine=build(label);barrier.wait()
    futures=[pool.submit(warm) for _ in range(workers)]
    for f in futures:f.result()
    return pool,local

def thread_scaling(specs,plain,outdir,config):
    rows=[];within=[];size=4096
    p=plain[:config['thread_bytes']]
    for scheme,mask in specs:
        base=Engine(scheme,mask);label=base.label;c=fixture_cipher(base,p,size)
        print('RQ4 threads',label,flush=True)
        sectors=len(p)//size
        for workers in range(1,config['max_workers']+1):
            pool,local=make_pool(label,workers)
            try:
                for decrypt in (False,True):
                    source=c if decrypt else p
                    def job(lo,hi):
                        sink=0
                        for j in range(lo,hi):
                            value=local.engine.crypt(source[j*size:(j+1)*size],j,decrypt);sink^=value[-1]
                        return sink
                    limits=[(sectors*i//workers,sectors*(i+1)//workers) for i in range(workers)]
                    # Warm the measured work once at each worker count/direction.
                    for f in [pool.submit(job,*r) for r in limits]:f.result()
                    for repeat in range(config['thread_repeats']):
                        tick=perf_counter_ns();futures=[pool.submit(job,*r) for r in limits]
                        sink=0
                        for f in futures:sink^=f.result()
                        elapsed=perf_counter_ns()-tick
                        rows.append(dict(scheme=label,direction='decrypt' if decrypt else 'encrypt',workers=workers,
                            repeat=repeat,bytes=len(source),elapsed_ns=elapsed,mib_s=len(source)*1e9/(MIB*elapsed),sink=sink))
                if scheme!='xts_library':
                    sector_cipher=c[:4096];blocks=256
                    def part(lo,hi):return local.engine.decrypt_range(sector_cipher,0,lo,hi)
                    limits=[(blocks*i//workers,blocks*(i+1)//workers) for i in range(workers)]
                    for repeat in range(config['thread_repeats']):
                        tick=perf_counter_ns()
                        for _ in range(config['within_sectors']):
                            futures=[pool.submit(part,*r) for r in limits]
                            recovered=b''.join(f.result() for f in futures)
                        elapsed=perf_counter_ns()-tick
                        if recovered!=p[:4096]:raise AssertionError('Parallel sector decryption incorrect')
                        within.append(dict(scheme=label,workers=workers,repeat=repeat,sectors=config['within_sectors'],
                            elapsed_ns=elapsed,ns_sector=elapsed/config['within_sectors']))
            finally:pool.shutdown()
            dump(outdir/'thread_raw.csv',rows);dump(outdir/'within_sector_raw.csv',within)

def recovery(specs,outdir):
    rows=[];p=hashlib.shake_256(b'recovery trace').digest(4096);r=31
    for scheme,mask in specs:
        e=Engine(scheme,mask);c=bytearray(e.encrypt(p,0));c[16*r]^=1
        recovered=e.decrypt(bytes(c),0)
        wrong=[j+1 for j in range(256) if recovered[16*j:16*(j+1)]!=p[16*j:16*(j+1)]]
        expected={32,33} if scheme in ('xex','cbc_mac','lrw_poly') else {32}
        if set(wrong)!=expected:raise AssertionError('Unexpected local-error trace')
        rows.append(dict(scheme=e.label,tampered_block=32,damaged_blocks=';'.join(map(str,wrong)),
                         first_intact_later_block=max(wrong)+1,detected_by_scheme=False))
    dump(outdir/'recovery.csv',rows)

def optimization(specs,outdir,config):
    rows=[];p=hashlib.shake_256(b'optimization fixture').digest(4096)
    rounds=3 if config['preset']=='smoke' else 50
    for scheme,mask in specs:
        fast=Engine(scheme,mask);ref=ReferenceEngine(scheme,mask,key=fast.k1+fast.k2);c=fast.encrypt(p,11)
        for decrypt in (False,True):
            source=c if decrypt else p;expected=p if decrypt else c
            for repeat in range(2 if config['preset']=='smoke' else 5):
                for engine in ((ref,fast) if repeat%2==0 else (fast,ref)):
                    tick=perf_counter_ns()
                    for _ in range(rounds):result=engine.crypt(source,11,decrypt)
                    elapsed=perf_counter_ns()-tick
                    assert result==expected
                    rows.append(dict(scheme=fast.label,direction='decrypt' if decrypt else 'encrypt',implementation='optimized' if engine is fast else 'reference',repeat=repeat,rounds=rounds,elapsed_ns=elapsed,ns_sector=elapsed/rounds))
    dump(outdir/'optimization_raw.csv',rows)
