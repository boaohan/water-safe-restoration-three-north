"""Compare regenerated key tables with supplied snapshots, including row identities."""
from pathlib import Path
import argparse, json
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--run',default='build/run');a=p.parse_args()
run=ROOT/a.run
keys={'R02_Class_LAIhydro_q25.csv':['ClassCode'],'R03_Class_Occupancy.csv':['ClassCode'],
      'R04_Class_LAIsafe.csv':['ClassCode'],'R05_Class_Eligibility.csv':['ClassCode'],
      'R06_CandidateLibrary.csv':['CandidateID'],'R07_ParetoFront.csv':['CandidateID'],
      'R07_BestCompromise.csv':['ClassCode'],'R08_FinalManagement_ByClass.csv':['ClassCode'],
      'R09C_Transferability_ByClass.csv':['ClassCode']}
report={};all_ok=True
for name,k in keys.items():
    old=pd.read_csv(ROOT/'data/reference'/name).sort_values(k).reset_index(drop=True)
    new=pd.read_csv(run/name).sort_values(k).reset_index(drop=True)
    same_rows=len(old)==len(new) and old[k].equals(new[k]);bad=[];max_diff={}
    cols=sorted(set(old)&set(new))
    if same_rows:
        for c in cols:
            if pd.api.types.is_numeric_dtype(old[c]) and pd.api.types.is_numeric_dtype(new[c]):
                if not np.allclose(old[c],new[c],rtol=1e-8,atol=1e-10,equal_nan=True):
                    bad.append(c)
                    with np.errstate(invalid='ignore'):
                        delta=np.abs(old[c].to_numpy(dtype=float)-new[c].to_numpy(dtype=float))
                    max_diff[c]=float(np.nanmax(delta))
            elif not old[c].fillna('').astype(str).equals(new[c].fillna('').astype(str)):bad.append(c)
    ok=same_rows and not bad
    all_ok &= ok
    report[name]={'rows_reference':len(old),'rows_regenerated':len(new),'row_keys_match':same_rows,'compared_common_columns':len(cols),'reference_only_columns':sorted(set(old)-set(new)),'new_only_columns':sorted(set(new)-set(old)),'different_columns':bad,'max_absolute_differences':max_diff,'common_values_match':bool(ok)}
result={'all_key_tables_match_on_common_columns':bool(all_ok),'rtol':1e-8,'atol':1e-10,'tables':report}
(run/'comparison_report.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
raise SystemExit(0 if all_ok else 1)
