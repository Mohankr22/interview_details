import streamlit as st
import pandas as pd
import os
import sqlite3
from dotenv import load_dotenv
from groq import Groq

# ----------------------------
# LOAD ENV
# ----------------------------
load_dotenv()
api_key = os.getenv("GROQ_API_KEY")

# ----------------------------
# PAGE SETTINGS
# ----------------------------
st.set_page_config(
    page_title="Interview Report + AI Chatbox",
    layout="wide"
)

st.title("Interview Report Generator")

# ----------------------------
# CHECK API KEY
# ----------------------------
if not api_key:
    st.error("❌ GROQ_API_KEY not found in .env file")
    st.stop()

client = Groq(api_key=api_key)

# ----------------------------
# SQLITE SETUP
# ----------------------------
conn = sqlite3.connect("interviews.db", check_same_thread=False)

# ----------------------------
# DATA SOURCE
# ----------------------------
st.subheader("📂 Choose Data Source")

option = st.radio(
    "Select option",
    ["Upload File", "Load from Database"]
)

df = None
date_col = None
interviewer_col = None
status_col = None

# =========================================================
# LOAD FROM DATABASE
# =========================================================
if option == "Load from Database":
    try:
        df = pd.read_sql_query("SELECT * FROM interviews", conn)

        if df.empty:
            st.warning("⚠️ No data found in database")
        else:
            st.success("✅ Data loaded from database")
            st.dataframe(df, use_container_width=True)

    except:
        st.error("❌ No table found. Please upload data first.")

# =========================================================
# UPLOAD FILE
# =========================================================
elif option == "Upload File":

    file = st.file_uploader("Upload Excel / CSV", type=["xlsx", "csv"])

    if file:

        if file.name.endswith(".csv"):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)

        df.columns = df.columns.str.strip()

        # Detect columns
        for col in df.columns:
            low = col.lower()

            if "date" in low:
                date_col = col

            if "interviewer" in low:
                interviewer_col = col

            if "status" in low:
                status_col = col

        # Clean date
        if date_col:
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce')

        # Save to DB
        df.to_sql("interviews", conn, if_exists="replace", index=False)

        st.success("✅ Data uploaded & saved to database")
        st.dataframe(df, use_container_width=True)

# =========================================================
# COMMON LOGIC (WORKS FOR BOTH OPTIONS)
# =========================================================
if df is not None and not df.empty:

    # Re-detect columns (important when loading from DB)
    for col in df.columns:
        low = col.lower()

        if "date" in low:
            date_col = col

        if "interviewer" in low:
            interviewer_col = col

        if "status" in low:
            status_col = col

    # =========================================================
    # SEARCH
    # =========================================================
    st.divider()
    st.subheader("🔍 SEARCH")

    search_text = st.text_input("Search anything")

    if search_text:
        search_conditions = [
            f'LOWER("{col}") LIKE LOWER("%{search_text}%")'
            for col in df.columns
        ]

        query = f"""
        SELECT * FROM interviews
        WHERE {" OR ".join(search_conditions)}
        """

        result = pd.read_sql_query(query, conn)
        st.dataframe(result, use_container_width=True)

    # =========================================================
    # FILTER
    # =========================================================
    st.divider()
    st.subheader("🧩 FILTER")

    c1, c2 = st.columns(2)

    if interviewer_col:
        interviewer_options = ["All"] + df[interviewer_col].dropna().astype(str).unique().tolist()
        selected_interviewer = c1.selectbox("Interviewer", interviewer_options)
    else:
        selected_interviewer = "All"

    if status_col:
        status_options = ["All"] + df[status_col].dropna().astype(str).unique().tolist()
        selected_status = c2.selectbox("Status", status_options)
    else:
        selected_status = "All"

    filtered_df = df.copy()

    if interviewer_col and selected_interviewer != "All":
        filtered_df = filtered_df[filtered_df[interviewer_col].astype(str) == selected_interviewer]

    if status_col and selected_status != "All":
        filtered_df = filtered_df[filtered_df[status_col].astype(str) == selected_status]

    st.dataframe(filtered_df, use_container_width=True)

    # =========================================================
    # DATE FILTER
    # =========================================================
    if date_col:
        st.divider()
        st.subheader("📅 Interview Date Filter")

        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')

        min_date = df[date_col].min()
        max_date = df[date_col].max()

        if pd.notnull(min_date) and pd.notnull(max_date):

            date_range = st.date_input(
                "Select Date Range",
                value=(min_date.date(), max_date.date())
            )

            if len(date_range) == 2:
                start_date = pd.to_datetime(date_range[0])
                end_date = pd.to_datetime(date_range[1])

                date_filtered_df = df[
                    (df[date_col] >= start_date) &
                    (df[date_col] <= end_date)
                ]

                st.success(f"📊 Total Interviews: {len(date_filtered_df)}")
                st.dataframe(date_filtered_df, use_container_width=True)

    # =========================================================
    # REPORT
    # =========================================================
    if interviewer_col and status_col:
        st.divider()
        st.subheader("📊 Final Report")

        report = pd.pivot_table(
            df,
            index=interviewer_col,
            columns=status_col,
            aggfunc="size",
            fill_value=0
        )

        report["Total"] = report.sum(axis=1)
        report.loc["Total"] = report.sum()

        st.dataframe(report, use_container_width=True)

    # =========================================================
    # SUMMARY
    # =========================================================
    st.divider()
    st.subheader("📊 Summary")

    st.metric("Total Candidates", len(df))

# =========================================================
# AI CHATBOX
# =========================================================
st.divider()
st.subheader("🤖 AI Chatbox")

question = st.text_input("Ask question about interview data")

if st.button("Ask AI"):

    if df is None or df.empty:
        st.warning("⚠️ Please load or upload data first")
    else:
        sample = df.head(30).to_string()

        prompt = f"""
You are HR data analyst.

Data:
{sample}

Question:
{question}

Give short answer.
"""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )

        st.success(response.choices[0].message.content)
        