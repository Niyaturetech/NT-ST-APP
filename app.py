import base64
import csv
import io
import re
from datetime import datetime, timezone

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Seminar Attendance", page_icon="✅", layout="centered")

OWNER = st.secrets.get("GITHUB_OWNER", "")
REPO = st.secrets.get("GITHUB_REPO", "")
BRANCH = st.secrets.get("GITHUB_BRANCH", "main")
TOKEN = st.secrets.get("GITHUB_TOKEN", "")
ATTENDANCE_DIR = st.secrets.get("ATTENDANCE_DIR", "attendance")
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "")

REQUIRED_COLUMNS = [
    "attendance_id", "timestamp_utc", "seminar_date", "college",
    "student_name", "mobile", "email", "department", "year", "roll_no"
]


def config_ok():
    return bool(OWNER and REPO and TOKEN)


def gh_headers():
    return {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def safe_filename(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return value.strip("._") or "unknown"


def attendance_filename(seminar_date: str, college: str) -> str:
    return f"{safe_filename(seminar_date)}_{safe_filename(college)}.csv"


def repo_path(seminar_date: str, college: str) -> str:
    return f"{ATTENDANCE_DIR.strip('/')}/{attendance_filename(seminar_date, college)}"


def github_get_file(path: str):
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{path}"
    r = requests.get(url, headers=gh_headers(), params={"ref": BRANCH}, timeout=20)
    if r.status_code == 404:
        return None, None
    r.raise_for_status()
    data = r.json()
    content = base64.b64decode(data["content"]).decode("utf-8")
    return content, data["sha"]


def github_put_file(path: str, content: str, sha: str | None, message: str):
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{path}"
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    payload = {"message": message, "content": encoded, "branch": BRANCH}
    if sha:
        payload["sha"] = sha
    r = requests.put(url, headers=gh_headers(), json=payload, timeout=30)
    if r.status_code == 409:
        raise RuntimeError("The attendance file changed at the same time. Please submit again.")
    r.raise_for_status()
    return r.json()


def parse_csv(content: str) -> list[dict]:
    if not content.strip():
        return []
    return list(csv.DictReader(io.StringIO(content)))


def build_csv(rows: list[dict]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=REQUIRED_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def normalize_mobile(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[-10:]
    return digits


def append_attendance(seminar_date: str, college: str, rows: list[dict]):
    path = repo_path(seminar_date, college)
    content, sha = github_get_file(path)
    existing = parse_csv(content or "")
    existing_mobiles = {normalize_mobile(r.get("mobile", "")) for r in existing}

    new_rows = []
    duplicate_rows = []
    for row in rows:
        mobile = normalize_mobile(row["mobile"])
        if mobile in existing_mobiles or any(normalize_mobile(x["mobile"]) == mobile for x in new_rows):
            duplicate_rows.append(row)
            continue
        row["mobile"] = mobile
        new_rows.append(row)
        existing_mobiles.add(mobile)

    if not new_rows:
        return 0, len(duplicate_rows), path

    updated = existing + new_rows
    github_put_file(
        path,
        build_csv(updated),
        sha,
        f"Add seminar attendance - {seminar_date} - {college}",
    )
    return len(new_rows), len(duplicate_rows), path


def list_attendance_files():
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{ATTENDANCE_DIR.strip('/')}"
    r = requests.get(url, headers=gh_headers(), params={"ref": BRANCH}, timeout=20)
    if r.status_code == 404:
        return []
    r.raise_for_status()
    return [x for x in r.json() if x.get("type") == "file" and x.get("name", "").endswith(".csv")]


def read_attendance_file(download_url: str):
    r = requests.get(download_url, headers=gh_headers(), timeout=20)
    r.raise_for_status()
    return r.text


def query_value(name, default=""):
    try:
        return st.query_params.get(name, default)
    except Exception:
        return default


st.markdown("<h1 style='text-align:center'>Seminar Attendance</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center;color:#666'>Niyature Technologies</p>", unsafe_allow_html=True)

if not config_ok():
    st.error("GitHub storage is not configured. Add the required Streamlit secrets before using the app.")
    st.code("GITHUB_OWNER = \"your-github-username\"\nGITHUB_REPO = \"seminar-attendance\"\nGITHUB_BRANCH = \"main\"\nGITHUB_TOKEN = \"your-token\"\nATTENDANCE_DIR = \"attendance\"\nADMIN_PASSWORD = \"your-admin-password\"")
    st.stop()

# Admin page
if query_value("admin") == "1":
    if not st.session_state.get("admin_logged_in", False):
        st.subheader("Admin Login")
        password = st.text_input("Admin password", type="password")
        if st.button("Login", type="primary", use_container_width=True):
            if ADMIN_PASSWORD and password == ADMIN_PASSWORD:
                st.session_state.admin_logged_in = True
                st.rerun()
            st.error("Invalid password.")
        st.stop()

    st.success("Admin dashboard")
    if st.button("Logout"):
        st.session_state.admin_logged_in = False
        st.rerun()

    st.subheader("Attendance files")
    files = list_attendance_files()
    if not files:
        st.info("No attendance CSV files have been created yet.")
    else:
        for item in files:
            st.markdown(f"**{item['name']}**")
            content = read_attendance_file(item["download_url"])
            df = pd.read_csv(io.StringIO(content))
            st.write(f"Records: {len(df)}")
            st.download_button(
                "Download CSV",
                data=content.encode("utf-8"),
                file_name=item["name"],
                mime="text/csv",
                key=f"download_{item['name']}",
                use_container_width=True,
            )
            with st.expander("Preview"):
                st.dataframe(df, use_container_width=True, hide_index=True)
    st.stop()

# Seminar parameters are intentionally explicit in the public URL.
seminar_date = query_value("date")
college = query_value("college")
seminar_name = query_value("seminar", "Seminar Attendance")

if not seminar_date or not college:
    st.info("The organizer has not provided a valid seminar attendance link.")
    st.markdown("Example public link:")
    st.code("https://YOUR-APP.streamlit.app/?seminar=Big%20Data%20AI&date=2026-10-05&college=ABC%20College")
    st.stop()

try:
    datetime.strptime(seminar_date, "%Y-%m-%d")
except ValueError:
    st.error("Invalid seminar date. Use YYYY-MM-DD.")
    st.stop()

st.subheader(seminar_name)
st.caption(f"Date: {seminar_date}  |  College: {college}")
st.info(f"Attendance will be stored in: {attendance_filename(seminar_date, college)}")

if "rows" not in st.session_state:
    st.session_state.rows = 1

st.markdown("### Mark attendance")
st.caption("A coordinator can enter multiple students from one device. Duplicate mobile numbers are rejected for this seminar/date/college file.")

for i in range(st.session_state.rows):
    with st.container(border=True):
        st.markdown(f"**Student {i + 1}**")
        c1, c2 = st.columns(2)
        c1.text_input("Full name *", key=f"name_{i}")
        c2.text_input("Mobile number *", key=f"mobile_{i}", max_chars=15)
        c3, c4 = st.columns(2)
        c3.text_input("Email", key=f"email_{i}")
        c4.text_input("Department", key=f"department_{i}")
        c5, c6, c7 = st.columns(3)
        c5.selectbox("Year", ["", "1st", "2nd", "3rd", "4th", "Other"], key=f"year_{i}")
        c6.text_input("Roll number", key=f"roll_{i}")
        c7.text_input("College", value=college, disabled=True, key=f"college_display_{i}")

c1, c2 = st.columns(2)
if c1.button("＋ Add another student", use_container_width=True):
    if st.session_state.rows < 50:
        st.session_state.rows += 1
        st.rerun()

if c2.button("Submit attendance", type="primary", use_container_width=True):
    rows = []
    errors = []
    seen = set()
    timestamp = datetime.now(timezone.utc).isoformat()

    for i in range(st.session_state.rows):
        name = st.session_state.get(f"name_{i}", "").strip()
        mobile = normalize_mobile(st.session_state.get(f"mobile_{i}", ""))
        email = st.session_state.get(f"email_{i}", "").strip()
        department = st.session_state.get(f"department_{i}", "").strip()
        year = st.session_state.get(f"year_{i}", "")
        roll_no = st.session_state.get(f"roll_{i}", "").strip()

        if not name or not mobile:
            errors.append(f"Student {i + 1}: name and mobile are required.")
            continue
        if len(mobile) != 10 or not mobile.isdigit():
            errors.append(f"Student {i + 1}: enter a valid 10-digit mobile number.")
            continue
        if mobile in seen:
            errors.append(f"Student {i + 1}: duplicate mobile number in this submission.")
            continue
        seen.add(mobile)
        rows.append({
            "attendance_id": f"ATT-{datetime.now().strftime('%Y%m%d%H%M%S')}-{i+1:02d}",
            "timestamp_utc": timestamp,
            "seminar_date": seminar_date,
            "college": college,
            "student_name": name,
            "mobile": mobile,
            "email": email,
            "department": department,
            "year": year,
            "roll_no": roll_no,
        })

    for error in errors:
        st.error(error)

    if rows:
        try:
            added, duplicates, path = append_attendance(seminar_date, college, rows)
            if added:
                st.success(f"Attendance successfully marked for {added} student(s).")
                st.caption(f"Stored in GitHub: {path}")
            if duplicates:
                st.warning(f"{duplicates} student(s) were skipped because attendance already exists.")
            if added:
                st.session_state.rows = 1
                for key in list(st.session_state.keys()):
                    if re.match(r"^(name|mobile|email|department|year|roll_no)_\d+$", key):
                        del st.session_state[key]
                st.rerun()
        except Exception as e:
            st.error(f"Could not save attendance: {e}")

st.divider()
st.caption("Please verify student details before submitting. Attendance is stored as a CSV file in the configured GitHub repository.")
