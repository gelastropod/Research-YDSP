"""Conservative launch-median intervals; single-launch bootstrap is provisional."""
import math
import numpy as np
import pandas as pd

def resampled_medians(values,rng,draws,block=1):
    x=np.asarray(values,dtype=float);n=len(x)
    if n<2:return np.full(draws,np.nan)
    # Bound temporary memory for 500 profiling rows or many read samples.
    out=[]
    for k in range(0,draws,1000):
        m=min(1000,draws-k)
        starts=rng.integers(n,size=(m,(n+block-1)//block))
        idx=((starts[:,:,None]+np.arange(block))%n).reshape(m,-1)[:,:n]
        out.append(np.median(x[idx],axis=1))
    return np.concatenate(out)

def launch_interval(values):
    """Conservative distribution-free >=95% median CI under iid launches.

    [X_(k), X_(n-k+1)], coverage >= 1-2*P[Bin(n,1/2)<k].
    Six launches are the minimum for finite two-sided 95% bounds.
    """
    x=np.sort(np.asarray(values,float));n=len(x);best=None
    for k in range(1,(n+1)//2+1):
        coverage=1-2*sum(math.comb(n,j) for j in range(k))/2**n
        if coverage>=.95:best=(float(x[k-1]),float(x[n-k]),coverage)
    return best if best else (np.nan,np.nan,np.nan)

def estimate(frame,column,rng,draws):
    groups=[g[column].to_numpy(dtype=float) for _,g in frame.groupby('session',sort=True)]
    medians=np.array([np.median(v) for v in groups]);point=float(np.median(medians))
    if len(groups)>1:
        dist=None
        scope='between_launch_order_statistics';effective=len(groups)
    else:
        dist=resampled_medians(groups[0],rng,draws,block=2)
        scope='within_launch_adjacent_pair_bootstrap';effective=len(groups[0])
    if len(groups)>1:
        low,high,coverage=launch_interval(medians)
    else:
        finite=dist[np.isfinite(dist)]
        low,high=np.quantile(finite,[.025,.975]) if len(finite) else (np.nan,np.nan)
        coverage=np.nan
    return dict(median=point,ci_low=low,ci_high=high,sessions=len(groups),samples=len(frame),
                ci_scope=scope,ci_replicates=effective,coverage_lower_bound=coverage,
                ci_reliable=('requires_at_least_six_launches' if 1<len(groups)<6 else 'requires_iid_launches' if len(groups)>=6 else 'provisional_within_launch'))

def summarize(frame,keys,column,rng,draws):
    rows=[]
    for values,g in frame.groupby(keys,sort=True):
        if not isinstance(values,tuple):values=(values,)
        rows.append(dict(zip(keys,values),**estimate(g,column,rng,draws)))
    return pd.DataFrame(rows)

def paired_ratio(frame,keys,value,level,numerator,denominator,rng,draws):
    """Pair session medians; one-launch fallback resamples phases separately."""
    rows=[]
    for values,g in frame.groupby(keys,sort=True):
        if not isinstance(values,tuple):values=(values,)
        a=g[g[level]==numerator];b=g[g[level]==denominator]
        ma=a.groupby('session')[value].median();mb=b.groupby('session')[value].median()
        shared=ma.index.intersection(mb.index)
        if len(shared)>1:
            ratios=(ma.loc[shared]/mb.loc[shared]).to_numpy();point=np.median(ratios)
            dist=None;scope='paired_launch_order_statistics'
        elif len(shared)==1:
            av=a[a.session==shared[0]][value].to_numpy();bv=b[b.session==shared[0]][value].to_numpy()
            point=np.median(av)/np.median(bv)
            dist=resampled_medians(av,rng,draws,2)/resampled_medians(bv,rng,draws,2)
            scope='within_launch_phase_ratio'
        else:continue
        if len(shared)>1:lo,hi,coverage=launch_interval(ratios)
        else:
            finite=dist[np.isfinite(dist)];lo,hi=np.quantile(finite,[.025,.975]) if len(finite) else (np.nan,np.nan)
            coverage=np.nan
        rows.append(dict(zip(keys,values),ratio=point,ci_low=lo,ci_high=hi,sessions=len(shared),ci_scope=scope,coverage_lower_bound=coverage,
                         within_five_percent=(bool(lo>=.95 and hi<=1.05) if np.isfinite(lo) and np.isfinite(hi) else np.nan)))
    return pd.DataFrame(rows)
