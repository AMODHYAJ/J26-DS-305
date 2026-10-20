"""C3 - Link each transformer (SIN) to its node coordinate from Gnodes.xlsx.

Gnodes SectionId pattern: 'CSE' (Embilipitiya) + SIN code, e.g. CSER009 -> SIN R009.
Per supervisor: the first row (SequenceNumber 0) of a node is the transformer
coordinate; later rows are geographic bends and are ignored.
X/Y are Kandawala grid metres.
"""
import sys
import pandas as pd


def load_nodes(gnodes_xlsx):
    g = pd.read_excel(gnodes_xlsx)
    g["SectionId"] = g["SectionId"].astype(str).str.strip()
    m = g["SectionId"].str.extract(r"^CSE([A-Z])(\d{3})$")
    g["sin"] = m[0] + m[1]
    g = g.dropna(subset=["sin"])
    first = g[g["SequenceNumber"] == 0].drop_duplicates("sin")
    return first[["sin", "SectionId", "X", "Y"]].rename(columns={"X": "x_kandawala", "Y": "y_kandawala"})


def main(solar_csv, gnodes_xlsx, out_csv):
    solar = pd.read_csv(solar_csv)
    nodes = load_nodes(gnodes_xlsx)
    out = solar.merge(nodes, on="sin", how="left")
    out["has_coord"] = out["x_kandawala"].notna()
    out.to_csv(out_csv, index=False)
    print(f"transformers: {len(out)} | with coordinates: {out.has_coord.sum()} | missing: {(~out.has_coord).sum()}")
    print(out.groupby("csc").has_coord.agg(["sum", "count"]).rename(columns={"sum": "matched", "count": "total"}))
    miss = out[~out.has_coord]
    print(f"missing solar kW: {miss.solar_kw.sum():.1f} of {out.solar_kw.sum():.1f}")


if __name__ == "__main__":
    main(*sys.argv[1:4])