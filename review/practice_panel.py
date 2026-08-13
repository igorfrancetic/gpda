#!/usr/bin/env python3
"""
Practice-level analysis of the quarterly GP Direct Access extract
(datain/gpda.xlsx), 2018/19 Q1 to 2025/26 Q1.

Two things this data can do that the trust panel cannot.

1. WITHIN-PRACTICE IDENTIFICATION. The extract is practice x provider x
   quarter. Quarterly aggregation reveals far more structure than the monthly
   file suggested: 2.81 providers per practice-quarter on average (the monthly
   file showed 1.87), a median of 13 distinct providers per practice over the
   period, and 7,683 practices using at least two. That supports a design with
   practice x provider AND practice x quarter fixed effects, which absorbs
   every practice-level shock - including the national policy itself - and
   identifies from variation across providers used by the SAME practice in the
   SAME quarter. Any provider-level exposure can then be tested cleanly.

2. THE FULL SERIES. Seven years through mid-2025, so the persistence of the
   post-announcement change can be traced.

Caveats
-------
  * The announcement (November 2022) falls inside 2022/23 Q3, so that quarter
    is transitional and is dropped from the within-practice models.
  * Small counts are suppressed with an asterisk: 45% of rows but only 0.4% of
    volume. They are imputed uniform on 1-3, as in the original analysis.
  * This extract covers ALL modalities and body sites, and is about three
    times the size of the cancer-suitable subset the trust panel uses. It has
    no non-GP comparator, so it cannot support the difference-in-differences;
    it complements the trust panel rather than replacing it.

    python review/practice_panel.py
"""
import pandas as pd, numpy as np
from scipy import stats


def read_gpda(path):
    """Stream the quarterly practice x provider extract out of the workbook."""
    import openpyxl
    ws = openpyxl.load_workbook(path, read_only=True, data_only=True)["By provider and GP practice"]
    rows = [r[:7] for r in ws.iter_rows(min_row=11, values_only=True) if r[0] is not None]
    return pd.DataFrame(rows, columns=["fy", "qtr", "prov", "provname", "gp", "gpname", "cases"])

# ---------- two-way high-dimensional FE via alternating projections ----------
def demean2(M, g1, g2, tol=1e-9, maxit=200):
    M = np.asarray(M, float).copy()
    n1, n2 = g1.max()+1, g2.max()+1
    c1 = np.bincount(g1, minlength=n1).astype(float)
    c2 = np.bincount(g2, minlength=n2).astype(float)
    for _ in range(maxit):
        prev = M.copy()
        for j in range(M.shape[1]):
            M[:,j] -= (np.bincount(g1, weights=M[:,j], minlength=n1)/c1)[g1]
            M[:,j] -= (np.bincount(g2, weights=M[:,j], minlength=n2)/c2)[g2]
        if np.max(np.abs(M-prev)) < tol: break
    return M

def fit(df, y, xnames, X, fe1, fe2, cluster):
    g1 = pd.factorize(df[fe1])[0]; g2 = pd.factorize(df[fe2])[0]
    A = demean2(np.column_stack([df[y].to_numpy(float)]+[np.asarray(x,float) for x in X]), g1, g2)
    yd, Xd = A[:,0], A[:,1:]
    keep = Xd.std(axis=0) > 1e-10
    Xd, xnames = Xd[:,keep], [n for n,k in zip(xnames,keep) if k]
    XtXi = np.linalg.pinv(Xd.T@Xd); b = XtXi@(Xd.T@yd); e = yd - Xd@b
    cl = pd.factorize(df[cluster])[0]; C = cl.max()+1
    s = np.zeros((C, Xd.shape[1])); np.add.at(s, cl, Xd*e[:,None])
    N, K = len(yd), Xd.shape[1] + g1.max()+1 + g2.max()+1
    V = (C/(C-1))*((N-1)/(N-K))*(XtXi@(s.T@s)@XtXi)
    return pd.Series(b,index=xnames), pd.DataFrame(V,index=xnames,columns=xnames), N, C

# ---------- panel ----------
d = read_gpda('datain/gpda.xlsx')
d.columns=['fy','qtr','prov','provname','gp','gpname','cases']
d['n']=pd.to_numeric(d.cases,errors='coerce'); d['sup']=d.cases.astype(str).str.strip()=='*'
rng=np.random.default_rng(333); d.loc[d.sup,'n']=rng.integers(1,4,int(d.sup.sum()))
d['qn']=d.qtr.str[-1].astype(int); d['fy4']=d.fy.astype(str).str[:4].astype(int)
d['t']=d.fy4*4+d.qn
d=d[d.prov.str.startswith('R') & (d.n>0)].copy()
# announcement Nov 2022 falls inside 2022/23 Q3 -> drop that transitional quarter
ANN = 2022*4+4          # first full post quarter = 2022/23 Q4 (Jan-Mar 2023)
d['post']=(d.t>=ANN).astype(float)
d=d[d.t!=2022*4+3]

# ---------- trust capacity, as built for the original paper ----------
cap=pd.read_excel('replication/datain/National-Imaging-Data-Collection-Asset-Count-2022-23-v1.xlsx',
                  sheet_name='ICB, Imaging Network and Trust', header=13, usecols='B:S')
cap=cap.rename(columns={'Organisation Code':'prov','MRI':'k_mri','CT':'k_ct','Ultrasound':'k_us'})
cap=cap[cap.prov.notna()]; cap['k_tot']=cap.k_mri+cap.k_ct+cap.k_us
wf=pd.read_csv('replication/datain/NHS Workforce Statistics, October 2022 medical staff.csv')
wf=wf[wf.Specialty.isin(['Clinical radiology','Medical oncology'])]
wf=wf.groupby('Org code',as_index=False)['Total FTE'].sum().rename(columns={'Org code':'prov','Total FTE':'fte'})
cap=cap.merge(wf,on='prov',how='left'); cap['ratio']=cap.fte/cap.k_tot
ok=cap.ratio.notna(); cap.loc[ok,'tert']=pd.qcut(cap.loc[ok,'ratio'],3,labels=[1,2,3]).astype(float)

m=d.merge(cap[['prov','ratio','tert']],on='prov',how='inner').dropna(subset=['tert'])
m['ly']=np.log(m.n); m['pair']=m.gp+'_'+m.prov; m['pq']=m.gp+'_'+m.t.astype(str)
print(f"rows {len(m):,}  practices {m.gp.nunique():,}  providers {m.prov.nunique()}  quarters {m.t.nunique()}")
print(f"practice-provider pairs {m.pair.nunique():,}   practice-quarter cells {m.pq.nunique():,}")

print("\n=== WITHIN-PRACTICE design: practice x provider FE + practice x quarter FE ===")
print("    every practice-level shock (incl. the national policy) is absorbed;")
print("    identification is across providers used by the SAME practice in the SAME quarter\n")
X=[m.post*(m.tert==2), m.post*(m.tert==3)]
b,V,N,C=fit(m,'ly',['post#T2','post#T3'],X,'pair','pq','prov')
for k in ['post#T2','post#T3']:
    e=b[k]; se=V.loc[k,k]**0.5
    print(f"  {k} (vs bottom tertile): {100*(np.exp(e)-1):+6.2f}%  "
          f"[{100*(np.exp(e-1.96*se)-1):+6.2f},{100*(np.exp(e+1.96*se)-1):+6.2f}]  "
          f"p={2*(1-stats.norm.cdf(abs(e/se))):.4f}")
print(f"  N={N:,}  clusters(providers)={C}")


# ===================== adjusted quarterly path =====================
REF=2022*4+2                                   # 2022/23 Q2, last full pre-announcement quarter
ts=sorted(d.t.unique())
names,X=[],[]
for tt in ts:
    if tt==REF: continue
    names.append(tt); X.append((d.t==tt).astype(float))
# absorb practice-provider pair; quarter dummies are the regressors; cluster on practice
g=pd.factorize(d['pair'])[0]
A=np.column_stack([d.ly.to_numpy(float)]+[np.asarray(x,float) for x in X])
cnt=np.bincount(g,minlength=g.max()+1).astype(float)
for j in range(A.shape[1]):
    A[:,j]-= (np.bincount(g,weights=A[:,j],minlength=g.max()+1)/cnt)[g]
yd,Xd=A[:,0],A[:,1:]
XtXi=np.linalg.pinv(Xd.T@Xd); b=XtXi@(Xd.T@yd); e=yd-Xd@b
cl=pd.factorize(d.gp)[0]; C=cl.max()+1
s=np.zeros((C,Xd.shape[1])); np.add.at(s,cl,Xd*e[:,None])
N,K=len(yd),Xd.shape[1]+g.max()+1
V=(C/(C-1))*((N-1)/(N-K))*(XtXi@(s.T@s)@XtXi); se=np.sqrt(np.diag(V))
print(f"Adjusted quarterly path, GP direct access per practice-provider pair")
print(f"practice-provider fixed effects; reference 2022/23 Q2; clustered on {C:,} practices; N={N:,}\n")
for nm,coef,s_ in zip(names,b,se):
    q=((nm-1)%4)+1; fy=(nm-q)//4; lab=f"{fy}/{str(fy+1)[2:]} Q{q}"
    mark=''
    if nm==2022*4+3: mark='   <- announcement quarter (transitional)'
    if nm==2022*4+4: mark='   <- first full post quarter'
    star='*' if abs(coef/s_)>1.96 else ' '
    print(f"  {lab:>11}  {100*(np.exp(coef)-1):+7.2f}%  [{100*(np.exp(coef-1.96*s_)-1):+7.2f},"
          f"{100*(np.exp(coef+1.96*s_)-1):+7.2f}] {star}{mark}")
