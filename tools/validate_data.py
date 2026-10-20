"""Validate the released tables and Figure 4/5 data relationships."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
R=Path(__file__).resolve().parents[1]
read=lambda p:pd.read_csv(R/p)
front=read('data/figure4/R07_ParetoFront_REVISED.csv')
best=read('data/figure4/R07_BestCompromise_REVISED.csv')
ranges=read('data/figure4/R07_ParetoRanges_ByClass_REVISED.csv')
main=read('data/figure5/R08_FinalManagement_ByClass_REVISED.csv')
area=read('data/figure5/R08_Management_AreaSummary_REVISED.csv')
assert len(front)==480 and len(best)==25 and best.ClassCode.nunique()==25
assert len(main)==58 and main.ClassCode.nunique()==58 and len(ranges)==25
assert best.LifeFormStructure.value_counts().to_dict()=={'low-tree mixed':22,'shrub-herbaceous':3}
assert not front.duplicated(['ClassCode','CandidateID']).any()
cols=['q_tree','q_shrub','q_herb']
for df in (front,best):assert np.allclose(df[cols].sum(axis=1),1)
for c in cols:
    bounds=front.groupby('ClassCode')[c].agg(['min','max'])
    b=ranges.set_index('ClassCode').sort_index()
    assert np.allclose(bounds['min'],b[c+'_min']) and np.allclose(bounds['max'],b[c+'_max'])
joined=best.merge(front,on=['ClassCode','CandidateID'],suffixes=('_selected','_front'),validate='one_to_one')
assert len(joined)==25
for c in cols+['LAI_target','obj1_sand_benefit','obj2_eco_stability','obj3_water_pressure','obj4_gde_risk']:
    assert np.allclose(joined[c+'_selected'],joined[c+'_front'])
assert np.isclose(main.Area_km2.sum(),3999548.721424142)
group=main.groupby('FinalManagementPathway').agg(Area_km2=('Area_km2','sum'),n_ClassCode=('ClassCode','nunique'))
for _,r in area.iterrows():
    assert np.isclose(r.Area_km2,group.loc[r.FinalManagementPathway,'Area_km2'])
    assert r.n_ClassCode==group.loc[r.FinalManagementPathway,'n_ClassCode']
    assert np.isclose(r.Area_share_pct,100*r.Area_km2/main.Area_km2.sum())
for file,key,pct in [('R08_Management_ByGDE_REVISED.csv','GDE_Level','Within_GDE_Level_pct'),('R08_Management_ByAridity_REVISED.csv','AridityClass','Within_Aridity_pct')]:
    df=read('data/figure5/'+file)
    assert np.allclose(df.groupby(key)[pct].sum(),100)
    actual=main.groupby([key,'FinalManagementPathway']).Area_km2.sum()
    for _,r in df.iterrows():assert np.isclose(r.Area_km2,actual.get((r[key],r.FinalManagementPathway),0))
assert main.Figure5_EF_Include.sum()==25
ef=main[main.Figure5_EF_Include==1]
assert ef.FinalManagementPathway.value_counts().to_dict()=={'Close-to-nature structural management':15,'Low-tree mixed restoration':10}
assert set(ef.ClassCode)==set(best.ClassCode)
print('PASS: 58 units; 480 Pareto records; 25 selected units; 22/3 structures; regional and group-area summaries; q proportions; selected candidates.')
