import streamlit as st
import pandas as pd
from datetime import date
from urllib.parse import urlencode
from io import BytesIO
import qrcode

from github_storage import (
    github_configured,
    append_attendance,
    read_attendance,
    list_attendance_files,
)

# ---------------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------------

st.set_page_config(
    page_title="Seminar Attendance",
    page_icon="🎓",
    layout="centered",
)

# ---------------------------------------------------------
# CUSTOM CSS
# ---------------------------------------------------------

st.markdown(
    """
    <style>
    .main-title {
        font-size: 34px;
        font-weight: 700;
        margin-bottom: 0;
    }

    .company-name {
        font-size: 18px;
        color: #555;
        margin-bottom: 25px;
    }

    .success-box {
        padding: 15px;
        border-radius: 10px;
        background-color: #e8f5e9;
        border: 1px solid #81c784;
    }

    .info-box {
        padding: 15px;
        border-radius: 10px;
        background-color: #e3f2fd;
        border: 1px solid #64b5f6;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# HEADER
# ---------------------------------------------------------

st.markdown(
    '<div class="main-title">🎓 Seminar Attendance</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="company-name">Niyature Technologies</div>',
    unsafe_allow_html=True,
)


# ---------------------------------------------------------
# GITHUB CONFIG CHECK
# ---------------------------------------------------------

if not github_configured():
    st.error(
        """
        GitHub storage is not configured.

        Please configure the following values in Streamlit Cloud:

        - GITHUB_OWNER
        - GITHUB_REPO
        - GITHUB_BRANCH
        - GITHUB_TOKEN
        - ATTENDANCE_DIR
        - ADMIN_PASSWORD
        """
    )
    st.stop()


# ---------------------------------------------------------
# URL PARAMETERS
# ---------------------------------------------------------

params = st.query_params

seminar = params.get("seminar", "")
seminar_date = params.get("date", "")
college = params.get("college", "")
admin_mode = params.get("admin", "")


# ---------------------------------------------------------
# VALIDATE SEMINAR URL
# ---------------------------------------------------------

if not admin_mode:

    if not seminar or not seminar_date or not college:
        st.warning(
            """
            The organizer has not provided a valid seminar attendance link.
            """
        )

        st.info(
            """
            A valid seminar link must contain:

            `seminar`

            `date`

            `college`
            """
        )

        st.code(
            "https://YOUR-APP.streamlit.app/"
            "?seminar=Big%20Data%20AI"
            "&date=2026-10-05"
            "&college=ABC%20College"
        )

        st.stop()


# ---------------------------------------------------------
# ADMIN MODE
# ---------------------------------------------------------

if admin_mode == "1":

    st.header("🔐 Organizer / Admin")

    password = st.text_input(
        "Admin Password",
        type="password",
    )

    admin_password = st.secrets.get(
        "ADMIN_PASSWORD",
        "",
    )

    if not password:
        st.info("Enter the admin password.")
        st.stop()

    if password != admin_password:
        st.error("Invalid admin password.")
        st.stop()

    st.success("Admin access granted.")

    st.divider()

    # -----------------------------------------------------
    # CREATE SEMINAR LINK
    # -----------------------------------------------------

    st.subheader("Create Seminar Attendance Link")

    seminar_name = st.text_input(
        "Seminar Name",
        placeholder="Big Data Analytics",
    )

    college_name = st.text_input(
        "College Name",
        placeholder="ABC College of Engineering",
    )

    seminar_dt = st.date_input(
        "Seminar Date",
        value=date.today(),
    )

    if st.button(
        "Generate Attendance Link",
        type="primary",
        use_container_width=True,
    ):

        if not seminar_name.strip():
            st.error("Please enter seminar name.")
            st.stop()

        if not college_name.strip():
            st.error("Please enter college name.")
            st.stop()

        query = urlencode(
            {
                "seminar": seminar_name.strip(),
                "date": seminar_dt.isoformat(),
                "college": college_name.strip(),
            }
        )

        # APP_URL should be configured in Streamlit Secrets.
        app_url = st.secrets.get(
            "APP_URL",
            "",
        ).strip()

        if not app_url:
            st.warning(
                """
                APP_URL is not configured in Streamlit Secrets.

                Enter your Streamlit application URL below.
                """
            )

            app_url = st.text_input(
                "Streamlit App URL",
                placeholder="https://your-app.streamlit.app",
            ).strip().rstrip("/")

        if app_url:

            attendance_url = f"{app_url}/?{query}"

            st.success("Attendance link generated.")

            st.text_input(
                "Student Attendance URL",
                value=attendance_url,
            )

            st.markdown("### QR Code")

            qr = qrcode.make(attendance_url)

            buffer = BytesIO()
            qr.save(buffer, format="PNG")

            st.image(
                buffer.getvalue(),
                caption="Scan to mark attendance",
                width=300,
            )

            st.download_button(
                label="Download QR Code",
                data=buffer.getvalue(),
                file_name="seminar_attendance_qr.png",
                mime="image/png",
                use_container_width=True,
            )

    # -----------------------------------------------------
    # VIEW ATTENDANCE FILES
    # -----------------------------------------------------

    st.divider()

    st.subheader("📊 Attendance Records")

    try:

        files = list_attendance_files()

        if not files:
            st.info("No attendance files found yet.")

        else:

            selected_file = st.selectbox(
                "Select Attendance File",
                files,
            )

            if selected_file:

                df = read_attendance(
                    selected_file
                )

                if df is not None and not df.empty:

                    st.write(
                        f"Total Attendance: **{len(df)}**"
                    )

                    st.dataframe(
                        df,
                        use_container_width=True,
                        hide_index=True,
                    )

                    csv_data = df.to_csv(
                        index=False
                    ).encode("utf-8")

                    st.download_button(
                        "Download CSV",
                        data=csv_data,
                        file_name=selected_file.split("/")[-1],
                        mime="text/csv",
                        use_container_width=True,
                    )

                else:
                    st.warning(
                        "Attendance file is empty."
                    )

    except Exception as e:

        st.error(
            f"Unable to load attendance records: {e}"
        )

    st.stop()


# ---------------------------------------------------------
# STUDENT ATTENDANCE PAGE
# ---------------------------------------------------------

st.header(seminar)

st.markdown(
    f"""
    **College:** {college}

    **Seminar Date:** {seminar_date}
    """
)

st.divider()

# ---------------------------------------------------------
# ATTENDANCE FORM
# ---------------------------------------------------------

st.subheader("Mark Attendance")

st.write(
    "You can enter multiple students from the same device."
)

MAX_STUDENTS = 20

with st.form("attendance_form"):

    number_of_students = st.number_input(
        "Number of Students",
        min_value=1,
        max_value=MAX_STUDENTS,
        value=1,
        step=1,
    )

    student_entries = []

    for i in range(int(number_of_students)):

        st.markdown(
            f"**Student {i + 1}**"
        )

        col1, col2 = st.columns(2)

        with col1:

            student_name = st.text_input(
                "Student Name",
                key=f"name_{i}",
                placeholder="Full Name",
            )

        with col2:

            enrollment_number = st.text_input(
                "Enrollment / Roll Number",
                key=f"roll_{i}",
                placeholder="Roll Number",
            )

        student_entries.append(
            {
                "student_name": student_name.strip(),
                "enrollment_number": enrollment_number.strip(),
            }
        )

    submitted = st.form_submit_button(
        "Submit Attendance",
        type="primary",
        use_container_width=True,
    )


# ---------------------------------------------------------
# PROCESS ATTENDANCE
# ---------------------------------------------------------

if submitted:

    valid_students = []

    for student in student_entries:

        if (
            student["student_name"]
            and student["enrollment_number"]
        ):
            valid_students.append(student)

    if not valid_students:

        st.error(
            "Please enter at least one student's details."
        )

        st.stop()

    # ---------------------------------------------
    # Check duplicate roll numbers inside submission
    # ---------------------------------------------

    roll_numbers = [
        x["enrollment_number"].lower()
        for x in valid_students
    ]

    duplicate_rolls = {
        x for x in roll_numbers
        if roll_numbers.count(x) > 1
    }

    if duplicate_rolls:

        st.error(
            "Duplicate enrollment / roll number found in this submission."
        )

        st.write(
            ", ".join(duplicate_rolls)
        )

        st.stop()

    # ---------------------------------------------
    # Prepare seminar identifier
    # ---------------------------------------------

    seminar_info = {
        "seminar": seminar,
        "date": seminar_date,
        "college": college,
    }

    # ---------------------------------------------
    # Save each student
    # ---------------------------------------------

    successful = []
    duplicate = []
    failed = []

    for student in valid_students:

        result = append_attendance(
            seminar_info=seminar_info,
            student_name=student["student_name"],
            enrollment_number=student["enrollment_number"],
        )

        if result["status"] == "success":

            successful.append(student)

        elif result["status"] == "duplicate":

            duplicate.append(student)

        else:

            failed.append(
                {
                    **student,
                    "error": result.get(
                        "message",
                        "Unknown error",
                    ),
                }
            )

    # ---------------------------------------------
    # Results
    # ---------------------------------------------

    if successful:

        st.success(
            f"Attendance successfully recorded for "
            f"{len(successful)} student(s)."
        )

    if duplicate:

        st.warning(
            f"{len(duplicate)} student(s) were already marked present."
        )

        with st.expander(
            "View duplicate students"
        ):

            for student in duplicate:

                st.write(
                    f"• {student['student_name']} "
                    f"({student['enrollment_number']})"
                )

    if failed:

        st.error(
            f"{len(failed)} student(s) could not be recorded."
        )

        with st.expander(
            "View failed records"
        ):

            for student in failed:

                st.write(
                    f"• {student['student_name']} "
                    f"({student['enrollment_number']})"
                )

                st.caption(
                    student["error"]
                )

    if successful:

        st.balloons()

        st.markdown(
            """
            <div class="success-box">

            ### ✅ Attendance Submitted

            Thank you for attending the seminar.

            </div>
            """,
            unsafe_allow_html=True,
        )
