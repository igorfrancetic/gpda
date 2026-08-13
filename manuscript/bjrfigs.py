import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt, pandas as pd, numpy as np
BLUE,ORANGE,INK,MUTED='#0072B2','#D55E00','#1a1a1a','#6b6b6b'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,'axes.edgecolor':'#999999',
  'axes.linewidth':.8,'xtick.color':MUTED,'ytick.color':MUTED,'text.color':INK,
  'axes.labelcolor':INK,'figure.dpi':300})

# ---------- Figure 1 : GP share over time ----------
g=pd.read_csv('bjr_fig1.csv',parse_dates=['ym'])
fig,ax=plt.subplots(figsize=(7.0,3.2))
ax.axvspan(pd.Timestamp('2020-03-01'),pd.Timestamp('2021-03-01'),color='#e9e9e9',lw=0,zorder=0)
ax.text(pd.Timestamp('2020-09-01'),9.6,'Pandemic disruption\n(excluded from models)',
        ha='center',va='bottom',fontsize=6.6,color=MUTED)
ax.plot(g.ym,g.share,color=BLUE,lw=1.5,zorder=3)
ax.axvline(pd.Timestamp('2022-11-01'),color=ORANGE,lw=1.2,ls=(0,(4,3)),zorder=4)
ax.annotate('Policy announced\nNov 2022',xy=(pd.Timestamp('2022-11-15'),12.8),
            fontsize=7,color=ORANGE,ha='left',weight='bold')
for x0,x1,lab in [('2018-04-01','2020-02-01','pre-pandemic\nmean 25.1%'),
                  ('2022-11-01','2025-03-01','post-policy\nmean 26.7%')]:
    s=g[(g.ym>=x0)&(g.ym<=x1)].share.mean()
    ax.hlines(s,pd.Timestamp(x0),pd.Timestamp(x1),color=ORANGE if 'post' in lab else MUTED,
              lw=1.6,zorder=5)
    ax.annotate(lab,xy=(pd.Timestamp(x1),s),xytext=(3,-14 if 'pre' in lab else 6),
                textcoords='offset points',fontsize=6.8,
                color=ORANGE if 'post' in lab else MUTED,weight='bold')
ax.set_ylabel('GP direct referrals as % of all\ncancer-detection imaging events')
ax.set_ylim(8,33); ax.grid(axis='y',color='#eee',lw=.6,zorder=0); ax.set_axisbelow(True)
for s in ('top','right'): ax.spines[s].set_visible(False)
fig.tight_layout(); fig.savefig('BJR_Fig1.png',dpi=300,bbox_inches='tight')
fig.savefig('BJR_Fig1.pdf',bbox_inches='tight')

# ---------- Figure 2 : forest, volume vs wait ----------
F=pd.read_csv('bjr_fig2.csv')
order=['Brain MRI','CT chest/abdomen','Chest x-ray','Ultrasound abdomen/pelvis','Ultrasound kidney/bladder']
fig,axes=plt.subplots(1,2,figsize=(7.4,3.0),sharey=True,gridspec_kw={'wspace':.08})
for ax,kind,title,col in [(axes[0],'Volume','Imaging activity',BLUE),
                          (axes[1],'Median wait','Median wait (request to test)',ORANGE)]:
    sub=F[F.kind==kind].set_index('mod').reindex(order).dropna(subset=['est'])
    y=np.arange(len(order))[::-1]
    ax.axvline(0,color='#bbb',lw=.8,zorder=1)
    for yy,m in zip(y,order):
        if m not in sub.index: continue
        r=sub.loc[m]; sig=(r.lo>0)|(r.hi<0); c=col if sig else MUTED
        ax.plot([r.lo,r.hi],[yy,yy],color=c,lw=1.5,solid_capstyle='round',zorder=3)
        ax.plot([r.est],[yy],'o',ms=5.2,color=c,mec='white',mew=.7,zorder=4)
        ax.annotate(f'{r.est:+.1f}%',xy=(r.hi,yy),xytext=(4,0),textcoords='offset points',
                    va='center',fontsize=6.8,color=INK)
    ax.set_title(title,fontsize=8,loc='left',pad=6,weight='bold')
    ax.set_xlabel('Adjusted % change, GP vs other referrals',fontsize=7.2)
    ax.grid(axis='x',color='#eee',lw=.6,zorder=0); ax.set_axisbelow(True)
    for s in ('top','right','left'): ax.spines[s].set_visible(False)
    ax.tick_params(axis='y',length=0)
axes[0].set_yticks(np.arange(len(order))[::-1]); axes[0].set_yticklabels(order,fontsize=7.2)
axes[0].set_xlim(-12,56); axes[1].set_xlim(-34,26)
fig.tight_layout(); fig.savefig('BJR_Fig2.png',dpi=300,bbox_inches='tight')
fig.savefig('BJR_Fig2.pdf',bbox_inches='tight')
print('ok')
