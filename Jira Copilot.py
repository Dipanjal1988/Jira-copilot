import streamlit as st

import zipfile

import tempfile

import os

import re

import pandas as pd

from datetime import datetime

import io

import requests

from requests.auth import HTTPBasicAuth



# -------------- ICS Branding Setup -------------- #

st.set_page_config(page_title="ICS-Jira Copilot", layout="centered")

ICS_COLOR = "#002060"

st.markdown(f"<h1 style='color:{ICS_COLOR}; font-family:sans-serif;'>ICS - Jira Copilot</h1>", unsafe_allow_html=True)



# -------------- Login Page -------------- #

if "authenticated" not in st.session_state:

    st.session_state.authenticated = False



if not st.session_state.authenticated:

    password = st.text_input("Enter password", type="password")

    if st.button("Login"):

        if password == "icsjira2025":

            st.session_state.authenticated = True

        else:

            st.error("Incorrect password.")

    st.stop()



# -------------- Parsing Helpers -------------- #

def extract_columns(sql):

    match = re.search(r'select\s+(.*?)\s+from', sql, re.IGNORECASE | re.DOTALL)

    if match:

        raw = match.group(1)

        skip_keywords = ['uri', 'format', 'header', 'footer']

        columns = []

        for col in raw.split(','):

            col_clean = col.strip().split()[0]

            if not any(k in col_clean.lower() for k in skip_keywords):

                columns.append(col_clean)

        return columns[:5]

    return []



def extract_table(sql):

    match = re.search(r'from\s+([a-zA-Z0-9_.]+)', sql, re.IGNORECASE)

    return match.group(1) if match else "unspecified_table"



def extract_conditions(sql):

    match = re.search(r'where\s+(.*?)(group by|order by|limit|;|$)', sql, re.IGNORECASE | re.DOTALL)

    return match.group(1).strip() if match else None



def extract_schedule(sql):

    match = re.search(r'(daily|hourly|schedule\s*[:=]\s*["\']?([a-zA-Z0-9 _:/-]+))', sql, re.IGNORECASE)

    if match:

        return match.group(1).lower()

    return ""



def extract_target_path(sql):

    match = re.search(r'uri\s*=\s*[\'"]([^\'"]+)[\'"]', sql, re.IGNORECASE)

    return match.group(1) if match else None



def parse_job_file(filename, content):

    job_name = os.path.splitext(os.path.basename(filename))[0]

    return {

        "job_name": job_name,

        "table": extract_table(content),

        "columns": extract_columns(content),

        "conditions": extract_conditions(content),

        "schedule": extract_schedule(content),

        "target_path": extract_target_path(content),

        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    }



def generate_user_story(job):

    col_list = ", ".join(job["columns"]) if job["columns"] else "1 or more columns"

    story = f"The ICS team will develop and deploy the egress job **{job['job_name']}** to extract data from columns ({col_list}) from the table **{job['table']}**"

    if job["conditions"]:

        story += f" with the condition `{job['conditions']}`"

    if job["schedule"]:

        story += f", scheduled for `{job['schedule']}` execution"

    if job["target_path"]:

        story += f", targeting **{job['target_path']}**"

    story += "."

    return story



# -------------- File Upload -------------- #

st.markdown(f"<h3 style='color:{ICS_COLOR};'>Upload Job Files</h3>", unsafe_allow_html=True)

uploaded_file = st.file_uploader("Upload a ZIP or a single job file", type=["zip", "sql", "bteq", "plsql", "txt"])

story_rows = []



if uploaded_file:

    with tempfile.TemporaryDirectory() as tmpdir:

        if uploaded_file.name.endswith(".zip"):

            with zipfile.ZipFile(uploaded_file, "r") as zip_ref:

                zip_ref.extractall(tmpdir)

            for root, _, files in os.walk(tmpdir):

                for file in files:

                    if file.lower().endswith(('.sql', '.bteq', '.plsql', '.txt')):

                        path = os.path.join(root, file)

                        with open(path, "r", encoding="utf-8") as f:

                            content = f.read()

                            job = parse_job_file(file, content)

                            story = generate_user_story(job)

                            story_rows.append([job["job_name"], story, job["timestamp"]])

        else:

            content = uploaded_file.read().decode("utf-8")

            job = parse_job_file(uploaded_file.name, content)

            story = generate_user_story(job)

            story_rows.append([job["job_name"], story, job["timestamp"]])



# -------------- Output & Excel Export -------------- #

if story_rows:

    df = pd.DataFrame(story_rows, columns=["egress_job_name", "user_story", "timestamp"])

    df.index += 1

    df.reset_index(inplace=True)

    df.rename(columns={"index": "Index"}, inplace=True)



    st.markdown(f"<h3 style='color:{ICS_COLOR};'>Generated User Stories</h3>", unsafe_allow_html=True)

    for _, row in df.iterrows():

        st.markdown(f"**{row['Index']}.** {row['user_story']}", unsafe_allow_html=True)



    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:

        df.to_excel(writer, index=False, sheet_name="UserStories")

        workbook = writer.book

        worksheet = writer.sheets["UserStories"]

        wrap_format = workbook.add_format({'text_wrap': True, 'valign': 'top'})

        worksheet.set_column("A:A", 8)

        worksheet.set_column("B:B", 25)

        worksheet.set_column("C:C", 120, wrap_format)

        worksheet.set_column("D:D", 25)



    st.download_button(

        label="Download User Stories as Excel",

        data=output.getvalue(),

        file_name="ics_egress_user_stories.xlsx",

        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    )



# -------------- Optional JIRA Integration -------------- #

st.markdown(f"<h3 style='color:{ICS_COLOR};'>Optional JIRA Integration</h3>", unsafe_allow_html=True)

with st.expander("Push stories to JIRA 'To Do' column"):

    jira_url = st.text_input("JIRA Base URL (e.g. https://yourdomain.atlassian.net)")

    jira_email = st.text_input("JIRA Email")

    jira_token = st.text_input("API Token", type="password")

    jira_project = st.text_input("JIRA Project Key (e.g. ICS)")



    if st.button("Create JIRA Stories"):

        if jira_url and jira_email and jira_token and jira_project:

            headers = {"Accept": "application/json", "Content-Type": "application/json"}

            auth = HTTPBasicAuth(jira_email, jira_token)

            for _, row in df.iterrows():

                payload = {

                    "fields": {

                        "project": {"key": jira_project},

                        "summary": row['egress_job_name'],

                        "description": row['user_story'],

                        "issuetype": {"name": "Story"}

                    }

                }

                response = requests.post(f"{jira_url}/rest/api/3/issue", headers=headers, auth=auth, json=payload)

                if response.status_code == 201:

                    st.success(f"Created: {response.json()['key']}")

                else:

                    st.error(f"Failed: {response.status_code} {response.text}")