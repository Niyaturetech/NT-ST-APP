# Seminar Attendance — GitHub CSV Storage

Streamlit seminar attendance app that stores each seminar's attendance as a CSV file directly in a GitHub repository. No database is required.

## CSV naming

Each file is named:

`seminar_date_college.csv`

Example:

`2026-10-05_ABC_College.csv`

The app creates the file automatically when the first attendance is submitted.

## GitHub token

Create a GitHub fine-grained Personal Access Token for the repository. It needs repository **Contents: Read and write** permission. Store the token only in Streamlit Cloud Secrets.

Never commit the token to GitHub.

## Streamlit Cloud Secrets

```toml
GITHUB_OWNER = "your-github-username"
GITHUB_REPO = "seminar-attendance"
GITHUB_BRANCH = "main"
GITHUB_TOKEN = "github_pat_..."
ATTENDANCE_DIR = "attendance"
ADMIN_PASSWORD = "strong-admin-password"
```

## Public attendance URL

Use URL parameters:

`https://YOUR-APP.streamlit.app/?seminar=Big%20Data%20AI&date=2026-10-05&college=ABC%20College`

The app writes to:

`attendance/2026-10-05_ABC_College.csv`

## Admin URL

`https://YOUR-APP.streamlit.app/?admin=1`

Enter the `ADMIN_PASSWORD` from Streamlit Secrets.

## Important concurrency note

The app uses GitHub's file API and checks the current file SHA before updating it. If many students submit at exactly the same moment, GitHub can reject a simultaneous update. The app reports this rather than silently losing data. For very large/high-concurrency events, use a real database or queue-based backend.
