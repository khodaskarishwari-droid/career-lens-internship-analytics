from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import re

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="CareerLens | Career Intelligence",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_FILE = DATA_DIR / "internships.csv"

COLUMNS = [
    "ID", "Company", "Role", "Status", "Required Skills",
    "Applied Date", "Follow-up Date", "Job URL", "Notes"
]
STATUSES = ["Interested", "Applied", "Assessment", "Interview", "Offer", "Rejected", "Withdrawn"]
DATE_FORMAT = "%Y-%m-%d"

SAMPLE_DATA = [
    ["CL-1001", "TechNova (Sample)", "Data Analyst Intern", "Applied", "Python, SQL, Power BI", "2026-10-12", "2026-10-26", "https://example.com", "Sample record — replace with a real opportunity."],
    ["CL-1002", "DataBridge (Sample)", "Python Developer Intern", "Interview", "Python, Git, APIs", "2026-10-08", "2026-10-24", "https://example.com", "Sample record — prepare project examples."],
    ["CL-1003", "CloudSpark (Sample)", "Data Analyst Intern", "Applied", "SQL, Excel, Power BI", "2026-10-15", "2026-10-29", "https://example.com", "Sample record — review the job description."],
    ["CL-1004", "InsightWorks (Sample)", "ML Intern", "Rejected", "Python, Pandas, Scikit-learn", "2026-10-02", "", "https://example.com", "Sample record — note skills to strengthen."],
    ["CL-1005", "NextGen Labs (Sample)", "Data Intern", "Offer", "Python, SQL, Excel", "2026-09-29", "", "https://example.com", "Sample record — review offer details carefully."],
]

# ---------- Data layer: kept separate so it can be tested ----------
def normalize_skill(skill: str) -> str:
    """Normalize skill labels for case-insensitive matching."""
    return " ".join(str(skill).strip().casefold().split())


def parse_skills(text: str) -> list[str]:
    """Split comma-separated skills, remove blanks and duplicates."""
    output, seen = [], set()
    for part in str(text or "").split(","):
        cleaned = " ".join(part.strip().split())
        key = normalize_skill(cleaned)
        if key and key not in seen:
            output.append(cleaned)
            seen.add(key)
    return output


def calculate_skill_match(owned_skills, required_text: str) -> dict:
    required = parse_skills(required_text)
    owned = {normalize_skill(s) for s in owned_skills if normalize_skill(s)}
    matched = [s for s in required if normalize_skill(s) in owned]
    missing = [s for s in required if normalize_skill(s) not in owned]
    score = len(matched) / len(required) if required else 0.0
    return {"required": required, "matched": matched, "missing": missing, "score": score}



def calculate_metrics(data: pd.DataFrame) -> dict:
    """Calculate application overview metrics safely."""
    total = len(data)

    status = (
        data["Status"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    applied = int(
        status.isin([
            "Applied",
            "Assessment",
            "Interview",
            "Offer",
            "Rejected",
            "Withdrawn",
        ]).sum()
    )

    interviews = int((status == "Interview").sum())
    offers = int((status == "Offer").sum())
    rejected = int((status == "Rejected").sum())

    closed = int(
        status.isin(["Offer", "Rejected", "Withdrawn"]).sum()
    )

    response_rate = (
        (closed + interviews) * 100 / applied
        if applied
        else 0.0
    )

    # Multiply before dividing to match the test's expected
    # floating-point calculation: 100 / 3.
    offer_rate = (
        offers * 100 / applied
        if applied
        else 0.0
    )

    return {
        "total": total,
        "applied": applied,
        "interviews": interviews,
        "offers": offers,
        "rejected": rejected,
        "response_rate": response_rate,
        "offer_rate": offer_rate,
    }


def empty_data() -> pd.DataFrame:
    return pd.DataFrame(columns=COLUMNS)


def validate_data(data: pd.DataFrame) -> pd.DataFrame:
    """Return a clean dataframe with the expected columns and normalized fields."""
    frame = data.copy()
    for col in COLUMNS:
        if col not in frame.columns:
            frame[col] = ""
    frame = frame[COLUMNS].fillna("").copy()
    for col in COLUMNS:
        frame[col] = frame[col].astype(str).str.strip()
    frame["Status"] = frame["Status"].where(frame["Status"].isin(STATUSES), "Interested")
    frame = frame[frame["Company"].str.strip().ne("") & frame["Role"].str.strip().ne("")]
    return frame.reset_index(drop=True)


def load_data(path: Path = DATA_FILE) -> pd.DataFrame:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        pd.DataFrame(SAMPLE_DATA, columns=COLUMNS).to_csv(path, index=False)
    try:
        frame = pd.read_csv(path, dtype=str).fillna("")
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return empty_data()
    return validate_data(frame)


def save_data(data: pd.DataFrame, path: Path = DATA_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    validate_data(data).to_csv(path, index=False)


def generate_id(data: pd.DataFrame) -> str:
    existing = set(data.get("ID", pd.Series(dtype=str)).astype(str))
    number = 1001
    while f"CL-{number}" in existing:
        number += 1
    return f"CL-{number}"


def upcoming_followups(data: pd.DataFrame, today: date | None = None) -> pd.DataFrame:
    """Return non-closed applications with follow-up due today or earlier."""
    today = today or date.today()

    if data.empty:
        return data.copy()

    frame = data.copy()
    frame["_followup"] = pd.to_datetime(
        frame["Follow-up Date"], errors="coerce"
    )

    today_timestamp = pd.Timestamp(today)

    open_status = ~frame["Status"].isin(["Offer", "Rejected", "Withdrawn"])
    due = frame["_followup"].notna() & (
        frame["_followup"] <= today_timestamp
    )

    result = frame[open_status & due].drop(columns=["_followup"])
    return result.reset_index(drop=True)

def skill_frequency(data: pd.DataFrame) -> pd.DataFrame:
    counts: dict[str, int] = {}
    for text in data.get("Required Skills", pd.Series(dtype=str)).fillna(""):
        for skill in parse_skills(text):
            counts[skill] = counts.get(skill, 0) + 1
    return pd.DataFrame(
        sorted([{"Skill": k, "Opportunities": v} for k, v in counts.items()],
               key=lambda row: (-row["Opportunities"], row["Skill"].casefold())),
        columns=["Skill", "Opportunities"],
    )



# ---------- Visual design ----------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@400;600;700;800&display=swap');

:root {
    --ink: #F3F6FF;
    --muted: #A8B4CC;
    --panel: #101B30;
    --line: #293B56;
    --orange: #FF8A32;
    --violet: #8B7CFF;
    --cyan: #63D9F5;
}

.stApp {
    background:
        radial-gradient(ellipse at 85% 0%, #202A52 0%, transparent 40%),
        radial-gradient(ellipse at 0% 100%, #17213A 0%, transparent 35%),
        linear-gradient(135deg, #080D19, #0A1020 60%, #080D19);
    color: var(--ink);
    font-family: 'DM Sans', sans-serif;
}

.block-container {
    max-width: 1580px;
    padding: 1.5rem 2rem 3rem;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0B1323, #090E1B);
    border-right: 1px solid #26344B;
}

[data-testid="stSidebar"] > div {
    padding-top: 1.5rem;
}

h1, h2, h3 {
    font-family: 'Manrope', sans-serif !important;
    letter-spacing: -0.5px;
    color: #FFFFFF;
}

h1 {
    font-weight: 800 !important;
}

h2, h3 {
    font-weight: 700 !important;
}

p, label, .stCaption {
    color: #D3DCEC;
}

[data-testid="stMetric"] {
    background: linear-gradient(145deg, #172640, #0D1729);
    border: 1px solid #2A3D59;
    border-radius: 18px;
    padding: 18px 20px;
    min-height: 120px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.16);
    transition: border-color 0.2s ease, transform 0.2s ease;
}

[data-testid="stMetric"]:hover {
    border-color: #8B7CFF;
    transform: translateY(-2px);
}

[data-testid="stMetricLabel"] {
    color: #B9C6DC !important;
    font-size: 0.9rem !important;
}

[data-testid="stMetricValue"] {
    color: #FFFFFF !important;
    font-family: 'Manrope', sans-serif;
    font-weight: 800;
}

.hero {
    padding: 30px;
    border: 1px solid #394B73;
    border-radius: 24px;
    background:
        radial-gradient(ellipse at 90% 20%, rgba(139, 124, 255, 0.22), transparent 45%),
        linear-gradient(115deg, rgba(24, 43, 73, 0.98), rgba(26, 35, 70, 0.94), rgba(44, 34, 75, 0.86));
    margin-bottom: 24px;
    position: relative;
    overflow: hidden;
    box-shadow: 0 18px 50px rgba(0, 0, 0, 0.22);
    transition: border-color 0.25s ease;
}

.hero:hover {
    border-color: #7165C7;
}

.hero:after {
    content: '↗';
    position: absolute;
    right: 28px;
    top: 10px;
    font-size: 100px;
    color: rgba(99, 217, 245, 0.12);
    font-weight: 800;
    pointer-events: none;
}

.hero-kicker {
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 2.5px;
    color: #B8ADFF;
    text-transform: uppercase;
}

.hero-title {
    font-family: 'Manrope', sans-serif;
    font-size: clamp(28px, 3vw, 43px);
    font-weight: 800;
    line-height: 1.16;
    color: #FFFFFF;
    margin: 10px 0;
}

.hero-copy {
    max-width: 760px;
    color: #D0DAEA;
    font-size: 15px;
    line-height: 1.8;
}

.section-card {
    border: 1px solid #293B56;
    background: linear-gradient(145deg, rgba(18, 30, 52, 0.96), rgba(10, 18, 32, 0.96));
    border-radius: 18px;
    padding: 20px;
    box-shadow: 0 10px 28px rgba(0, 0, 0, 0.12);
    transition: border-color 0.2s ease, transform 0.2s ease;
}

.section-card:hover {
    border-color: #526B91;
    transform: translateY(-2px);
}

div.stButton > button,
div.stDownloadButton > button {
    border-radius: 11px;
    border: 1px solid #A69BFF;
    background: linear-gradient(110deg, #7465E8, #8B7CFF);
    color: #FFFFFF;
    font-weight: 700;
    min-height: 42px;
    transition: all 0.2s ease;
}

div.stButton > button:hover,
div.stDownloadButton > button:hover {
    border-color: #C5BEFF;
    color: #FFFFFF;
    filter: brightness(1.1);
    box-shadow: 0 5px 18px rgba(139, 124, 255, 0.22);
}

.stTextInput input,
.stTextArea textarea,
.stDateInput input,
.stSelectbox div[data-baseweb="select"] {
    border-radius: 10px;
}

.stTextInput input:focus,
.stTextArea textarea:focus {
    border-color: #8B7CFF;
    box-shadow: 0 0 0 2px rgba(139, 124, 255, 0.18);
}

div[data-testid="stDataFrame"] {
    border: 1px solid #293B56;
    border-radius: 14px;
    overflow: hidden;
}

div[data-testid="stTabs"] button {
    font-weight: 600;
}

div[data-testid="stTabs"] button[aria-selected="true"] {
    color: #B8ADFF;
}

a {
    color: #8FE7FF !important;
}

.small-muted {
    color: #A8B4CC;
    font-size: 12px;
}

hr {
    border-color: #26344B;
}

@media (max-width: 768px) {
    .block-container {
        padding: 1rem 1rem 2rem;
    }

    .hero {
        padding: 22px 18px;
        border-radius: 18px;
    }

    .hero-title {
        font-size: 28px;
    }

    [data-testid="stMetric"] {
        padding: 14px;
        min-height: 100px;
    }
}

@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
        transition: none !important;
        animation: none !important;
    }
}
</style>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown("<div style='font-size:30px;font-weight:800;color:#fff'>🎯 Career<span style='color:#FF8A32'>Lens</span></div>", unsafe_allow_html=True)
    st.caption("YOUR CAREER. YOUR LENS. YOUR FUTURE.")
    st.divider()
    page = st.radio("NAVIGATION", ["Overview", "Application Manager", "Skill Match", "Career Insights", "Action Center", "About & Help"], label_visibility="visible")
    st.divider()
    data = load_data()
    st.metric("Tracked opportunities", len(data))
    st.markdown("<div class='small-muted'>Build momentum with one intentional step every day.</div>", unsafe_allow_html=True)
    st.divider()
    st.markdown("**TODAY'S FOCUS**")
    due_count = len(upcoming_followups(data))
    st.write(f"📨 {due_count} follow-up(s) due")
    st.write("🎯 Review one missing skill")
    st.write("⏱️ Spend 20 minutes learning")

# Top strip
top_a, top_b = st.columns([3, 1])
with top_a:
    st.caption(f"CAREER INTELLIGENCE PLATFORM  •  {date.today().strftime('%d %b %Y')}")
with top_b:
    st.download_button("⬇ Export all data", data=data.to_csv(index=False).encode("utf-8"), file_name="careerlens_applications.csv", mime="text/csv", use_container_width=True)

st.markdown("""
<div class="hero">
  <div class="hero-kicker">YOUR CAREER, WITH CLARITY</div>
  <div class="hero-title">Small steps today.<br>Better opportunities tomorrow.</div>
  <div class="hero-copy">A personal workspace to organize applications, understand skill gaps, and turn your job search into a measurable plan. Your records stay in your local CSV file.</div>
</div>
""", unsafe_allow_html=True)

# Main pages
if page == "Overview":
    m = calculate_metrics(data)
    st.subheader("📊 Your Career Command Center")
    st.caption("A practical snapshot of your internship journey.")
    cols = st.columns(5)
    metrics = [
        ("Total opportunities", m["total"], "All tracked records"),
        ("Active applications", m["applied"], "Excludes interested-only"),
        ("Interviews", m["interviews"], "Prepare and follow up"),
        ("Offers", m["offers"], "Celebrate progress"),
        ("Offer rate", f'{m["offer_rate"]:.1f}%', "Offers / active applications"),
    ]
    for col, (label, value, help_text) in zip(cols, metrics):
        col.metric(label, value, help=help_text)

    left, right = st.columns([1.15, 1])
    with left:
        st.markdown("#### Application status")
        if data.empty:
            st.info("Add your first opportunity in Application Manager.")
        else:
            status_counts = data["Status"].value_counts().rename_axis("Status").reset_index(name="Applications")
            fig = px.pie(status_counts, names="Status", values="Applications", hole=.64,
                         color_discrete_sequence=["#FF8A32","#4F8CFF","#8B5CF6","#20C997","#F43F5E","#FACC15","#64748B"])
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                              font_color="#EAF0FC", margin=dict(t=10,b=10,l=5,r=5),
                              legend_title_text="", height=320)
            fig.update_traces(textposition="inside", textinfo="percent")
            st.plotly_chart(fig, use_container_width=True)
    with right:
        st.markdown("#### Application pipeline")
        pipeline_order = ["Interested", "Applied", "Assessment", "Interview", "Offer", "Rejected", "Withdrawn"]
        pipeline = data["Status"].value_counts().reindex(pipeline_order, fill_value=0).rename_axis("Stage").reset_index(name="Count")
        fig = px.funnel(pipeline[pipeline["Count"] > 0], x="Count", y="Stage",
                        color="Stage", color_discrete_sequence=["#4F8CFF","#FF8A32","#FACC15","#8B5CF6","#20C997","#F43F5E","#64748B"])
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          font_color="#EAF0FC", showlegend=False, margin=dict(t=10,b=10,l=5,r=5), height=320)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### 🔥 Next best actions")
    due = upcoming_followups(data)
    a, b, c = st.columns(3)
    with a:
        st.markdown("<div class='section-card'><b>📨 Follow up thoughtfully</b><p class='small-muted'>Review applications whose follow-up date is today or overdue.</p></div>", unsafe_allow_html=True)
        st.metric("Follow-ups due", len(due))
    with b:
        st.markdown("<div class='section-card'><b>🧠 Strengthen your fit</b><p class='small-muted'>Use Skill Match to compare your current skills with a target role.</p></div>", unsafe_allow_html=True)
        st.metric("Distinct requested skills", len(skill_frequency(data)))
    with c:
        st.markdown("<div class='section-card'><b>📈 Keep your pipeline active</b><p class='small-muted'>Track progress consistently; do not treat the sample data as real outcomes.</p></div>", unsafe_allow_html=True)
        st.metric("Rejected applications", m["rejected"])

    if not data.empty:
        st.markdown("#### Recently tracked")
        recent = data.tail(5).iloc[::-1][["Company", "Role", "Status", "Applied Date", "Follow-up Date"]]
        st.dataframe(recent, use_container_width=True, hide_index=True)

elif page == "Application Manager":
    st.subheader("🗂️ Application Manager")
    st.write("Add, search, update, and remove opportunities. Save meaningful notes and follow-up dates.")
    with st.expander("＋ Add a new opportunity", expanded=True):
        with st.form("add_application", clear_on_submit=True):
            c1, c2 = st.columns(2)
            company = c1.text_input("Company *")
            role = c2.text_input("Role *")
            c3, c4 = st.columns(2)
            status = c3.selectbox("Status", STATUSES, index=1)
            applied_date = c4.date_input("Applied / saved date", value=date.today())
            c5, c6 = st.columns(2)
            follow_date = c5.date_input("Follow-up date (optional)", value=None, key="new_follow_date")
            job_url = c6.text_input("Job URL (optional)", placeholder="https://...")
            skills = st.text_input("Required skills (comma-separated)", placeholder="Python, SQL, Power BI")
            notes = st.text_area("Notes / next step", placeholder="Recruiter name, interview prep, application reference...")
            submitted = st.form_submit_button("Save opportunity", use_container_width=True)
            if submitted:
                if not company.strip() or not role.strip():
                    st.error("Company and role are required.")
                elif job_url.strip() and not re.match(r"^https?://", job_url.strip(), re.I):
                    st.error("Job URL must start with http:// or https://.")
                elif ((data["Company"].str.casefold() == company.strip().casefold()) &
                      (data["Role"].str.casefold() == role.strip().casefold()) &
                      (~data["Status"].isin(["Rejected", "Withdrawn"]))).any():
                    st.warning("A similar open application already exists. Check the records before adding a duplicate.")
                else:
                    row = {
                        "ID": generate_id(data), "Company": company.strip(), "Role": role.strip(),
                        "Status": status, "Required Skills": ", ".join(parse_skills(skills)),
                        "Applied Date": applied_date.isoformat(),
                        "Follow-up Date": follow_date.isoformat() if follow_date else "",
                        "Job URL": job_url.strip(), "Notes": notes.strip()
                    }
                    save_data(pd.concat([data, pd.DataFrame([row])], ignore_index=True))
                    st.success("Opportunity saved.")
                    st.rerun()

    st.markdown("#### Your opportunities")
    q1, q2 = st.columns([2, 1])
    search = q1.text_input("Search company, role, or skills")
    status_filter = q2.selectbox("Filter by status", ["All"] + STATUSES)
    view = data.copy()
    if search.strip():
        pattern = re.escape(search.strip())
        view = view[view[["Company", "Role", "Required Skills"]].apply(
            lambda col: col.str.contains(pattern, case=False, na=False)).any(axis=1)]
    if status_filter != "All":
        view = view[view["Status"] == status_filter]
    st.dataframe(view, use_container_width=True, hide_index=True)
    if not view.empty:
        ids = view["ID"].tolist()
        chosen_id = st.selectbox("Choose an application to edit or delete", ids,
                                 format_func=lambda x: f"{x} · {view.loc[view['ID'] == x, 'Company'].iloc[0]} — {view.loc[view['ID'] == x, 'Role'].iloc[0]}")
        selected = data[data["ID"] == chosen_id].iloc[0]
        with st.expander("✏️ Edit selected opportunity"):
            with st.form("edit_application"):
                ec1, ec2 = st.columns(2)
                ecompany = ec1.text_input("Company", value=selected["Company"])
                erole = ec2.text_input("Role", value=selected["Role"])
                ec3, ec4 = st.columns(2)
                estatus = ec3.selectbox("Status", STATUSES, index=STATUSES.index(selected["Status"]) if selected["Status"] in STATUSES else 0)
                eapplied = ec4.date_input("Applied date", value=pd.to_datetime(selected["Applied Date"], errors="coerce").date() if pd.notna(pd.to_datetime(selected["Applied Date"], errors="coerce")) else date.today())
                efollow_raw = pd.to_datetime(selected["Follow-up Date"], errors="coerce")
                efollow_default = efollow_raw.date() if pd.notna(efollow_raw) else None
                efollow = st.date_input("Follow-up date (optional)", value=efollow_default, key="edit_follow_date")
                eurl = st.text_input("Job URL", value=selected["Job URL"])
                eskills = st.text_input("Required skills", value=selected["Required Skills"])
                enotes = st.text_area("Notes", value=selected["Notes"])
                save_edit = st.form_submit_button("Save changes")
                if save_edit:
                    if not ecompany.strip() or not erole.strip():
                        st.error("Company and role are required.")
                    elif eurl.strip() and not re.match(r"^https?://", eurl.strip(), re.I):
                        st.error("Job URL must start with http:// or https://.")
                    else:
                        updated = data.copy()
                        idx = updated.index[updated["ID"] == chosen_id][0]
                        updated.loc[idx, ["Company","Role","Status","Applied Date","Follow-up Date","Job URL","Required Skills","Notes"]] = [
                            ecompany.strip(), erole.strip(), estatus, eapplied.isoformat(),
                            efollow.isoformat() if efollow else "", eurl.strip(),
                            ", ".join(parse_skills(eskills)), enotes.strip()
                        ]
                        save_data(updated)
                        st.success("Changes saved.")
                        st.rerun()
        with st.expander("🗑️ Delete selected opportunity"):
            st.warning("Deletion permanently removes this row from the local CSV. Export a backup first if needed.")
            confirm = st.checkbox("I understand this record will be deleted.", key="confirm_delete")
            if st.button("Delete selected record", disabled=not confirm):
                save_data(data[data["ID"] != chosen_id])
                st.success("Record deleted.")
                st.rerun()
    else:
        st.info("No records match your filters.")

elif page == "Skill Match":
    st.subheader("🧠 Skill Match Lab")
    st.write("Compare your skills with a role's requirements. This is a transparent overlap score, not a prediction of hiring success.")
    known = ["Python","SQL","Excel","Power BI","Tableau","Pandas","NumPy","Matplotlib","Statistics","Machine Learning","Scikit-learn","Deep Learning","NLP","TensorFlow","PyTorch","Git","GitHub","APIs","AWS","MongoDB","OOP","Java","JavaScript","HTML","CSS","Communication","Problem Solving","Data Cleaning","Data Storytelling"]
    your_skills = st.multiselect("Skills you currently know", known, default=["Python","SQL"], accept_new_options=True)
    target = st.selectbox("Choose requirements from a tracked opportunity", ["Custom requirements"] + data["ID"].tolist(),
                          format_func=lambda x: x if x == "Custom requirements" else f"{x} · {data.loc[data['ID']==x,'Company'].iloc[0]} — {data.loc[data['ID']==x,'Role'].iloc[0]}")
    default_req = "Python, SQL, Pandas, Power BI"
    if target != "Custom requirements":
        default_req = data.loc[data["ID"] == target, "Required Skills"].iloc[0]
    requirements = st.text_area("Required skills (comma-separated)", value=default_req, key=f"req_{target}")
    if st.button("Analyze skill fit", type="primary"):
        result = calculate_skill_match(your_skills, requirements)
        if not result["required"]:
            st.warning("Enter at least one required skill.")
        else:
            left, right = st.columns([1, 1.5])
            with left:
                st.metric("Skill overlap", f'{result["score"]*100:.1f}%')
                st.progress(result["score"])
                st.caption(f'{len(result["matched"])} of {len(result["required"])} unique skills matched.')
            with right:
                st.markdown("#### Skill breakdown")
                x, y = st.columns(2)
                x.success("Matched")
                for skill in result["matched"] or ["No matched skills yet"]:
                    x.write(f"✅ {skill}" if result["matched"] else skill)
                y.warning("Skills to develop")
                for skill in result["missing"] or ["No gaps in the entered list"]:
                    y.write(f"🎯 {skill}" if result["missing"] else skill)
            if result["missing"]:
                st.markdown("#### Suggested learning plan")
                for i, skill in enumerate(result["missing"], 1):
                    st.write(f"**{i}. {skill}** — learn the basics, practise one small task, then document a mini-project.")
            st.caption("Limitations: matching is based on text labels only; it does not assess depth, experience, or employer preferences.")

elif page == "Career Insights":
    st.subheader("📈 Career Insights")
    st.write("Discover patterns in the opportunities you have recorded.")
    if data.empty:
        st.info("Add opportunities to unlock insights.")
    else:
        freq = skill_frequency(data)
        l, r = st.columns(2)
        with l:
            st.markdown("#### Most requested skills")
            if not freq.empty:
                fig = px.bar(freq.head(10).sort_values("Opportunities"), x="Opportunities", y="Skill", orientation="h",
                             color="Opportunities", color_continuous_scale=["#334155","#FF8A32"])
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#EAF0FC",
                                  coloraxis_showscale=False, margin=dict(t=10,b=10,l=5,r=5), height=380)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No required skills recorded.")
        with r:
            st.markdown("#### Status by opportunity")
            counts = data["Status"].value_counts().rename_axis("Status").reset_index(name="Count")
            fig = px.bar(counts, x="Status", y="Count", color="Status",
                         color_discrete_sequence=["#FF8A32","#4F8CFF","#8B5CF6","#20C997","#F43F5E","#FACC15","#64748B"])
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#EAF0FC",
                              showlegend=False, margin=dict(t=10,b=10,l=5,r=5), height=380)
            st.plotly_chart(fig, use_container_width=True)
        st.markdown("#### Data quality snapshot")
        d1, d2, d3 = st.columns(3)
        d1.metric("Records with a job URL", int(data["Job URL"].str.startswith(("http://","https://")).sum()))
        d2.metric("Records with skills listed", int(data["Required Skills"].str.strip().ne("").sum()))
        d3.metric("Records with notes", int(data["Notes"].str.strip().ne("").sum()))
        st.caption("Insights describe your saved records; they do not establish labour-market demand beyond your sample.")

elif page == "Action Center":
    st.subheader("🧭 Action Center")
    st.write("A simple daily checklist based on your saved records. Dates are reminders you manage, not messages sent automatically.")
    due = upcoming_followups(data)
    if due.empty:
        st.success("No follow-ups are due today or overdue. Add a follow-up date when you apply.")
    else:
        st.markdown("#### Follow-ups due")
        st.dataframe(due[["Company","Role","Status","Follow-up Date","Job URL","Notes"]], use_container_width=True, hide_index=True)
    st.markdown("#### Suggested weekly routine")
    st.markdown("""
    - **Review (15 min):** update the status of every active application.
    - **Follow up (15 min):** check the company's stated process and send a polite message when appropriate.
    - **Practise (30 min):** choose one missing skill and complete a small exercise.
    - **Reflect (10 min):** record what worked and the next action.
    """)
    st.info("CareerLens currently stores data locally in a CSV. It does not send emails, scrape job sites, or guarantee interviews.")

elif page == "About & Help":
    st.subheader("✨ About CareerLens")
    st.write("CareerLens is a student-focused internship tracking and career-planning dashboard. It brings application records, skill overlap analysis, and simple action reminders into one workspace.")
    st.markdown("#### Technology stack")
    st.markdown("- **Python:** business logic and validation\n- **Streamlit:** interactive web interface\n- **Pandas:** data cleaning and analysis\n- **Plotly:** interactive visualizations\n- **CSV:** local persistence and export\n- **pytest:** automated unit tests\n- **Git/GitHub:** version control and collaboration")
    st.markdown("#### How it works")
    st.markdown("You enter records → Python validates fields → Pandas stores and analyzes rows → metrics and charts summarize the records → the Action Center helps you plan your next step.")
    st.markdown("#### Privacy and limitations")
    st.markdown("- Data is stored in `data/internships.csv` on the machine/server running this app.\n- Do not enter passwords, sensitive personal information, or private recruiter details.\n- Sample rows are labelled and should be replaced with your own records.\n- Skill match is simple text overlap, not an AI hiring prediction.\n- CSV storage is appropriate for a learning project; a public multi-user deployment should add authentication, a database, access controls, and a privacy policy.")
    st.markdown("#### Run locally")
    st.code("python -m pip install -r requirements.txt\npython -m streamlit run app.py", language="bash")
    st.markdown("#### Project repository")
    st.markdown("Add your repository URL here: `https://github.com/khodaskarishwari-droid/career-lens-internship-analytics`")
    st.caption("Replace demo records with real opportunities before using analytics to make personal decisions.")
