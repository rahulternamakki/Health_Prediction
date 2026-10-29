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
from styles import CSS

# 1. Page configuration must be the first Streamlit call
st.set_page_config(page_title="Health Risk Records", layout="wide")

# Apply custom visual styling (fixed string, no user data)
st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)

# 2. Permanent medical disclaimer on every page
st.info("Screening aid only. Not a medical diagnosis. Consult a qualified doctor.")

# 3. Sidebar navigation & clinical context
with st.sidebar:
    st.markdown("### Health Predictor")
    st.caption("Clinical Decision-Support Platform")
    page = st.radio("Navigation", ["Records", "Add patient"])
    st.divider()
    with st.expander("Reference Guidelines"):
        st.markdown(
            "- **Glucose:** 70–99 normal, 100–125 prediabetes, 126+ diabetes\n"
            "- **Haemoglobin:** ~12–17.5 g/dL reference range\n"
            "- **Total Cholesterol:** <200 desirable, 200–239 borderline, 240+ high"
        )

# Fixed mapping for risk badges (zero user data in badges)
RISK_BADGE_MAP = {
    "Low": ("Low Risk", "green", "🟢"),
    "Moderate": ("Moderate Risk", "orange", "🟠"),
    "High": ("High Risk", "red", "🔴"),
    "Pending": ("Pending", "gray", "⏳"),
}


def render_risk_badge(risk_level: str):
    label, color, icon = RISK_BADGE_MAP.get(risk_level, ("Unknown", "gray", "❓"))
    st.badge(label, color=color, icon=icon)


@st.dialog("Confirm delete")
def confirm_delete_dialog(patient: dict):
    st.write(f"Are you sure you want to delete patient **{patient['full_name']}**?")
    st.caption("This action is permanent and cannot be undone.")
    col_cancel, col_confirm = st.columns(2)
    with col_cancel:
        if st.button("Cancel", key="dlg_cancel_btn", use_container_width=True):
            st.rerun()
    with col_confirm:
        if st.button("Confirm", type="primary", key="dlg_confirm_btn", use_container_width=True):
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
        with st.container(border=True):
            st.success(f"Patient **{created['full_name']}** added successfully!")
            col_b, col_rem = st.columns([1, 4])
            with col_b:
                render_risk_badge(created.get("risk_level", "Pending"))
            with col_rem:
                st.write(f"**Remarks:** {created['remarks'] or 'No remarks recorded.'}")
            if created.get("risk_level") == "Pending":
                st.warning(
                    "AI service was temporarily unavailable. Record was saved as 'Pending'. "
                    "You can re-run prediction from the Records page."
                )

    tabs = st.tabs(["Patient Intake Form", "Guidance & Notes"])
    with tabs[0]:
        with st.container(border=True):
            with st.form("add_patient_form", clear_on_submit=False):
                col_name, col_dob = st.columns([2, 1])
                with col_name:
                    full_name = st.text_input("Full name", key=f"name_{nonce}")
                with col_dob:
                    date_of_birth = st.text_input(
                        "Date of birth", placeholder="dd/mm/yyyy", key=f"dob_{nonce}"
                    )

                email = st.text_input("Email", key=f"email_{nonce}")

                st.markdown("##### Blood Test Values")
                col_g, col_h, col_c = st.columns(3)
                with col_g:
                    glucose = st.number_input(
                        "Glucose (mg/dL)",
                        value=None,
                        min_value=0.0,
                        max_value=10000.0,
                        step=0.1,
                        format="%.1f",
                        key=f"gluc_{nonce}",
                    )
                with col_h:
                    haemoglobin = st.number_input(
                        "Haemoglobin (g/dL)",
                        value=None,
                        min_value=0.0,
                        max_value=100.0,
                        step=0.1,
                        format="%.1f",
                        key=f"hb_{nonce}",
                    )
                with col_c:
                    cholesterol = st.number_input(
                        "Cholesterol (mg/dL)",
                        value=None,
                        min_value=0.0,
                        max_value=10000.0,
                        step=0.1,
                        format="%.1f",
                        key=f"chol_{nonce}",
                    )

                submitted = st.form_submit_button("Save & Evaluate Patient", type="primary")
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

    with tabs[1]:
        with st.container(border=True):
            st.markdown("#### Clinical Evaluation Guidelines")
            st.write(
                "When demographic and blood panel measurements are saved, the system submits the age and values "
                "to the AI clinical decision-support engine. Patient personal data (name, email, DOB) is strictly isolated."
            )
            st.markdown(
                "- **Glucose Range:** 20.0 to 600.0 mg/dL\n"
                "- **Haemoglobin Range:** 3.0 to 25.0 g/dL\n"
                "- **Cholesterol Range:** 50.0 to 600.0 mg/dL"
            )


elif page == "Records":
    st.title("Patient Records")

    if "action_message" in st.session_state:
        st.success(st.session_state.pop("action_message"))

    search_query = st.text_input(
        "Search records", placeholder="Filter by patient name or email...", key="search_query"
    )

    try:
        patients = list_patients(search=search_query)
    except ApiError as err:
        st.error(err.message)
        patients = []

    total_count = len(patients)
    high_risk_count = sum(1 for p in patients if p.get("risk_level") == "High")
    pending_count = sum(1 for p in patients if p.get("risk_level") == "Pending")
    moderate_risk_count = sum(1 for p in patients if p.get("risk_level") == "Moderate")

    # Stat tiles in a bordered container
    with st.container(border=True):
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Patients", total_count)
        col2.metric("High Risk", high_risk_count)
        col3.metric("Moderate Risk", moderate_risk_count)
        col4.metric("Pending AI", pending_count)

    st.write("")

    if total_count == 0:
        with st.container(border=True):
            if search_query:
                st.info("No patients found matching your search query.")
            else:
                st.info("No patient records yet. Use 'Add patient' from the sidebar to create one.")
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

            with st.container(border=True):
                head_col, badge_col = st.columns([3, 1])
                with head_col:
                    st.subheader(f"Selected Record: {selected_patient['full_name']}")
                with badge_col:
                    render_risk_badge(selected_patient.get("risk_level", "Pending"))

                v1, v2, v3, v4 = st.columns(4)
                v1.metric("Date of Birth", selected_patient["date_of_birth"])
                v2.metric("Glucose", f"{selected_patient['glucose']} mg/dL")
                v3.metric("Haemoglobin", f"{selected_patient['haemoglobin']} g/dL")
                v4.metric("Cholesterol", f"{selected_patient['cholesterol']} mg/dL")

                st.markdown("**Clinical Evaluation & AI Remarks:**")
                st.info(selected_patient["remarks"] or "No remarks recorded.")

                col_edit, col_rerun, col_del = st.columns(3)
                with col_edit:
                    if st.button(
                        "Edit Record",
                        key=f"btn_edit_{selected_patient['id']}",
                        use_container_width=True,
                    ):
                        st.session_state.edit_id = selected_patient["id"]
                        st.rerun()

                with col_rerun:
                    if st.button(
                        "Re-run Prediction",
                        key=f"btn_rerun_{selected_patient['id']}",
                        use_container_width=True,
                    ):
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
                    if st.button(
                        "Delete Record",
                        type="primary",
                        key=f"btn_del_{selected_patient['id']}",
                        use_container_width=True,
                    ):
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
            with st.container(border=True):
                st.subheader(f"Edit Patient: {target_patient['full_name']}")
                with st.form("edit_patient_form", clear_on_submit=False):
                    c_n, c_d = st.columns([2, 1])
                    with c_n:
                        edit_name = st.text_input("Full name", value=target_patient["full_name"])
                    with c_d:
                        edit_dob = st.text_input(
                            "Date of birth",
                            value=target_patient["date_of_birth"],
                            placeholder="dd/mm/yyyy",
                        )
                    edit_email = st.text_input("Email", value=target_patient["email"])

                    st.markdown("##### Blood Test Values")
                    g_c, h_c, ch_c = st.columns(3)
                    with g_c:
                        edit_glucose = st.number_input(
                            "Glucose (mg/dL)",
                            value=float(target_patient["glucose"]),
                            min_value=0.0,
                            max_value=10000.0,
                            step=0.1,
                            format="%.1f",
                        )
                    with h_c:
                        edit_hb = st.number_input(
                            "Haemoglobin (g/dL)",
                            value=float(target_patient["haemoglobin"]),
                            min_value=0.0,
                            max_value=100.0,
                            step=0.1,
                            format="%.1f",
                        )
                    with ch_c:
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
                        save_submitted = st.form_submit_button(
                            "Save Changes", type="primary", use_container_width=True
                        )
                    with col_cancel:
                        cancel_edit = st.form_submit_button("Cancel", use_container_width=True)

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
