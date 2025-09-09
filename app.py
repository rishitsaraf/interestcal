import io
import numpy as np
import pandas as pd
import streamlit as st
import os

# ---- App chrome ----
pd.set_option("display.float_format", "{:.2f}".format)
st.set_page_config(page_title="Interest Calculator", layout="centered")

# Fix cursor styling for selectbox and force light theme
st.markdown("""
<style>
.stSelectbox > div > div > select {
    cursor: pointer !important;
}
.stSelectbox > div > div > div {
    cursor: pointer !important;
}
</style>
""", unsafe_allow_html=True)

st.title("Interest Calculator")

# ---- Upload file ----
uploaded = st.file_uploader("Upload Excel")

# ---- Select bank and annual interest rate ----
col1, col2 = st.columns(2)
with col1:
    bank_choice = st.selectbox("Select bank format / logic", ["Axis Bank", "Standard Chartered", "HDFC Bank"])

with col2:
    annual_interest_rate_input = st.number_input(
        "Annual interest rate (%)", min_value=0.0, max_value=100.0,
        value=8.0, step=0.1, format="%.2f"
    )
run_btn = st.button("Run", use_container_width=True)

def calc_axis(annual_interest_rate_input):

    #Upload the file
    df = pd.read_excel(uploaded)

    # 1) Find the first non-NaN row in column 3 (index 2)
    header_row = df[df.iloc[:, 2].notna()].index[0]

    # 2) Set that row as header, drop rows up to that row, reset index
    df.columns = df.iloc[header_row]
    df = df.drop(index=range(header_row + 1))
    df = df.reset_index(drop=True)

    # 3) Drop columns where column name is NaN
    df = df.loc[:, df.columns.notna()] ##### error

    # 4) Normalize column names (lowercase, underscores, remove non-alnum)
    df.columns = (
        df.columns
          .astype(str)
          .str.strip()
          .str.lower()
          .str.replace(r"\s+", "_", regex=True)
          .str.replace(r"[^a-z0-9_]", "", regex=True)
    )

    # 5) Replace blanks with NaN; trim leading/trailing all-empty rows
    df = df.replace(r'^\s*$', np.nan, regex=True)
    row_has_data = df.notna().any(axis=1)

    if row_has_data.any():
        first_valid = row_has_data.idxmax()
        last_valid  = row_has_data[::-1].idxmax()
        df = df.loc[first_valid:last_valid].reset_index(drop=True)
    else:
        df = df.iloc[0:0].copy()

    # 6) Keep only the last row per date (date is first column), preserve order
    date_col = df.columns[0]
    mask = ~df[date_col].duplicated(keep='last')
    df_last_per_date = df[mask].copy()

    # 7) Convert balanceinr to numeric (coerce)
    if "balanceinr" in df_last_per_date.columns:
        df_last_per_date["balanceinr"] = pd.to_numeric(
            df_last_per_date["balanceinr"], errors="coerce"
        )
    else:
        st.error("Column 'balanceinr' not found after cleaning. Please check your sheet.")
        st.stop()

    # 8) Annual rate in absolute percent → fraction
    annual_interest_rate = annual_interest_rate_input

    df_last_per_date["tran_date"] = pd.to_datetime(df_last_per_date["tran_date"],format="%d-%m-%Y")
    df_last_per_date["day"] = df_last_per_date["tran_date"].dt.day_name()
    # Calculate difference in days with next row
    df_last_per_date["day_diff"] = (
        df_last_per_date["tran_date"].shift(-1) - df_last_per_date["tran_date"]
    ).dt.days
    df_last_per_date["day_diff"] = df_last_per_date["day_diff"].fillna(1)



    # 9) Daily interest only if balance is negative; else 0
    df_last_per_date["daily_interest"] = np.where(
        df_last_per_date["balanceinr"] < 0,
        df_last_per_date["balanceinr"] * -1 *(annual_interest_rate / 365) * df_last_per_date["day_diff"],
        0
    )

    # 10) Sum interest
    total_interest = df_last_per_date["daily_interest"].sum()

    # ---- UI Output ----
    export_df = df_last_per_date[[date_col, "balanceinr", "daily_interest"]].copy()
    # Add summary row
    total_interest = export_df["daily_interest"].sum()
    summary_row = {date_col: "TOTAL", "balanceinr": "", "daily_interest": total_interest}
    export_df = pd.concat([export_df, pd.DataFrame([summary_row])], ignore_index=True)
    # Download cleaned CSV
    out_buf = io.StringIO()
    export_df.to_csv(out_buf, index=False)
    st.download_button(
        "Download Output as a CSV",
        data=out_buf.getvalue(),
        file_name="cleaned_interest.csv",
        mime="text/csv",
    )
    # Also display table in app
    st.subheader("Export Preview")
    st.dataframe(export_df)
    # In app output
    st.subheader("Result")
    st.write(f"Total month's interest: **{total_interest:.2f}**")

def calc_sc(annual_interest_rate_input):
    df = pd.read_excel(uploaded)
    # 1. Find the first non-NaN row in column 3 (index 2)
    header_row = df[df.iloc[:, 2].notna()].index[0]
    # 2. Set that row as header
    df.columns = df.iloc[header_row]
    df = df.drop(index=range(header_row + 1))  # drop all rows up to header row
    # 3. Reset index
    df = df.reset_index(drop=True)
    # Drop columns where column name is NaN
    df = df.loc[:, df.columns.notna()]
    df.columns = (
        df.columns
        .str.strip()                     # remove leading/trailing spaces
        .str.lower()                     # convert to lowercase
        .str.replace(r"\s+", "_", regex=True)   # replace spaces with _
        .str.replace(r"[^a-z0-9_]", "", regex=True)  # remove non-alphanumeric
    )
    df = df.replace(r'^\s*$', np.nan, regex=True)
    row_has_data = df.notna().any(axis=1)

    if row_has_data.any():
        first_valid = row_has_data.idxmax()
        last_valid  = row_has_data[::-1].idxmax()
        df = df.loc[first_valid:last_valid].reset_index(drop=True)
    else:
        df = df.iloc[0:0].copy()

    df["balance"] = (
    df["balance"]
      .astype(str)
      .str.replace(",", "", regex=False)
      .astype(float)
    )
    mask = ~df["date"].duplicated(keep='last')
    df_last_per_date = df[mask].copy()
    df_last_per_date["daily_interest"] = np.where(
    df_last_per_date["balance"] < 0,
    df_last_per_date["balance"] * -1*(annual_interest_rate_input / 365),
    0
    )
    total_interest = df_last_per_date["daily_interest"].sum()

    export_df = df_last_per_date[["date","balance", "daily_interest"]].copy()
    # Add summary row
    total_interest = export_df["daily_interest"].sum()
    summary_row = {"date": "TOTAL", "balance": "", "daily_interest": total_interest}
    export_df = pd.concat([export_df, pd.DataFrame([summary_row])], ignore_index=True)
    # Download cleaned CSV
    out_buf = io.StringIO()
    export_df.to_csv(out_buf, index=False)
    st.download_button(
        "Download Output as a CSV",
        data=out_buf.getvalue(),
        file_name="cleaned_interest.csv",
        mime="text/csv",
    )
    # Also display table in app
    st.subheader("Export Preview")
    st.dataframe(export_df)
    # In app output
    st.subheader("Result")
    st.write(f"Total month's interest: **{total_interest:.2f}**")
    
def calc_hdfc(annual_interest_rate_input):
    df = pd.read_excel(uploaded)
    df.columns = (
    df.columns
      .str.strip()                     # remove leading/trailing spaces
      .str.lower()                     # convert to lowercase
      .str.replace(r"\s+", "_", regex=True)   # replace spaces with _
      .str.replace(r"[^a-z0-9_]", "", regex=True)  # remove non-alphanumeric
    )
    df2 = df.iloc[::-1].reset_index(drop=True)
    df2["transaction_date"] = pd.to_datetime(df2["transaction_date"], format="%d/%m/%Y %H:%M:%S")
    df2["day"] = df2["transaction_date"].dt.day_name()
    # keep only the last occurrence per date, preserving original order
    mask = ~df2["value_date"].duplicated(keep='last')
    df_last_per_date = df2[mask].copy()
    # Make sure it's datetime
    df_last_per_date["value_date"] = pd.to_datetime(
        df_last_per_date["value_date"], format="%d/%m/%Y"
    )
    # Calculate difference in days with next row
    df_last_per_date["day_diff"] = (
        df_last_per_date["value_date"].shift(-1) - df_last_per_date["value_date"]
    ).dt.days
    df_last_per_date["day_diff"] = df_last_per_date["day_diff"].fillna(1)
    
    df_last_per_date["daily_interest"] = np.where(
        df_last_per_date["running_balance"] < 0,
        df_last_per_date["running_balance"] * -1 *(annual_interest_rate_input / 365) * df_last_per_date["day_diff"],
        0
    )
    total_interest = df_last_per_date["daily_interest"].sum()

    export_df = df_last_per_date[["value_date","running_balance", "daily_interest"]].copy()
    # Add summary row
    total_interest = export_df["daily_interest"].sum()
    summary_row = {"value_date": "TOTAL", "running_balance": "", "daily_interest": total_interest}
    export_df = pd.concat([export_df, pd.DataFrame([summary_row])], ignore_index=True)
    # Download cleaned CSV
    out_buf = io.StringIO()
    export_df.to_csv(out_buf, index=False)
    st.download_button(
        "Download Output as a CSV",
        data=out_buf.getvalue(),
        file_name="cleaned_interest.csv",
        mime="text/csv",
    )
    # Also display table in app
    st.subheader("Export Preview")
    st.dataframe(export_df)
    # In app output
    st.subheader("Result")
    st.write(f"Total month's interest: **{total_interest:.2f}**")

# ---- Run ----
if uploaded and run_btn:
    annual_rate = annual_interest_rate_input / 100.0
    if bank_choice == "Axis Bank":
        calc_axis(annual_rate)
    elif bank_choice == "Standard Chartered":
        calc_sc( annual_rate)
    else:
        calc_hdfc(annual_rate)


    

