from pathlib import Path

import pandas as pd
import streamlit as st


# ---------------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------------

st.set_page_config(
    page_title="C3 Transformer Solar Exposure",
    layout="wide"
)


# ---------------------------------------------------------
# PATHS
# ---------------------------------------------------------

C3_DIR = Path(__file__).resolve().parent

DATA_FILE = (
        C3_DIR
        / "output"
        / "transformer_risk_ui.csv"
)


# ---------------------------------------------------------
# LOAD DATA
# ---------------------------------------------------------

@st.cache_data
def load_data():
    return pd.read_csv(DATA_FILE)


df = load_data()


# ---------------------------------------------------------
# TITLE
# ---------------------------------------------------------

st.title("Transformer Solar Exposure Assessment")

st.caption(
    "C3 — Predictive GIS-Based Grid Risk Assessment "
    "for Distributed Rooftop Solar"
)


# ---------------------------------------------------------
# SUMMARY METRICS
# ---------------------------------------------------------

primary_count = (
    df["assessment_method"]
    .eq("Load-adjusted exposure")
    .sum()
)

fallback_count = (
    df["assessment_method"]
    .eq("Solar-only fallback")
    .sum()
)

coord_count = (
    df["latitude"]
    .notna()
    .sum()
)


col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Transformers",
    len(df)
)

col2.metric(
    "Load-adjusted",
    int(primary_count)
)

col3.metric(
    "Fallback",
    int(fallback_count)
)

col4.metric(
    "Mapped",
    int(coord_count)
)


# ---------------------------------------------------------
# FILTERS
# ---------------------------------------------------------

st.subheader("Filters")

filter_col1, filter_col2, filter_col3 = st.columns(3)


csc_options = [
                  "All"
              ] + sorted(
    df["csc"]
    .dropna()
    .unique()
    .tolist()
)

selected_csc = filter_col1.selectbox(
    "CSC",
    csc_options
)


filtered = df.copy()

if selected_csc != "All":
    filtered = filtered[
        filtered["csc"]
        == selected_csc
        ]


feeder_options = [
                     "All"
                 ] + sorted(
    filtered["feeder"]
    .dropna()
    .unique()
    .tolist()
)

selected_feeder = filter_col2.selectbox(
    "Feeder",
    feeder_options
)

if selected_feeder != "All":
    filtered = filtered[
        filtered["feeder"]
        == selected_feeder
        ]


status_options = [
                     "All"
                 ] + sorted(
    filtered["scenario_status"]
    .dropna()
    .unique()
    .tolist()
)

selected_status = filter_col3.selectbox(
    "Scenario status",
    status_options
)

if selected_status != "All":
    filtered = filtered[
        filtered["scenario_status"]
        == selected_status
        ]


# ---------------------------------------------------------
# MAIN LAYOUT
# ---------------------------------------------------------

map_col, detail_col = st.columns(
    [2, 1]
)


# ---------------------------------------------------------
# MAP
# ---------------------------------------------------------

with map_col:

    st.subheader(
        "Available Transformer Locations"
    )

    map_df = filtered[
        filtered["latitude"].notna()
        & filtered["longitude"].notna()
        ].copy()

    if len(map_df) > 0:

        st.map(
            map_df,
            latitude="latitude",
            longitude="longitude"
        )

        st.caption(
            f"{len(map_df)} transformer locations "
            "available for the current selection."
        )

    else:

        st.info(
            "No transformer coordinates are available "
            "for the current filter selection."
        )


# ---------------------------------------------------------
# SELECT TRANSFORMER
# ---------------------------------------------------------

with detail_col:

    st.subheader(
        "Transformer Details"
    )

    transformer_options = (
        filtered["sin"]
        .dropna()
        .astype(str)
        .tolist()
    )

    if transformer_options:

        selected_sin = st.selectbox(
            "Select transformer",
            transformer_options
        )

        selected = filtered[
            filtered["sin"]
            .astype(str)
            == selected_sin
            ].iloc[0]


        st.metric(
            "Priority rank",
            (
                int(selected["priority_rank"])
                if pd.notna(
                    selected["priority_rank"]
                )
                else "Fallback"
            )
        )


        st.write(
            "**CSC:**",
            selected["csc"]
        )

        st.write(
            "**Feeder:**",
            selected["feeder"]
        )

        st.write(
            "**Section:**",
            selected["section"]
        )

        st.write(
            "**Transformer rating:**",
            f"{selected['kva']:.0f} kVA"
        )

        st.write(
            "**Connected solar:**",
            f"{selected['solar_kw']:.2f} kW"
        )


        if pd.notna(
                selected["model_load_kw"]
        ):

            st.write(
                "**Modelled load:**",
                f"{selected['model_load_kw']:.2f} kW"
            )


        if pd.notna(
                selected["exposure_score"]
        ):

            st.write(
                "**Exposure score:**",
                f"{selected['exposure_score']:.3f}"
            )

        else:

            st.write(
                "**Solar / kVA fallback:**",
                f"{selected['fallback_indicator']:.3f}"
            )


        st.write(
            "**Scenario status:**",
            selected["scenario_status"]
        )

        st.write(
            "**Assessment method:**",
            selected["assessment_method"]
        )

        st.write(
            "**Data status:**",
            selected["data_confidence"]
        )


        with st.expander(
                "Why was this transformer prioritised?"
        ):

            st.write(
                selected[
                    "assessment_explanation"
                ]
            )

    else:

        st.info(
            "No transformers match the "
            "current filters."
        )


# ---------------------------------------------------------
# RANKED TABLE
# ---------------------------------------------------------

st.subheader(
    "Transformer Priority List"
)


table_columns = [
    "priority_rank",
    "sin",
    "csc",
    "feeder",
    "kva",
    "solar_kw",
    "model_load_kw",
    "exposure_score",
    "scenario_status",
    "assessment_method"
]


table_df = filtered[
    table_columns
].copy()


table_df = table_df.rename(
    columns={
        "priority_rank": "Rank",
        "sin": "Transformer",
        "csc": "CSC",
        "feeder": "Feeder",
        "kva": "Rating (kVA)",
        "solar_kw": "Solar (kW)",
        "model_load_kw": "Modelled Load (kW)",
        "exposure_score": "Exposure Score",
        "scenario_status": "Scenario Status",
        "assessment_method": "Assessment Method"
    }
)


st.dataframe(
    table_df,
    use_container_width=True,
    hide_index=True
)


# ---------------------------------------------------------
# METHOD NOTE
# ---------------------------------------------------------

with st.expander(
        "Assessment methodology and limitations"
):

    st.markdown(
        """
        **Current provisional exposure score**

        `(0.95 × connected solar kW - modelled load kW) / transformer kVA`

        The score is used as a first-level screening and
        prioritisation indicator.

        The current load values are CEB network-model loads,
        not measured historical transformer demand.

        Transformers without usable modelled load are kept as
        solar-only fallback records and are not mixed into the
        primary load-adjusted ranking.

        The assessment does not represent a full AC power-flow
        study or confirmed measured reverse power flow.
        """
    )