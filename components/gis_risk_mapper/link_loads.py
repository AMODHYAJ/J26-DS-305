"""Join modelled network loads to transformer-level solar data.

Usage:
python link_loads.py solar_with_coords.csv Loads.xlsx solar_loads_matched.csv

Loads.SectionId is linked using 'CSE' + SIN.

The three phase kW values are summed to obtain total modelled
three-phase active load. These values are network-model loads,
not measured historical demand.
"""

import sys
import pandas as pd

solar_csv, loads_xlsx, out_csv = sys.argv[1:4]

clean = lambda s: (
    s.astype(str)
    .str.replace('\u200d', '', regex=False)
    .str.strip()
)

# ---------------------------------------------------------
# LOAD MODEL DATA
# ---------------------------------------------------------

loads = pd.read_excel(loads_xlsx)

loads['SectionId'] = clean(loads['SectionId'])

loads['model_load_kw'] = loads[
    ['Phase1Kw', 'Phase2Kw', 'Phase3Kw']
].sum(axis=1)

# Sum multiple model-load rows attached to the same section.
# Keep spot/distributed row counts for traceability.
grouped = (
    loads.groupby('SectionId')
    .agg(
        model_load_kw=('model_load_kw', 'sum'),
        load_rows=('model_load_kw', 'size'),
        spot_load_rows=('IsSpotLoad', 'sum')
    )
    .reset_index()
)

# ---------------------------------------------------------
# SOLAR TRANSFORMERS
# ---------------------------------------------------------

solar = pd.read_csv(solar_csv)

solar['load_key'] = (
        'CSE' + solar['sin'].astype(str)
)

matched = solar.merge(
    grouped,
    left_on='load_key',
    right_on='SectionId',
    how='left'
)

matched = matched.drop(
    columns=['SectionId'],
    errors='ignore'
)

matched['load_matched'] = (
    matched['model_load_kw'].notna()
)

# ---------------------------------------------------------
# FEATURES
# ---------------------------------------------------------

matched['solar_to_kva'] = (
        matched['solar_kw']
        / matched['kva']
)

matched['model_load_to_kva'] = (
        matched['model_load_kw']
        / matched['kva']
)

matched['solar_to_model_load'] = (
        matched['solar_kw']
        / matched['model_load_kw']
)

matched['solar_minus_model_load_kw'] = (
        matched['solar_kw']
        - matched['model_load_kw']
)

# ---------------------------------------------------------
# SAVE
# ---------------------------------------------------------

matched.to_csv(
    out_csv,
    index=False
)

matched_only = matched[
    matched['load_matched']
]

print(
    'transformers:',
    len(matched),
    '| load matched:',
    len(matched_only),
    '| unmatched:',
    int((~matched['load_matched']).sum())
)

print(
    'match rate:',
    round(
        len(matched_only)
        / len(matched)
        * 100,
        2
    ),
    '%'
)

print(
    '\nMatch coverage by CSC:'
)

print(
    matched.groupby('csc')['load_matched']
    .apply(
        lambda v: f'{int(v.sum())}/{len(v)}'
    )
    .to_string()
)