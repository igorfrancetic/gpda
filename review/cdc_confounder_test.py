"""
Does the community diagnostic centre programme explain the November 2022 step?

Sivey and Wen (2024, Health Policy 147:105101) show CDCs raised diagnostic
volume by about 6% with no effect on waiting times, which makes them the
obvious confounder for this analysis. Two things answer the concern.

First, timing. Every one of the 79 dated first-wave CDCs in the government's
operational list went live between July 2021 and August 2022, and 84% of them
in 2021 Q3-Q4 - all of it before the November 2022 announcement. A programme
that finished rolling out before the announcement cannot manufacture a step at
it; it shifts the pre-period level, which the fixed effects absorb.

Second, a direct test. Adding regional CDC exposure, the cumulative count of
CDCs live in a trust's region, interacted with the GP series, leaves the
announcement effect intact and slightly larger.

Caveats: regional exposure is coarse with only seven regions, and the
government list is current to 14 August 2022, so it says nothing about the
later CDC waves that ran through 2025. Those remain the most plausible
explanation for the further rise observed from 2023/24 Q4 onward. Matching
CDCs to parent trusts via the ODS Portal, as Sivey and Wen did, would sharpen
both points.

    python review/build_panel.py && python review/cdc_confounder_test.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from did_analysis import areg, pct
import pandas as pd, numpy as np
from scipy import stats

# Region now travels with the panel (review/build_panel.py), so this script
# has no dependency on the original replication package.
cdc=pd.read_csv('datain/cdc/cdc_operational_2022-08-14.tsv',sep='\t')
cdc['dt']=pd.to_datetime(cdc.live_date,format='%d %b %Y',errors='coerce')
cdc=cdc.dropna(subset=['dt'])

P=pd.read_csv('review/results/panel_from_raw.csv',parse_dates=['ym'])
COV=['Chest (X-ray)','Chest and/or abdomen (CT)','Brain (MRI)','Abdomen and/or pelvis (Ultrasound)']
regmap=P.dropna(subset=['region']).groupby('orgcode').region.first()
w=P[P.test.isin(COV)].pivot_table(index=['orgcode','ym'],columns='src',values='events',aggfunc='sum').reset_index()
w.columns.name=None; w['cmp']=w['All']-w['GP Direct Access']
a=w[['orgcode','ym','GP Direct Access']].rename(columns={'GP Direct Access':'y'}).assign(gp=1)
b=w[['orgcode','ym','cmp']].rename(columns={'cmp':'y'}).assign(gp=0)
L=pd.concat([a,b]).dropna(subset=['y']); L=L[L.y>0].copy()
L['region']=L.orgcode.map(regmap)
L=L.dropna(subset=['region'])
L['ly']=np.log(L.y); L['post']=(L.ym>='2022-11-01').astype(float)
L['cell']=L.orgcode+'_'+L.gp.astype(str); L['mo']=L.ym.astype(str); L['cm']=L.ym.dt.month
L=L[~((L.ym>='2020-03-01')&(L.ym<='2021-03-01'))]

# cumulative CDCs live in each region by month, normalised
months=sorted(L.ym.unique())
cum=[]
for r in cdc.region.unique():
    dts=cdc[cdc.region==r].dt
    for m in months: cum.append((r,m,(dts<=m).sum()))
C=pd.DataFrame(cum,columns=['region','ym','ncdc'])
L=L.merge(C,on=['region','ym'],how='left'); L['ncdc']=L.ncdc.fillna(0)
L['ncdc_z']=(L.ncdc-L.ncdc.mean())/L.ncdc.std()

def run(extra, label):
    n,X=[],[]
    def add(k,v): n.append(k); X.append(np.asarray(v,float))
    add('post#GP', L.post*L.gp)
    for k,v in extra: add(k,v)
    for c in sorted(L.cm.unique())[1:]: add(f'gpM{c}',(L.cm==c).astype(float)*L.gp)
    for m in sorted(L.mo.unique())[1:]: add(f'mo_{m}',(L.mo==m).astype(float))
    bb,V,N,Cn=areg(L,'ly',n,np.column_stack(X),'cell','orgcode')
    print(f"\n{label}")
    for k in ['post#GP']+[e[0] for e in extra]:
        e=bb[k]; se=V.loc[k,k]**0.5
        print(f"   {k:<22s} {pct(e):+6.2f}%  [{pct(e-1.96*se):+6.2f},{pct(e+1.96*se):+6.2f}]  "
              f"p={2*(1-stats.norm.cdf(abs(e/se))):.4f}")
    print(f"   N={N:,}  trusts={Cn}")

print("Do community diagnostic centres explain the November 2022 step?")
print("All 79 dated first-wave CDCs opened BEFORE the announcement (Jul 2021 - Aug 2022),")
print("so by timing they cannot generate a step at Nov 2022. Testing directly:")
run([], "1. Announcement only")
run([('cdc#GP', L.ncdc_z*L.gp)], "2. + regional CDC exposure (cumulative CDCs live, per SD) x GP")
