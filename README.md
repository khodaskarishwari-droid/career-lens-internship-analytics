# CareerLens — Internship & Career Intelligence Dashboard

CareerLens is a student-focused Streamlit app for tracking internship applications, comparing a student's skills with a role's requirements, exploring patterns in saved applications, and reviewing follow-ups.

## Features
- Overview KPI cards, application-status donut chart, and pipeline visualization
- Add, search, filter, edit, and delete internship records
- Required-skill overlap score with matched/missing skill breakdown
- Requested-skill frequency and application data-quality insights
- Follow-up action center based on dates recorded by the user
- CSV persistence, filtered records view, and data export
- Input validation, duplicate warning, and automated unit tests

## Tech stack
Python, Streamlit, Pandas, Plotly, CSV, pytest, Git/GitHub.

## Run locally (Windows)
```bat
cd /d C:\Users\User\Documents\career-lens-internship-analytics
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

If you already have a `.venv`, activate it and install requirements rather than recreating it.

## Run tests
```bat
python -m pytest -v
```

The test module imports functions from `app.py`; the app's Streamlit page code also runs on import. If your local test environment reports Streamlit runtime warnings, check that the tests still pass and consider moving the pure data functions into a separate `careerlens_core.py` module for a cleaner production architecture.

## Data
Records are stored in `data/internships.csv`. The app creates clearly labelled demo rows on first run. Export a backup before deleting records. The CSV is local to the machine running the app; do not enter sensitive information.

## Important limitations
- Skill matching is text-based overlap, not a measurement of proficiency or a prediction of hiring.
- Follow-up dates are reminders only; no emails are sent.
- Sample records are illustrative, not real employer data.
- CSV storage is suitable for a student portfolio prototype. A real multi-user public deployment should use authentication, a database, authorization, secure secrets, backups, and a privacy policy.

## Suggested evidence for assessment
1. Screenshot of each page and its working controls.
2. Successful output of `python -m pytest -v`.
3. A short demo showing add/edit/filter/delete and CSV export.
4. GitHub commits showing incremental development.
5. A report describing design decisions, testing evidence, limitations, and future work.

## Repository
https://github.com/khodaskarishwari-droid/career-lens-internship-analytics
