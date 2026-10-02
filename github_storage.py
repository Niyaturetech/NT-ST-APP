import base64
import io
import time
import re
from datetime import datetime

import pandas as pd
import requests
import streamlit as st


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

GITHUB_API = "https://api.github.com"


def github_configured():

    required = [
        "GITHUB_OWNER",
        "GITHUB_REPO",
        "GITHUB_BRANCH",
        "GITHUB_TOKEN",
    ]

    for key in required:

        value = st.secrets.get(key, "")

        if not value:
            return False

    return True


def get_config():

    return {
        "owner": st.secrets["GITHUB_OWNER"],
        "repo": st.secrets["GITHUB_REPO"],
        "branch": st.secrets.get(
            "GITHUB_BRANCH",
            "main",
        ),
        "token": st.secrets["GITHUB_TOKEN"],
        "attendance_dir": st.secrets.get(
            "ATTENDANCE_DIR",
            "attendance",
        ),
    }


def get_headers():

    config = get_config()

    return {
        "Authorization": (
            f"Bearer {config['token']}"
        ),
        "Accept": (
            "application/vnd.github+json"
        ),
        "X-GitHub-Api-Version": "2022-11-28",
    }


# ---------------------------------------------------------
# SAFE FILE NAME
# ---------------------------------------------------------

def sanitize_filename(value):

    value = str(value).strip()

    value = re.sub(
        r"[^A-Za-z0-9_-]+",
        "_",
        value,
    )

    value = re.sub(
        r"_+",
        "_",
        value,
    )

    return value.strip("_")


def get_attendance_file_path(
    seminar_date,
    college,
):

    config = get_config()

    safe_college = sanitize_filename(
        college
    )

    filename = (
        f"{seminar_date}_"
        f"{safe_college}.csv"
    )

    return (
        f"{config['attendance_dir'].strip('/')}/"
        f"{filename}"
    )


# ---------------------------------------------------------
# GITHUB URL
# ---------------------------------------------------------

def github_file_url(path):

    config = get_config()

    return (
        f"{GITHUB_API}/repos/"
        f"{config['owner']}/"
        f"{config['repo']}/contents/"
        f"{path}"
        f"?ref={config['branch']}"
    )


# ---------------------------------------------------------
# READ CSV FROM GITHUB
# ---------------------------------------------------------

def read_csv_from_github(
    path,
):

    response = requests.get(
        github_file_url(path),
        headers=get_headers(),
        timeout=20,
    )

    if response.status_code == 404:

        return (
            pd.DataFrame(),
            None,
        )

    response.raise_for_status()

    data = response.json()

    encoded_content = data.get(
        "content",
        "",
    ).replace("\n", "")

    if not encoded_content:

        return (
            pd.DataFrame(),
            data.get("sha"),
        )

    decoded = base64.b64decode(
        encoded_content
    ).decode(
        "utf-8"
    )

    if not decoded.strip():

        return (
            pd.DataFrame(),
            data.get("sha"),
        )

    df = pd.read_csv(
        io.StringIO(decoded),
        dtype=str,
    )

    return (
        df.fillna(""),
        data.get("sha"),
    )


# ---------------------------------------------------------
# WRITE CSV TO GITHUB
# ---------------------------------------------------------

def write_csv_to_github(
    path,
    df,
    sha=None,
):

    config = get_config()

    csv_content = df.to_csv(
        index=False
    )

    encoded = base64.b64encode(
        csv_content.encode("utf-8")
    ).decode("utf-8")

    payload = {
        "message": (
            "Update seminar attendance: "
            f"{path.split('/')[-1]}"
        ),
        "content": encoded,
        "branch": config["branch"],
    }

    if sha:

        payload["sha"] = sha

    url = (
        f"{GITHUB_API}/repos/"
        f"{config['owner']}/"
        f"{config['repo']}/contents/"
        f"{path}"
    )

    response = requests.put(
        url,
        headers=get_headers(),
        json=payload,
        timeout=20,
    )

    return response


# ---------------------------------------------------------
# APPEND ATTENDANCE
# ---------------------------------------------------------

def append_attendance(
    seminar_info,
    student_name,
    enrollment_number,
):

    seminar_date = seminar_info["date"]
    college = seminar_info["college"]
    seminar = seminar_info["seminar"]

    path = get_attendance_file_path(
        seminar_date,
        college,
    )

    # Retry to handle multiple students submitting
    # at approximately the same time.
    max_retries = 4

    for attempt in range(max_retries):

        try:

            df, sha = read_csv_from_github(
                path
            )

            # ---------------------------------------------
            # Create columns if file doesn't exist
            # ---------------------------------------------

            columns = [
                "timestamp",
                "seminar",
                "seminar_date",
                "college",
                "student_name",
                "enrollment_number",
                "status",
            ]

            if df.empty:

                df = pd.DataFrame(
                    columns=columns
                )

            # ---------------------------------------------
            # Normalize existing roll numbers
            # ---------------------------------------------

            if (
                "enrollment_number"
                in df.columns
            ):

                existing_rolls = (
                    df[
                        "enrollment_number"
                    ]
                    .astype(str)
                    .str.strip()
                    .str.lower()
                    .tolist()
                )

            else:

                existing_rolls = []

            current_roll = (
                str(enrollment_number)
                .strip()
                .lower()
            )

            # ---------------------------------------------
            # Duplicate check
            # ---------------------------------------------

            if current_roll in existing_rolls:

                return {
                    "status": "duplicate"
                }

            # ---------------------------------------------
            # New record
            # ---------------------------------------------

            new_record = {
                "timestamp": datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "seminar": seminar,
                "seminar_date": seminar_date,
                "college": college,
                "student_name": student_name,
                "enrollment_number": enrollment_number,
                "status": "Present",
            }

            new_df = pd.concat(
                [
                    df,
                    pd.DataFrame(
                        [new_record]
                    ),
                ],
                ignore_index=True,
            )

            # ---------------------------------------------
            # Save to GitHub
            # ---------------------------------------------

            response = write_csv_to_github(
                path=path,
                df=new_df,
                sha=sha,
            )

            if response.status_code in (
                200,
                201,
            ):

                return {
                    "status": "success"
                }

            # ---------------------------------------------
            # GitHub conflict
            # ---------------------------------------------

            if response.status_code == 409:

                # Another submission changed the file.
                # Fetch the latest version and retry.
                time.sleep(
                    0.5 * (attempt + 1)
                )

                continue

            return {
                "status": "error",
                "message": (
                    f"GitHub returned HTTP "
                    f"{response.status_code}: "
                    f"{response.text[:500]}"
                ),
            }

        except Exception as e:

            if attempt < max_retries - 1:

                time.sleep(
                    0.5 * (attempt + 1)
                )

                continue

            return {
                "status": "error",
                "message": str(e),
            }

    return {
        "status": "error",
        "message": (
            "Could not save attendance because "
            "the GitHub file was being updated "
            "by another submission. Please try again."
        ),
    }


# ---------------------------------------------------------
# LIST ATTENDANCE FILES
# ---------------------------------------------------------

def list_attendance_files():

    config = get_config()

    path = config[
        "attendance_dir"
    ].strip("/")

    url = (
        f"{GITHUB_API}/repos/"
        f"{config['owner']}/"
        f"{config['repo']}/contents/"
        f"{path}"
        f"?ref={config['branch']}"
    )

    response = requests.get(
        url,
        headers=get_headers(),
        timeout=20,
    )

    if response.status_code == 404:

        return []

    response.raise_for_status()

    items = response.json()

    files = []

    if isinstance(items, list):

        for item in items:

            if (
                item.get("type") == "file"
                and item.get("name", "")
                .lower()
                .endswith(".csv")
            ):

                files.append(
                    item["path"]
                )

    return sorted(
        files,
        reverse=True,
    )


# ---------------------------------------------------------
# READ ATTENDANCE FILE
# ---------------------------------------------------------

def read_attendance(
    path,
):

    df, _ = read_csv_from_github(
        path
    )

    return df
