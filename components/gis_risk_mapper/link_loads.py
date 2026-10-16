"""Join modelled transformer loads to solar_with_coords.csv.
Usage: python link_loads.py solar_with_coords.csv Loads.xlsx solar_loads_matched.csv
Key: Loads.SectionId == 'CSE' + SIN. Multiple rows per section (spot + distributed) are summed in kW."""
import sys, pandas as pd
solar_csv, loads_xlsx, out_csv = sys.argv[1:4]
clean = lambda s: s.astype(str).str.replace('\u200d', '').str.strip()

L = pd.read_excel(loads_xlsx)
L['SectionId'] = clean(L.SectionId)
L['kw'] = L[['Phase1Kw', 'Phase2Kw', 'Phase3Kw']].sum(axis=1)
g = L.groupby('SectionId').agg(load_kw=('kw', 'sum'), load_rows=('kw', 'size')).reset_index()

s = pd.read_csv(solar_csv)
s['load_key'] = 'CSE' + s['sin'].astype(str)
m = s.merge(g, left_on='load_key', right_on='SectionId', how='left', suffixes=('', '_load')).drop(columns='SectionId_load', errors='ignore')
m['load_matched'] = m.load_kw.notna()
m['solar_ratio'] = m.solar_kw / m.kva
m['load_ratio'] = m.load_kw / m.kva
m.to_csv(out_csv, index=False)

print('transformers:', len(m), '| load matched:', int(m.load_matched.sum()), '| unmatched:', int((~m.load_matched).sum()))
print('solar kW with load:', round(m[m.load_matched].solar_kw.sum(), 1), 'of', round(m.solar_kw.sum(), 1))
print(m.groupby('csc').load_matched.apply(lambda v: f'{v.sum()}/{len(v)}').to_string())
print('unique SIN keys:', m.groupby(['csc', 'sin']).ngroups, 'of', len(m))