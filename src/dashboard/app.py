"""
Streamlit dashboard for US salary analytics.
Run: streamlit run src/dashboard/app.py
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

PROCESSED_DIR = Path("data/processed")

# ── Label maps ────────────────────────────────────────────────────────────────

RACE_EARN_COLS = {
    "White (Non-Hispanic)": "median_earn_white_nh",
    "White (All)": "median_earn_white",
    "Black": "median_earn_black",
    "Asian": "median_earn_asian",
    "Hispanic": "median_earn_hispanic",
}

RACE_HHI_COLS = {
    "White (Non-Hispanic)": "median_hhi_white_nh",
    "White": "median_hhi_white",
    "Black": "median_hhi_black",
    "Asian": "median_hhi_asian",
    "Hispanic": "median_hhi_hispanic",
    "American Indian / Alaska Native": "median_hhi_aian",
}

FAMILY_SIZE_COLS = {
    "2 People":  "median_faminc_2person",
    "3 People":  "median_faminc_3person",
    "4 People":  "median_faminc_4person",
    "5 People":  "median_faminc_5person",
    "6 People":  "median_faminc_6person",
    "7+ People": "median_faminc_7plus",
}

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="US Salary Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Data loaders ──────────────────────────────────────────────────────────────

@st.cache_data
def load_census() -> pd.DataFrame | None:
    p = PROCESSED_DIR / "census_clean.parquet"
    return pd.read_parquet(p) if p.exists() else None




# ── Helpers ───────────────────────────────────────────────────────────────────

def dollar(val) -> str:
    return f"${val:,.0f}" if pd.notna(val) else "N/A"


def melt_cols(df: pd.DataFrame, col_map: dict, label_col: str, value_col: str, extra_cols: list | None = None) -> pd.DataFrame:
    """Melt a set of columns into a long-form DataFrame."""
    frames = []
    extra_cols = extra_cols or []
    for label, base_col in col_map.items():
        col = base_col  # suffix appended by caller
        if col in df.columns:
            sub = df[extra_cols + [col]].copy()
            sub[label_col] = label
            sub = sub.rename(columns={col: value_col})
            frames.append(sub)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    st.title("📊 US Salary Analytics")
    st.caption(
        "Data: **US Census Bureau ACS 1-Year Estimates** (2010–2023) · "
        "**Bureau of Labor Statistics OEWS** (2013–2023) · "
        "Inflation adjustment uses BLS CPI-U."
    )

    census = load_census()

    if census is None:
        st.error("No processed data found. Pull the data first:")
        st.code("python main.py", language="bash")
        st.stop()

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("Filters")

        all_years = sorted(census["year"].unique().tolist()) if census is not None else list(range(2013, 2024))
        year_range = st.select_slider(
            "Year range",
            options=all_years,
            value=(min(all_years), max(all_years)),
        )
        adjust = st.checkbox("Inflation-adjust to 2023 $", value=True)
        suffix = "_real" if adjust else ""
        dollar_label = "2023 $" if adjust else "Nominal $"

        st.divider()
        if census is not None:
            n_metros = census[census["geography"] == "Metro"]["geo_id"].nunique()
            st.caption(f"{n_metros} metro areas · {len(all_years)} years")

    # ── Filter helpers ────────────────────────────────────────────────────────
    def in_range(df: pd.DataFrame) -> pd.DataFrame:
        return df[(df["year"] >= year_range[0]) & (df["year"] <= year_range[1])]

    national = pd.DataFrame()
    metros = pd.DataFrame()
    if census is not None:
        c = in_range(census)
        national = c[c["geography"] == "National"].sort_values("year")
        metros   = c[c["geography"] == "Metro"]

    # ── Tabs ──────────────────────────────────────────────────────────────────
    t_overview, t_gender, t_race, t_family, t_industry, t_occ, t_metro = st.tabs([
        "Overview", "Gender Gap", "Race & Ethnicity", "Family Size", "By Industry", "By Occupation", "Metro Areas"
    ])

    # ─────────────────────────────────────────────────────────────────────────
    # TAB 1 — Overview
    # ─────────────────────────────────────────────────────────────────────────
    with t_overview:
        if national.empty:
            st.info("No national data available.")
        else:
            latest_yr = national["year"].max()
            row = national[national["year"] == latest_yr].iloc[0]

            st.subheader(f"National Snapshot — {latest_yr}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Median Earnings (All)", dollar(row.get(f"median_earnings_total{suffix}")))
            c2.metric("Median Earnings (Men)", dollar(row.get(f"median_earnings_male{suffix}")))
            c3.metric("Median Earnings (Women)", dollar(row.get(f"median_earnings_female{suffix}")))
            c4.metric("Median Household Income", dollar(row.get(f"median_hhi{suffix}")))

            st.divider()
            st.subheader("Earnings Trend")

            earn_cols = {
                f"median_earnings_total{suffix}": "All Workers",
                f"median_earnings_male{suffix}": "Men",
                f"median_earnings_female{suffix}": "Women",
            }
            available = {col: lbl for col, lbl in earn_cols.items() if col in national.columns}
            if available:
                trend_df = national[["year"] + list(available)].melt(
                    id_vars="year", var_name="_col", value_name="Median Earnings"
                )
                trend_df["Group"] = trend_df["_col"].map(available)
                fig = px.line(
                    trend_df.dropna(subset=["Median Earnings"]),
                    x="year", y="Median Earnings", color="Group",
                    markers=True,
                    labels={"year": "Year", "Median Earnings": dollar_label},
                )
                fig.update_layout(yaxis_tickformat="$,.0f", hovermode="x unified")
                st.plotly_chart(fig, width='stretch')

            hhi_col = f"median_hhi{suffix}"
            if hhi_col in national.columns:
                fig2 = px.area(
                    national[["year", hhi_col]].dropna(),
                    x="year", y=hhi_col,
                    labels={"year": "Year", hhi_col: dollar_label},
                    title="Median Household Income Over Time",
                )
                fig2.update_layout(yaxis_tickformat="$,.0f")
                st.plotly_chart(fig2, width='stretch')

    # ─────────────────────────────────────────────────────────────────────────
    # TAB 2 — Gender Gap
    # ─────────────────────────────────────────────────────────────────────────
    with t_gender:
        if national.empty:
            st.info("No national data available.")
        else:
            st.subheader("Gender Wage Gap Over Time")

            m_col  = f"median_earnings_male{suffix}"
            f_col  = f"median_earnings_female{suffix}"
            m_ft   = f"median_ftyr_male{suffix}"
            f_ft   = f"median_ftyr_female{suffix}"

            gap = national[["year", m_col, f_col, m_ft, f_ft]].copy()
            gap["gap_pct"]     = (gap[m_col] - gap[f_col]) / gap[m_col] * 100
            gap["gap_pct_ft"]  = (gap[m_ft]  - gap[f_ft])  / gap[m_ft]  * 100
            gap["women_of_men"]= gap[f_col] / gap[m_col] * 100

            col1, col2 = st.columns(2)
            with col1:
                fig = px.line(
                    gap.dropna(subset=["gap_pct"]),
                    x="year", y="gap_pct", markers=True,
                    title="Gender Pay Gap — All Workers",
                    labels={"year": "Year", "gap_pct": "Gap (% of men's earnings)"},
                )
                fig.update_layout(yaxis_ticksuffix="%")
                st.plotly_chart(fig, width='stretch')

            with col2:
                bar_df = gap[["year", m_col, f_col]].melt(
                    id_vars="year", var_name="Gender", value_name="Earnings"
                ).dropna()
                bar_df["Gender"] = bar_df["Gender"].map({m_col: "Men", f_col: "Women"})
                fig2 = px.bar(
                    bar_df, x="year", y="Earnings", color="Gender", barmode="group",
                    title="Median Earnings by Gender",
                    labels={"year": "Year", "Earnings": dollar_label},
                )
                fig2.update_layout(yaxis_tickformat="$,.0f")
                st.plotly_chart(fig2, width='stretch')

            st.subheader("Full-Time, Year-Round Workers Only")
            st.caption(
                "Comparing full-time/year-round workers controls for part-time work and time out of the workforce, "
                "giving a cleaner measure of the pay gap within comparable work schedules."
            )
            ft_df = gap[["year", m_ft, f_ft]].melt(
                id_vars="year", var_name="Gender", value_name="Earnings"
            ).dropna()
            ft_df["Gender"] = ft_df["Gender"].map({m_ft: "Men (FT/YR)", f_ft: "Women (FT/YR)"})
            fig3 = px.line(
                ft_df, x="year", y="Earnings", color="Gender", markers=True,
                title="Median Earnings — Full-Time, Year-Round Workers",
                labels={"year": "Year", "Earnings": dollar_label},
            )
            fig3.update_layout(yaxis_tickformat="$,.0f", hovermode="x unified")
            st.plotly_chart(fig3, width='stretch')

            if "gap_pct_ft" in gap.columns:
                fig4 = px.line(
                    gap.dropna(subset=["gap_pct_ft"]),
                    x="year", y="gap_pct_ft", markers=True,
                    title="Gender Pay Gap — Full-Time, Year-Round Workers",
                    labels={"year": "Year", "gap_pct_ft": "Gap (% of men's earnings)"},
                )
                fig4.update_layout(yaxis_ticksuffix="%")
                st.plotly_chart(fig4, width='stretch')

    # ─────────────────────────────────────────────────────────────────────────
    # TAB 3 — Race & Ethnicity
    # ─────────────────────────────────────────────────────────────────────────
    with t_race:
        if national.empty:
            st.info("No national data available.")
        else:
            st.subheader("Median Earnings by Race / Ethnicity")

            earn_map = {lbl: f"{col}{suffix}" for lbl, col in RACE_EARN_COLS.items()}
            earn_trend = melt_cols(national, earn_map, "Race/Ethnicity", "Median Earnings", ["year"])

            if not earn_trend.empty:
                earn_trend = earn_trend.dropna(subset=["Median Earnings"])
                fig = px.line(
                    earn_trend, x="year", y="Median Earnings", color="Race/Ethnicity",
                    markers=True,
                    labels={"year": "Year", "Median Earnings": dollar_label},
                    title="Median Earnings Trend by Race/Ethnicity",
                )
                fig.update_layout(yaxis_tickformat="$,.0f", hovermode="x unified")
                st.plotly_chart(fig, width='stretch')

                latest_race = earn_trend[earn_trend["year"] == earn_trend["year"].max()].sort_values("Median Earnings")
                fig2 = px.bar(
                    latest_race, x="Median Earnings", y="Race/Ethnicity", orientation="h",
                    text_auto=",.0f",
                    title=f"Median Earnings by Race/Ethnicity — {earn_trend['year'].max()}",
                )
                fig2.update_traces(texttemplate="$%{x:,.0f}", textposition="outside")
                fig2.update_layout(xaxis_tickformat="$,.0f")
                st.plotly_chart(fig2, width='stretch')

            st.divider()
            st.subheader("Median Household Income by Race / Ethnicity")

            hhi_map = {lbl: f"{col}{suffix}" for lbl, col in RACE_HHI_COLS.items()}
            hhi_trend = melt_cols(national, hhi_map, "Race/Ethnicity", "Median HH Income", ["year"])

            if not hhi_trend.empty:
                hhi_trend = hhi_trend.dropna(subset=["Median HH Income"])
                fig3 = px.line(
                    hhi_trend, x="year", y="Median HH Income", color="Race/Ethnicity",
                    markers=True,
                    labels={"year": "Year", "Median HH Income": dollar_label},
                    title="Median Household Income Trend by Race/Ethnicity",
                )
                fig3.update_layout(yaxis_tickformat="$,.0f", hovermode="x unified")
                st.plotly_chart(fig3, width='stretch')

    # ─────────────────────────────────────────────────────────────────────────
    # TAB 4 — Family Size
    # ─────────────────────────────────────────────────────────────────────────
    with t_family:
        if national.empty:
            st.info("No national data available.")
        else:
            st.subheader("Median Family Income by Family Size")

            fam_map = {lbl: f"{col}{suffix}" for lbl, col in FAMILY_SIZE_COLS.items()}
            fam_trend = melt_cols(national, fam_map, "Family Size", "Median Family Income", ["year"])

            if not fam_trend.empty:
                fam_trend = fam_trend.dropna(subset=["Median Family Income"])
                size_order = list(FAMILY_SIZE_COLS.keys())
                fam_trend["Family Size"] = pd.Categorical(fam_trend["Family Size"], categories=size_order, ordered=True)

                col1, col2 = st.columns(2)
                with col1:
                    latest_yr = fam_trend["year"].max()
                    snapshot = fam_trend[fam_trend["year"] == latest_yr].sort_values("Family Size")
                    fig = px.bar(
                        snapshot, x="Family Size", y="Median Family Income",
                        text_auto="$,.0f",
                        color="Median Family Income", color_continuous_scale="Blues",
                        title=f"Family Income by Size — {latest_yr}",
                        labels={"Median Family Income": dollar_label},
                    )
                    fig.update_layout(yaxis_tickformat="$,.0f", coloraxis_showscale=False)
                    st.plotly_chart(fig, width='stretch')

                with col2:
                    fig2 = px.line(
                        fam_trend, x="year", y="Median Family Income", color="Family Size",
                        markers=True,
                        category_orders={"Family Size": size_order},
                        title="Trend by Family Size",
                        labels={"year": "Year", "Median Family Income": dollar_label},
                    )
                    fig2.update_layout(yaxis_tickformat="$,.0f")
                    st.plotly_chart(fig2, width='stretch')

    # ─────────────────────────────────────────────────────────────────────────
    # TAB 5 — By Industry (Census ACS B24031/B24032)
    # ─────────────────────────────────────────────────────────────────────────
    with t_industry:
        st.subheader("Median Earnings by Industry")
        st.caption("Source: Census ACS B24031/B24032 — civilian employed population 16+")

        IND_LABELS = {
            "ind_earn_professional_sci_tech":  "Professional, Scientific & Technical",
            "ind_earn_finance_insurance":      "Finance & Insurance",
            "ind_earn_information":            "Information",
            "ind_earn_manufacturing":          "Manufacturing",
            "ind_earn_construction":           "Construction",
            "ind_earn_transport_utilities":    "Transportation & Utilities",
            "ind_earn_wholesale":              "Wholesale Trade",
            "ind_earn_public_admin":           "Public Administration",
            "ind_earn_education":              "Educational Services",
            "ind_earn_healthcare":             "Healthcare & Social Assistance",
            "ind_earn_retail":                 "Retail Trade",
            "ind_earn_other_services":         "Other Services",
            "ind_earn_accommodation_food":     "Accommodation & Food Services",
            "ind_earn_arts_food":              "Arts, Entertainment & Recreation",
        }

        if national.empty:
            st.info("No national data available.")
        else:
            latest_yr = national["year"].max()
            snap = national[national["year"] == latest_yr].iloc[0]

            ind_rows = []
            for base_col, label in IND_LABELS.items():
                col = f"{base_col}{suffix}"
                male_col = f"{base_col.replace('ind_earn_', 'ind_earn_male_')}{suffix}"
                val = snap.get(col)
                male_val = snap.get(male_col)
                if pd.notna(val):
                    ind_rows.append({
                        "Industry": label,
                        "All Workers": val,
                        "Men": male_val if pd.notna(male_val) else None,
                    })

            if ind_rows:
                ind_df = pd.DataFrame(ind_rows).sort_values("All Workers")
                fig = px.bar(
                    ind_df, x="All Workers", y="Industry", orientation="h",
                    text_auto=",.0f",
                    title=f"Median Earnings by Industry — {latest_yr}",
                    color="All Workers", color_continuous_scale="Viridis",
                    height=550,
                    labels={"All Workers": dollar_label},
                )
                fig.update_traces(texttemplate="$%{x:,.0f}", textposition="outside")
                fig.update_layout(xaxis_tickformat="$,.0f", coloraxis_showscale=False)
                st.plotly_chart(fig, width='stretch')

                # Male vs All gap by industry
                st.subheader("Men's Earnings vs. All Workers by Industry")
                gap_df = ind_df.dropna(subset=["Men"]).copy()
                gap_df["Gap (Men − All)"] = gap_df["Men"] - gap_df["All Workers"]
                melt_ind = gap_df[["Industry", "All Workers", "Men"]].melt(
                    id_vars="Industry", var_name="Group", value_name="Earnings"
                )
                fig2 = px.bar(
                    melt_ind.sort_values("Earnings", ascending=False),
                    x="Industry", y="Earnings", color="Group", barmode="group",
                    title=f"All Workers vs. Men by Industry — {latest_yr}",
                    labels={"Earnings": dollar_label},
                )
                fig2.update_layout(yaxis_tickformat="$,.0f", xaxis_tickangle=-30)
                st.plotly_chart(fig2, width='stretch')

            # Industry trend over time
            st.subheader("Industry Earnings Trends Over Time")
            trend_ind_labels = {
                "Professional, Scientific & Technical": "ind_earn_professional_sci_tech",
                "Finance & Insurance":                  "ind_earn_finance_insurance",
                "Information":                          "ind_earn_information",
                "Healthcare":                           "ind_earn_healthcare",
                "Retail Trade":                         "ind_earn_retail",
                "Accommodation & Food":                 "ind_earn_accommodation_food",
            }
            industry_options = list(trend_ind_labels.keys())
            selected_ind = st.multiselect("Industries to compare", options=industry_options,
                                          default=industry_options[:4])
            if selected_ind:
                trend_frames = []
                for lbl in selected_ind:
                    base = trend_ind_labels[lbl]
                    col = f"{base}{suffix}"
                    if col in national.columns:
                        sub = national[["year", col]].copy()
                        sub["Industry"] = lbl
                        sub = sub.rename(columns={col: "Median Earnings"})
                        trend_frames.append(sub)
                if trend_frames:
                    tdf = pd.concat(trend_frames).dropna(subset=["Median Earnings"])
                    fig3 = px.line(tdf, x="year", y="Median Earnings", color="Industry", markers=True,
                                   title="Industry Earnings Over Time",
                                   labels={"year": "Year", "Median Earnings": dollar_label})
                    fig3.update_layout(yaxis_tickformat="$,.0f", hovermode="x unified")
                    st.plotly_chart(fig3, width='stretch')

    # ─────────────────────────────────────────────────────────────────────────
    # TAB 6 — By Occupation (Census ACS B24011/B24021)
    # ─────────────────────────────────────────────────────────────────────────
    with t_occ:
        st.subheader("Median Earnings by Occupation Group")
        st.caption("Source: Census ACS B24011 (all), B24021 (male) — civilian employed population 16+")

        OCC_LABELS = {
            "occ_earn_mgmt_sci_arts":          "Management, Business, Science & Arts",
            "occ_earn_mgmt_biz_fin":           "↳ Management, Business & Finance",
            "occ_earn_computer_eng_sci":       "↳ Computer, Engineering & Science",
            "occ_earn_edu_legal_arts":         "↳ Education, Legal, Community & Arts",
            "occ_earn_healthcare_pract":       "↳ Healthcare Practitioners",
            "occ_earn_service":                "Service Occupations",
            "occ_earn_sales_office":           "Sales & Office",
            "occ_earn_construction":           "Natural Resources, Construction & Maintenance",
            "occ_earn_production_transport":   "Production, Transportation & Material Moving",
        }

        if national.empty:
            st.info("No national data available.")
        else:
            latest_yr = national["year"].max()
            snap = national[national["year"] == latest_yr].iloc[0]

            # Build snapshot bar chart
            occ_rows = []
            for base_col, label in OCC_LABELS.items():
                col = f"{base_col}{suffix}"
                if col in national.columns:
                    val = snap.get(col)
                    if pd.notna(val):
                        occ_rows.append({"Occupation Group": label, "Median Earnings": val})

            if occ_rows:
                occ_df = pd.DataFrame(occ_rows).sort_values("Median Earnings")
                fig = px.bar(
                    occ_df, x="Median Earnings", y="Occupation Group", orientation="h",
                    text_auto=",.0f",
                    title=f"Median Earnings by Occupation Group — {latest_yr}",
                    color="Median Earnings", color_continuous_scale="Blues",
                    height=500,
                )
                fig.update_traces(texttemplate="$%{x:,.0f}", textposition="outside")
                fig.update_layout(xaxis_tickformat="$,.0f", coloraxis_showscale=False)
                st.plotly_chart(fig, width='stretch')

            # Gender gap by occupation
            st.subheader("Gender Gap Within Occupation Groups")
            GENDER_OCC = {
                "Management, Business, Science & Arts": ("occ_earn_male_mgmt_sci_arts", "occ_earn_female_mgmt_sci_arts"),
                "Service": ("occ_earn_male_service", "occ_earn_female_service"),
                "Sales & Office": ("occ_earn_male_sales_office", "occ_earn_female_sales_office"),
                "Construction & Maintenance": ("occ_earn_male_construction", "occ_earn_female_construction"),
                "Production & Transport": ("occ_earn_male_production_transport", "occ_earn_female_production_transport"),
            }
            gender_rows = []
            for label, (m_base, f_base) in GENDER_OCC.items():
                m_col, f_col = f"{m_base}{suffix}", f"{f_base}{suffix}"
                m_val = snap.get(m_col)
                f_val = snap.get(f_col)
                if pd.notna(m_val) and pd.notna(f_val):
                    gender_rows.append({"Occupation": label, "Men": m_val, "Women": f_val,
                                        "Gap %": round((m_val - f_val) / m_val * 100, 1)})
            if gender_rows:
                gdf = pd.DataFrame(gender_rows)
                melt = gdf[["Occupation", "Men", "Women"]].melt(id_vars="Occupation", var_name="Gender", value_name="Earnings")
                fig2 = px.bar(
                    melt, x="Occupation", y="Earnings", color="Gender", barmode="group",
                    title=f"Earnings by Gender and Occupation Group — {latest_yr}",
                    labels={"Earnings": dollar_label},
                )
                fig2.update_layout(yaxis_tickformat="$,.0f")
                st.plotly_chart(fig2, width='stretch')

                st.dataframe(
                    gdf.rename(columns={"Gap %": "Gender Pay Gap (%)"})
                    .style.format({"Men": "${:,.0f}", "Women": "${:,.0f}", "Gender Pay Gap (%)": "{:.1f}%"}),
                    width='stretch',
                )

            # Trend for major occupation groups
            st.subheader("Occupation Earnings Trends Over Time")
            TREND_OCC = {
                "Mgmt, Business, Science & Arts": "occ_earn_mgmt_sci_arts",
                "Service": "occ_earn_service",
                "Sales & Office": "occ_earn_sales_office",
                "Construction & Maintenance": "occ_earn_construction",
                "Production & Transport": "occ_earn_production_transport",
            }
            trend_frames = []
            for label, base_col in TREND_OCC.items():
                col = f"{base_col}{suffix}"
                if col in national.columns:
                    sub = national[["year", col]].copy()
                    sub["Occupation"] = label
                    sub = sub.rename(columns={col: "Median Earnings"})
                    trend_frames.append(sub)
            if trend_frames:
                trend_df = pd.concat(trend_frames).dropna(subset=["Median Earnings"])
                fig3 = px.line(
                    trend_df, x="year", y="Median Earnings", color="Occupation", markers=True,
                    title="Occupation Group Earnings Over Time",
                    labels={"year": "Year", "Median Earnings": dollar_label},
                )
                fig3.update_layout(yaxis_tickformat="$,.0f", hovermode="x unified")
                st.plotly_chart(fig3, width='stretch')

    # ─────────────────────────────────────────────────────────────────────────
    # TAB 6 — Metro Areas
    # ─────────────────────────────────────────────────────────────────────────
    with t_metro:
        if metros.empty:
            st.warning("Metro data not loaded. Run `python main.py`.")
        else:
            st.subheader("Salary Analytics by Metropolitan Area")

            earn_col = f"median_earnings_total{suffix}"
            hhi_col  = f"median_hhi{suffix}"

            latest_metro_yr = metros["year"].max()
            latest_m = metros[metros["year"] == latest_metro_yr].copy()
            latest_m = latest_m[latest_m[earn_col].notna()].sort_values(earn_col, ascending=False)

            search = st.text_input("Search metro area", placeholder="e.g. New York, Austin, Seattle")
            if search:
                latest_m = latest_m[latest_m["metro_name"].str.contains(search, case=False, na=False)]

            col1, col2 = st.columns([3, 2])
            with col1:
                top_n = min(30, len(latest_m))
                fig = px.bar(
                    latest_m.head(top_n).sort_values(earn_col),
                    x=earn_col, y="metro_name", orientation="h",
                    title=f"Top {top_n} Metro Areas by Median Earnings — {latest_metro_yr}",
                    labels={earn_col: dollar_label, "metro_name": "Metro"},
                    height=max(450, top_n * 24),
                )
                fig.update_layout(xaxis_tickformat="$,.0f")
                st.plotly_chart(fig, width='stretch')

            with col2:
                display_df = latest_m[
                    [c for c in ["metro_name", earn_col, hhi_col, "total_population"] if c in latest_m.columns]
                ].rename(columns={
                    "metro_name": "Metro", earn_col: "Median Earnings",
                    hhi_col: "Median HH Income", "total_population": "Population",
                })
                st.dataframe(
                    display_df.style.format({
                        "Median Earnings": "${:,.0f}",
                        "Median HH Income": "${:,.0f}",
                        "Population": "{:,.0f}",
                    }),
                    height=500,
                    width='stretch',
                )

            st.subheader("Compare Metro Areas Over Time")
            metro_options = sorted(metros["metro_name"].dropna().unique())
            default_metros = metro_options[:3] if len(metro_options) >= 3 else metro_options
            selected_metros = st.multiselect("Select metros", options=metro_options, default=default_metros)

            if selected_metros:
                trend_m = metros[metros["metro_name"].isin(selected_metros)][["year", "metro_name", earn_col]].dropna()
                fig2 = px.line(
                    trend_m, x="year", y=earn_col, color="metro_name", markers=True,
                    labels={"year": "Year", earn_col: dollar_label, "metro_name": "Metro"},
                    title="Median Earnings Trend — Selected Metro Areas",
                )
                fig2.update_layout(yaxis_tickformat="$,.0f", hovermode="x unified")
                st.plotly_chart(fig2, width='stretch')


if __name__ == "__main__":
    main()
