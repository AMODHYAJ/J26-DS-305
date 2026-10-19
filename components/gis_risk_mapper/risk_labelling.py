"""C3 weak-supervision risk labels per transformer.
Usage: python risk_labelling.py solar_with_coords.csv risk_labels.csv
Thresholds are config constants: replace with your literature-cited values."""
import sys, pandas as pd, numpy as np

# ---- config (edit to match cited literature) ----
RATIO_MED, RATIO_HIGH = 0.5, 1.0      # solar kW / transformer kVA
EXPORT_MED, EXPORT_HIGH = 0.4, 0.7    # share of kW under export-type schemes (Net Plus, Net Plus Plus)
KW_PER_KVA_SMALL = 100                # small transformers (<=100 kVA)
SMALL_HIGH = 0.8                      # ratio at which a small transformer is escalated to High
EXPORT_SCHEMES = ['Net Plus', 'Net Plus Plus']
LOW, MED, HIGH, ABST = 0, 1, 2, -1

def features(d):
    d = d.copy()
    d['solar_to_kva'] = d.solar_kw / d.kva
    d['export_share'] = d[EXPORT_SCHEMES].sum(axis=1) / d.solar_kw
    d['kw_per_account'] = d.solar_kw / d.n_accounts
    d['small_xfmr'] = (d.kva <= KW_PER_KVA_SMALL).astype(int)
    return d

# ---- labelling functions: each returns LOW/MED/HIGH or ABST ----
def lf_ratio(r):
    return HIGH if r.solar_to_kva >= RATIO_HIGH else MED if r.solar_to_kva >= RATIO_MED else LOW
def lf_export(r):
    return HIGH if r.export_share >= EXPORT_HIGH else MED if r.export_share >= EXPORT_MED else LOW
def lf_small_heavy(r):  # votes only when a small transformer is already loaded >= 0.5
    return HIGH if (r.small_xfmr and r.solar_to_kva >= SMALL_HIGH) else ABST
LFS = [lf_ratio, lf_small_heavy]   # lf_export disabled: assumes Net Plus/Plus Plus are export-type (unconfirmed)

def weak_label(d):
    V = np.array([[lf(r) for lf in LFS] for r in d.itertuples()])
    def agg(row):
        v = row[row != ABST]
        if len(v) == 0: return ABST
        c = np.bincount(v, minlength=3)
        return int(2 - np.argmax(c[::-1]))   # majority vote; ties go to the higher risk class
    d['label_num'] = [agg(r) for r in V]
    d['risk_label'] = d.label_num.map({LOW:'Low', MED:'Medium', HIGH:'High'})
    d['lf_votes'] = [','.join(map(str, r)) for r in V]
    d['lf_agreement'] = [(r[r != ABST] == int(np.bincount(r[r != ABST]).argmax())).mean() for r in V]
    return d

if __name__ == '__main__':
    src, out = sys.argv[1], sys.argv[2]
    d = weak_label(features(pd.read_csv(src)))
    d.to_csv(out, index=False)
    print('transformers:', len(d))
    print(d.risk_label.value_counts().reindex(['Low','Medium','High']).to_string())
    print(d.groupby('csc').risk_label.value_counts().unstack(fill_value=0).to_string())
    print('mean LF agreement: %.2f' % d.lf_agreement.mean())