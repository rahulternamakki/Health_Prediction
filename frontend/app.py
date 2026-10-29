import pandas as pd
import streamlit as st

from api_client import (
    ApiError,
    create_patient,
    delete_patient,
    get_patient,
    list_patients,
    rerun_prediction,
    update_patient,
)

# 1. Page configuration must be the first Streamlit call
st.set_page_config(page_title="Health Risk Records", layout="wide")

# 2. Permanent medical disclaimer on every page
st.info("Screening aid only. Not a medical diagnosis. Consult a qualified doctor.")

# 3. Sidebar navigation
page = st.sidebar.radio("Navigation", ["Records", "Add patient"])


@st.dialog("Confirm delete")
def confirm_delete_dialog(patient: dict):
    st.write(f"Are you sure you want to delete patient **{patient['full_name']}**?")
    col_cancel, col_confirm = st.columns(2)
    with col_cancel:
        if st.button("Cancel", key="dlg_cancel_btn"):
            st.rerun()
    with col_confirm:
        if st.button("Confirm", type="primary", key="dlg_confirm_btn"):
            try:
                delete_patient(patient["id"])
                st.session_state.action_message = f"Patient {patient['full_name']} deleted."
                st.session_state.edit_id = None
                st.rerun()
            except ApiError as err:
                st.error(err.message)


if page == "Add patient":
    st.title("Add Patient")

    # Form nonce resets the form on success while preserving entered values on error
    nonce = st.session_state.setdefault("add_form_nonce", 0)

    # Show result banner from previous successful submission
    if "last_created" in st.session_state:
        created = st.session_state.pop("last_created")
        st.success(f"Patient **{created['full_name']}** added successfully!")
        st.write(f"**Risk Level:** {created['risk_level']}")
        st.write(f"**Remarks:** {created['remarks'] or 'No remarks recorded.'}")
        if created.get("risk_level") == "Pending":
            st.warning(
                "AI service was temporarily unavailable. Record was saved as 'Pending'. "
                "You can re-run prediction from the Records page."
            )

    with st.form("add_patient_form", clear_on_submit=False):
        full_name = st.text_input("Full name", key=f"name_{nonce}")
        date_of_birth = st.text_input("Date of birth", placeholder="dd/mm/yyyy", key=f"dob_{nonce}")
        email = st.text_input("Email", key=f"email_{nonce}")
        glucose = st.number_input(
            "Glucose (mg/dL)",
            value=None,
            min_value=0.0,
            max_value=10000.0,
            step=0.1,
            format="%.1f",
            key=f"gluc_{nonce}",
        )
        haemoglobin = st.number_input(
            "Haemoglobin (g/dL)",
            value=None,
            min_value=0.0,
            max_value=100.0,
            step=0.1,
            format="%.1f",
            key=f"hb_{nonce}",
        )
        cholesterol = st.number_input(
            "Cholesterol (mg/dL)",
            value=None,
            min_value=0.0,
            max_value=10000.0,
            step=0.1,
            format="%.1f",
            key=f"chol_{nonce}",
        )

        submitted = st.form_submit_button("Save Patient")
        if submitted:
            if (
                not full_name
                or not date_of_birth
                or not email
                or glucose is None
                or haemoglobin is None
                or cholesterol is None
            ):
                st.error("Please fill in all fields")
            else:
                payload = {
                    "full_name": full_name,
                    "date_of_birth": date_of_birth,
                    "email": email,
                    "glucose": float(glucose),
                    "haemoglobin": float(haemoglobin),
                    "cholesterol": float(cholesterol),
                }
                try:
                    with st.spinner("Analysing blood values..."):
                        res = create_patient(payload)
                    st.session_state.last_created = res
                    st.session_state.add_form_nonce += 1
                    st.rerun()
                except ApiError as err:
                    st.error(err.message)


elif page == "Records":
    st.title("Patient Records")

    if "action_message" in st.session_state:
        st.success(st.session_state.pop("action_message"))

    search_query = st.text_input(
        "Search", placeholder="Search by name or email...", key="search_query"
    )

    try:
        patients = list_patients(search=search_query)
    except ApiError as err:
        st.error(err.message)
        patients = []

    total_count = len(patients)
    high_risk_count = sum(1 for p in patients if p.get("risk_level") == "High")
    pending_count = sum(1 for p in patients if p.get("risk_level") == "Pending")

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Patients", total_count)
    col2.metric("High Risk", high_risk_count)
    col3.metric("Pending", pending_count)

    st.divider()

    if total_count == 0:
        if search_query:
            st.info("No patients found matching your search.")
        else:
            st.info("No patient records yet. Use Add patient to create one.")
    else:
        table_rows = []
        for p in patients:
            table_rows.append(
                {
                    "Name": p["full_name"],
                    "Date of birth": p["date_of_birth"],
                    "Email": p["email"],
                    "Glucose": p["glucose"],
                    "Haemoglobin": p["haemoglobin"],
                    "Cholesterol": p["cholesterol"],
                    "Risk": p["risk_level"],
                    "Remarks": p["remarks"] or "",
                }
            )
        df = pd.DataFrame(table_rows)

        event = st.dataframe(
            df,
            on_select="rerun",
            selection_mode="single-row",
            hide_index=True,
            use_container_width=True,
            key="patients_dataframe",
        )

        selected_rows = event.selection.rows if event and hasattr(event, "selection") else []
        if selected_rows and len(selected_rows) > 0 and 0 <= selected_rows[0] < len(patients):
            selected_patient = patients[selected_rows[0]]

            st.subheader(f"Selected: {selected_patient['full_name']}")
            st.write(f"**Remarks:** {selected_patient['remarks'] or 'No remarks recorded.'}")

            col_edit, col_rerun, col_del = st.columns(3)
            with col_edit:
                if st.button("Edit", key=f"btn_edit_{selected_patient['id']}"):
                    st.session_state.edit_id = selected_patient["id"]
                    st.rerun()

            with col_rerun:
                if st.button("Re-run prediction", key=f"btn_rerun_{selected_patient['id']}"):
                    try:
                        with st.spinner("Analysing blood values..."):
                            rerun_prediction(selected_patient["id"])
                        st.session_state.action_message = (
                            f"Prediction re-run successfully for {selected_patient['full_name']}."
                        )
                        st.rerun()
                    except ApiError as err:
                        st.error(err.message)

            with col_del:
                if st.button("Delete", type="primary", key=f"btn_del_{selected_patient['id']}"):
                    confirm_delete_dialog(selected_patient)

    # Edit section if an edit is active
    edit_id = st.session_state.get("edit_id")
    if edit_id:
        target_patient = next((p for p in patients if p["id"] == edit_id), None)
        if not target_patient:
            try:
                target_patient = get_patient(edit_id)
            except ApiError:
                target_patient = None

        if target_patient:
            st.divider()
            st.subheader(f"Edit Patient: {target_patient['full_name']}")
            with st.form("edit_patient_form", clear_on_submit=False):
                edit_name = st.text_input("Full name", value=target_patient["full_name"])
                edit_dob = st.text_input(
                    "Date of birth", value=target_patient["date_of_birth"], placeholder="dd/mm/yyyy"
                )
                edit_email = st.text_input("Email", value=target_patient["email"])
                edit_glucose = st.number_input(
                    "Glucose (mg/dL)",
                    value=float(target_patient["glucose"]),
                    min_value=0.0,
                    max_value=10000.0,
                    step=0.1,
                    format="%.1f",
                )
                edit_hb = st.number_input(
                    "Haemoglobin (g/dL)",
                    value=float(target_patient["haemoglobin"]),
                    min_value=0.0,
                    max_value=100.0,
                    step=0.1,
                    format="%.1f",
                )
                edit_chol = st.number_input(
                    "Cholesterol (mg/dL)",
                    value=float(target_patient["cholesterol"]),
                    min_value=0.0,
                    max_value=10000.0,
                    step=0.1,
                    format="%.1f",
                )

                col_save, col_cancel = st.columns(2)
                with col_save:
                    save_submitted = st.form_submit_button("Save Changes")
                with col_cancel:
                    cancel_edit = st.form_submit_button("Cancel")

                if cancel_edit:
                    st.session_state.edit_id = None
                    st.rerun()

                if save_submitted:
                    if (
                        not edit_name
                        or not edit_dob
                        or not edit_email
                        or edit_glucose is None
                        or edit_hb is None
                        or edit_chol is None
                    ):
                        st.error("Please fill in all fields")
                    else:
                        update_payload = {
                            "full_name": edit_name,
                            "date_of_birth": edit_dob,
                            "email": edit_email,
                            "glucose": float(edit_glucose),
                            "haemoglobin": float(edit_hb),
                            "cholesterol": float(edit_chol),
                        }
                        try:
                            with st.spinner("Analysing blood values..."):
                                update_patient(edit_id, update_payload)
                            st.session_state.edit_id = None
                            st.session_state.action_message = (
                                f"Patient {edit_name} updated successfully."
                            )
                            st.rerun()
                        except ApiError as err:
                            st.error(err.message)
