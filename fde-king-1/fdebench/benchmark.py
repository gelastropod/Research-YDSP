"""Each child process is one launch. Record batches, not bytes as replicates."""
import csv,hashlib,json,os,platform,random,sys,threading,time,importlib.metadata
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter_ns
from Crypto.Util import _cpu_features
from cryptography.hazmat.backends.openssl.backend import backend
from .engine import Engine,Cost,build,reference_for

MIB=1<<20

def environment(config):
    cpu=platform.processor() or os.environ.get('PROCESSOR_IDENTIFIER','not exposed')
    if Path('/proc/cpuinfo').exists():
        cpu=next((x.partition(':')[2].strip() for x in Path('/proc/cpuinfo').read_text().splitlines() if x.startswith('model name')),cpu)
    affinity=sorted(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else None
    frequency={}
    for j in (affinity or [])[:16]:
        p=Path(f'/sys/devices/system/cpu/cpu{j}/cpufreq/scaling_cur_freq')
        if p.exists():
            try:frequency[str(j)]=int(p.read_text())
            except (OSError,ValueError):pass
    source={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')}
    return dict(source_sha256=source,timestamp_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),python=sys.version,
        platform=platform.platform(),cpu_model=cpu,logical_cpus=os.cpu_count(),affinity=affinity,
        frequency_khz_snapshot=frequency or 'not exposed',execution='CPU only; no GPU/CUDA',
        gil_enabled=getattr(sys,'_is_gil_enabled',lambda:True)(),aes_ni_available=bool(_cpu_features.have_aes_ni()),
        clmul_available=bool(_cpu_features.have_clmul()),openssl=backend.openssl_version_text(),
        packages={n:importlib.metadata.version(n) for n in ('cryptography','pycryptodome','blake3','PyNaCl','numpy','matplotlib','pandas')},
        clock='perf_counter_ns',timer_resolution_ns=time.get_clock_info('perf_counter').resolution*1e9,
        conditions='Frequency/power/background load not controlled; snapshots do not prove constant clock',
        key_fixture='Shared public benchmark fixture; not production keys',config=config)

class Writer:
    def __init__(self,out,session):self.out=out;self.session=session;self.handles={}
    def write(self,name,rows):
        if not rows:return
        if name not in self.handles:
            path=self.out/'[RAW]'/f'session-{self.session:02d}-{name}.csv'
            f=path.open('w',newline='',encoding='utf-8');w=csv.DictWriter(f,fieldnames=['session']+list(rows[0]));w.writeheader()
            self.handles[name]=(f,w)
        f,w=self.handles[name]
        w.writerows(dict(session=self.session,**r) for r in rows);f.flush()
    def close(self):
        for f,w in self.handles.values():f.close()

class Progress:
    def __init__(self,label,total):self.label=label;self.total=total;self.n=0;self.start=time.perf_counter()
    def step(self):
        self.n+=1;t=time.perf_counter()-self.start
        print(f'{self.label}: {self.n}/{self.total}; elapsed {t:.1f}s; remaining ~{t/self.n*(self.total-self.n):.1f}s',flush=True)

def fixture(engine,plain,size):
    return b''.join(engine.encrypt(plain[k:k+size],k//size) for k in range(0,len(plain),size))

def pass_sectors(engine,source,size,decrypt):
    sink=0
    for k in range(0,len(source),size):
        value=engine.crypt(source[k:k+size],k//size,decrypt);sink^=value[-1]
    return sink

def measure(cfg,out,session):
    out=Path(out);rng=random.Random(cfg['seed']+session*10007);writer=Writer(out,session)
    (out/'[RAW]'/f'session-{session:02d}-environment.json').write_text(json.dumps(environment(cfg),indent=2)+'\n',encoding='utf-8')
    disk=bytearray(hashlib.shake_256(b'fde-xex benchmark image v1').digest(64*MIB))
    try:
        engines={s:build(s) for s in cfg['schemes']}
        if 1 in cfg['rqs']:components(cfg,engines,rng,writer)
        if 2 in cfg['rqs']:throughput(cfg,engines,disk,rng,writer)
        if 3 in cfg['rqs']:masks(cfg,engines,rng,writer)
        if 4 in cfg['rqs']:
            reads(cfg,engines,rng,writer)
            threads(cfg,engines,disk,rng,writer)
            recovery(engines,writer)
    finally:
        writer.close()
        (out/'[RAW]'/f'session-{session:02d}-end-environment.json').write_text(json.dumps(environment(cfg),indent=2)+'\n',encoding='utf-8')

def components(cfg,engines,rng,w):
    p=hashlib.shake_256(b'component sector').digest(4096);cases=[]
    for label,e in engines.items():
        c=e.encrypt(p,19)
        for decrypt in (False,True):cases.append((label,e,c if decrypt else p,decrypt))
    records=[];step=max(1,cfg['profile_rounds']//10);progress=Progress('RQ1 profiling rounds',cfg['profile_rounds'])
    for repeat in range(cfg['profile_rounds']):
        order=cases.copy();rng.shuffle(order)
        for label,e,source,decrypt in order:
            cost=Cost();result=e.crypt(source,19,decrypt,cost)
            other=max(0,cost.wall_ns-cost.seed_ns-cost.mask_ns-cost.data_ns-cost.library_ns)
            records.append(dict(scheme=label,direction='decrypt' if decrypt else 'encrypt',repeat=repeat,
                **vars(cost),other_ns=other,table_payload_bytes=e.table_bytes,sink=result[-1]))
        if (repeat+1)%step==0 or repeat+1==cfg['profile_rounds']:
            progress.n=repeat;progress.step()
    w.write('profile',records)  # One buffered write after the entire profile phase.
    rows=[]
    labels=list(engines)
    for repeat in range(cfg['setup_repeats']):
        rng.shuffle(labels)
        for label in labels:
            tick=perf_counter_ns();e=build(label);elapsed=perf_counter_ns()-tick
            rows.append(dict(scheme=label,repeat=repeat,setup_ns=elapsed,table_payload_bytes=e.table_bytes))
    w.write('setup',rows)
    # Alternate within each pair; randomize pairs to reduce ordering bias.
    optcases=[]
    for label,e in engines.items():
        ref=reference_for(e);c=e.encrypt(p,19)
        for decrypt in (False,True):optcases.append((label,e,ref,c if decrypt else p,decrypt))
    progress=Progress('RQ1 paired optimization rounds',cfg['optimization_repeats'])
    for repeat in range(cfg['optimization_repeats']):
        rng.shuffle(optcases);rows=[]
        for label,e,ref,source,decrypt in optcases:
            pair=[('reference',ref),('candidate',e)];rng.shuffle(pair)
            expected=p if decrypt else e.encrypt(p,19)
            for implementation,obj in pair:
                obj.crypt(source,19,decrypt)
                tick=perf_counter_ns()
                for _ in range(cfg['optimization_rounds']):result=obj.crypt(source,19,decrypt)
                elapsed=perf_counter_ns()-tick
                if result!=expected:raise AssertionError('Reference/candidate mismatch')
                rows.append(dict(scheme=label,direction='decrypt' if decrypt else 'encrypt',repeat=repeat,
                    implementation=implementation,rounds=cfg['optimization_rounds'],elapsed_ns=elapsed,
                    ns_sector=elapsed/cfg['optimization_rounds']))
        w.write('optimization',rows);progress.step()

def throughput(cfg,engines,disk,rng,w):
    cases=[]
    # Inputs/ciphertexts/keys prepared outside all timed batches; no plaintext-result cache.
    for mib in cfg['work_mib']:
        plain=bytes(memoryview(disk)[:int(mib*MIB)])
        for size in cfg['sector_sizes']:
            for label,e in engines.items():
                cipher=fixture(e,plain,size)
                for decrypt in (False,True):cases.append((label,e,mib,size,decrypt,cipher if decrypt else plain))
    rng.shuffle(cases)
    print('RQ2 warming all conditions',flush=True)
    for label,e,mib,size,decrypt,source in cases:pass_sectors(e,source,size,decrypt)
    progress=Progress('RQ2 timed conditions',cfg['repeats']*len(cases))
    for repeat in range(cfg['repeats']):
        rng.shuffle(cases)
        for label,e,mib,size,decrypt,source in cases:
            tick=perf_counter_ns();sink=pass_sectors(e,source,size,decrypt);elapsed=perf_counter_ns()-tick
            n=len(source)//size
            w.write('throughput',[dict(scheme=label,direction='decrypt' if decrypt else 'encrypt',work_mib=mib,
                sector_size=size,repeat=repeat,bytes=len(source),sectors=n,elapsed_ns=elapsed,
                mib_s=len(source)*1e9/MIB/elapsed,ns_sector=elapsed/n,ns_byte=elapsed/len(source),sink=sink)])
            progress.step()

def masks(cfg,engines,rng,w):
    candidates=[(s,e) for s,e in engines.items() if e.mask is not None]
    if not candidates:print('RQ3 skipped: no mask profiles selected',flush=True);return
    prefixes=[(19).to_bytes(16,'big')+j.to_bytes(16,'big') for j in range(256)]
    contexts=[x+hashlib.sha256(x).digest()[:16] for x in prefixes]
    cases=[(s,e,dep) for s,e in candidates for dep in (False,True)]
    for s,e,dep in cases:e.mask(contexts[0])
    progress=Progress('RQ3 timed conditions',len(cases)*cfg['repeats'])
    for repeat in range(cfg['repeats']):
        rng.shuffle(cases)
        for label,e,dependent in cases:
            h=e.mask;state=bytes(16);calls=cfg['hash_calls']
            tick=perf_counter_ns()
            if dependent:
                for i in range(calls):state=h(prefixes[i&255]+state)
            else:
                for i in range(calls):state=h(contexts[i&255])
            elapsed=perf_counter_ns()-tick
            w.write('mask',[dict(scheme=label,dependent=dependent,repeat=repeat,calls=calls,elapsed_ns=elapsed,
                ns_call=elapsed/calls,sink=state[-1])]);progress.step()

def reads(cfg,engines,rng,w):
    p=hashlib.shake_256(b'random access').digest(4096);cases=[];records=[]
    for label,e in engines.items():
        c=e.encrypt(p,19)
        for j in (0,31,63,127,191,255):
            for _ in range(10):e.decrypt_block(c,19,j)
            cases.append((label,e,c,j))
    for repeat in range(cfg['read_samples']):
        rng.shuffle(cases)
        for label,e,c,j in cases:
            tick=perf_counter_ns();result=e.decrypt_block(c,19,j);elapsed=perf_counter_ns()-tick
            if result!=p[16*j:16*(j+1)]:raise AssertionError('Random read failed')
            needed=4096 if label=='xts_library' else (16 if label.startswith(('ecb','xts')) or not j else 32)
            records.append(dict(scheme=label,block=j+1,repeat=repeat,elapsed_ns=elapsed,ciphertext_bytes=needed))
    w.write('reads',records)

def pool_for(label,workers):
    local=threading.local();barrier=threading.Barrier(workers)
    pool=ThreadPoolExecutor(max_workers=workers)
    def warm():local.engine=build(label);barrier.wait()
    try:
        for f in [pool.submit(warm) for _ in range(workers)]:f.result()
    except BaseException:
        pool.shutdown();raise
    return pool,local

def threads(cfg,engines,disk,rng,w):
    items=[(s,kib) for s in engines for kib in cfg['thread_kib']];rng.shuffle(items)
    for label,kib in items:
        print(f'RQ4 {label}, {kib:g} KiB: pool/key setup and warm-up',flush=True)
        plain=bytes(memoryview(disk)[:int(kib*1024)]);cipher=fixture(engines[label],plain,4096);sectors=len(plain)//4096
        pools={}
        try:
            for workers in cfg['workers']:pools[workers]=pool_for(label,workers)
            def run(workers,decrypt):
                pool,local=pools[workers];source=cipher if decrypt else plain
                def job(lo,hi):
                    sink=0
                    for j in range(lo,hi):sink^=local.engine.crypt(source[j*4096:(j+1)*4096],j,decrypt)[-1]
                    return sink
                bounds=[(sectors*i//workers,sectors*(i+1)//workers) for i in range(workers)]
                futures=[pool.submit(job,*b) for b in bounds]
                return sum(f.result() for f in futures)
            cases=[(t,d) for t in cfg['workers'] for d in (False,True)]
            for t,d in cases:run(t,d)
            progress=Progress(f'RQ4 {label} {kib:g} KiB trials',cfg['thread_repeats'])
            for repeat in range(cfg['thread_repeats']):
                rng.shuffle(cases);rows=[]
                for workers,decrypt in cases:
                    tick=perf_counter_ns();sink=run(workers,decrypt);elapsed=perf_counter_ns()-tick
                    rows.append(dict(scheme=label,thread_kib=kib,direction='decrypt' if decrypt else 'encrypt',workers=workers,
                        repeat=repeat,bytes=len(plain),elapsed_ns=elapsed,mib_s=len(plain)*1e9/MIB/elapsed,sink=sink))
                w.write('threads',rows);progress.step()
            # Once per scheme (not repeated for every inter-sector batch size).
            if kib==cfg['thread_kib'][0] and label!='xts_library':
                cases=cfg['workers'].copy();rows=[]
                for repeat in range(cfg['thread_repeats']):
                    rng.shuffle(cases)
                    for workers in cases:
                        pool,local=pools[workers];c=cipher[:4096]
                        bounds=[(256*i//workers,256*(i+1)//workers) for i in range(workers)]
                        def part(lo,hi):return local.engine.decrypt_range(c,0,lo,hi)
                        tick=perf_counter_ns()
                        for _ in range(cfg['within_sectors']):
                            futures=[pool.submit(part,*b) for b in bounds];recovered=b''.join(f.result() for f in futures)
                        elapsed=perf_counter_ns()-tick
                        if recovered!=plain[:4096]:raise AssertionError('Range recovery failed')
                        rows.append(dict(scheme=label,workers=workers,repeat=repeat,sectors=cfg['within_sectors'],
                            elapsed_ns=elapsed,ns_sector=elapsed/cfg['within_sectors']))
                w.write('within',rows)
        finally:
            for pool,local in pools.values():pool.shutdown()

def recovery(engines,w):
    p=hashlib.shake_256(b'recovery trace').digest(4096);rows=[]
    for label,e in engines.items():
        for r in (0,31,255):
            c=bytearray(e.encrypt(p,0));c[16*r]^=1;value=e.decrypt(bytes(c),0)
            wrong=[j+1 for j in range(256) if value[16*j:16*(j+1)]!=p[16*j:16*(j+1)]]
            expected=[r+1] if label.startswith(('ecb','xts')) or r==255 else [r+1,r+2]
            if wrong!=expected:raise AssertionError('Unexpected local recovery')
            rows.append(dict(scheme=label,tampered_block=r+1,damaged_blocks=';'.join(map(str,wrong)),detected=False))
    w.write('recovery',rows)
