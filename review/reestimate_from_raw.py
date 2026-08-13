"""
Re-estimate the manuscript's headline models on the panel rebuilt from the
published DID tables, and compare against what the manuscript reports.

    python review/build_panel.py && python review/reestimate_from_raw.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from did_analysis import areg, pct
import pandas as pd, numpy as np
from scipy import stats

D=pd.read_csv('review/results/panel_from_raw.csv',parse_dates=['ym'])
COV=['Chest (X-ray)','Chest and/or abdomen (CT)','Brain (MRI)','Abdomen and/or pelvis (Ultrasound)']
def prep(d, tests, val='events'):
    w=d[d.test.isin(tests)].pivot_table(index=['orgcode','ym'],columns='src',values=val,aggfunc='sum').reset_index()
    w.columns.name=None
    if val=='events':
        w['cmp']=w['All']-w['GP Direct Access']
    else:
        w['cmp']=w['All']
    a=w[['orgcode','ym','GP Direct Access']].rename(columns={'GP Direct Access':'y'}).assign(gp=1)
    b=w[['orgcode','ym','cmp']].rename(columns={'cmp':'y'}).assign(gp=0)
    L=pd.concat([a,b]).dropna(subset=['y']); L=L[L.y>0].copy()
    L['ly']=np.log(L.y); L['post']=(L.ym>='2022-11-01').astype(float)
    L['cell']=L.orgcode+'_'+L.gp.astype(str); L['mo']=L.ym.astype(str); L['cm']=L.ym.dt.month
    return L

def fit(L,label):
    n,X=[],[]
    def a(k,v): n.append(k); X.append(np.asarray(v,float))
    a('post#GP', L.post*L.gp)
    for c in sorted(L.cm.unique())[1:]: a(f'gpM{c}',(L.cm==c).astype(float)*L.gp)
    for m in sorted(L.mo.unique())[1:]: a(f'mo_{m}',(L.mo==m).astype(float))
    b,V,N,C=areg(L,'ly',n,np.column_stack(X),'cell','orgcode')
    e=b['post#GP']; se=V.loc['post#GP','post#GP']**0.5
    print(f"  {label:<50s} {pct(e):+6.2f}%  [{pct(e-1.96*se):+6.2f},{pct(e+1.96*se):+6.2f}]  "
          f"p={2*(1-stats.norm.cdf(abs(e/se))):.4f}  N={N:,}  post months={int(L[L.post==1].ym.nunique())}")

nocovid=~((D.ym>='2020-03-01')&(D.ym<='2021-03-01'))
print("ACTIVITY, four covered test groups (published estimate was +10.41% [5.76,15.26])")
fit(prep(D[nocovid&(D.ym<='2023-11-01')],COV), "Old window Apr18-Nov23, REBUILT from raw")
fit(prep(D[nocovid&(D.ym<='2024-03-01')],COV), "Through Mar 2024 (truncation fixed)")
fit(prep(D[nocovid],COV),                      "FULL Apr18-Mar25 (extended)")

print("\nWAITING TIME, pooled four covered groups (published was +5.86% [-0.04,12.10])")
for lab,sub in [("Old window Apr18-Nov23, REBUILT", D[nocovid&(D.ym<='2023-11-01')]),
                ("FULL Apr18-Mar25 (extended)", D[nocovid])]:
    fit(prep(sub,COV,val='wait'), lab)

print("\nACTIVITY by test group, FULL window")
for t in COV+['Kidney or Bladder (Ultrasound)']:
    fit(prep(D[nocovid],[t]), t)
