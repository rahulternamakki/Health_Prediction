# Custom CSS string for Clinical Editorial theme (Phase 8 UI Polish)
# This CSS is a fixed string from our code; user data is never placed inside it.

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,400&display=swap');

html, body, [class*="css"] {
    font-family: 'Geist', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    color: #1B1C19;
}

/* Serif display headings */
h1, h2 {
    font-family: 'Newsreader', Georgia, serif !important;
    font-weight: 500 !important;
    letter-spacing: -0.015em !important;
    color: #0F2A24 !important;
}

h3, h4, h5, h6 {
    font-family: 'Geist', sans-serif !important;
    font-weight: 600 !important;
    color: #0F2A24 !important;
}

/* Pill buttons */
.stButton > button {
    border-radius: 9999px !important;
    font-family: 'Geist', sans-serif !important;
    font-weight: 500 !important;
    padding: 0.4rem 1.25rem !important;
    transition: all 0.15s ease-in-out !important;
}

.stButton > button[kind="primary"] {
    background-color: #0F2A24 !important;
    color: #FFFFFF !important;
    border: 1px solid #0F2A24 !important;
}

.stButton > button[kind="primary"]:hover {
    background-color: #194037 !important;
    border-color: #194037 !important;
}

.stButton > button[kind="secondary"] {
    background-color: #FFFFFF !important;
    color: #0F2A24 !important;
    border: 1px solid #E6E2D8 !important;
}

.stButton > button[kind="secondary"]:hover {
    border-color: #2F6F62 !important;
    color: #2F6F62 !important;
}

/* Metric tiles */
[data-testid="stMetric"] {
    background-color: #FFFFFF !important;
    border: 1px solid #E6E2D8 !important;
    border-radius: 12px !important;
    padding: 14px 18px !important;
    box-shadow: 0 1px 3px rgba(15, 42, 36, 0.03) !important;
}

[data-testid="stMetricLabel"] {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.75rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    color: #58605D !important;
}

[data-testid="stMetricValue"] {
    font-family: 'Geist', sans-serif !important;
    font-weight: 700 !important;
    color: #0F2A24 !important;
}

/* Bordered containers (cards) */
[data-testid="stVerticalBlockBorderWrapper"] > div {
    border: 1px solid #E6E2D8 !important;
    border-radius: 14px !important;
    background-color: #FFFFFF !important;
    box-shadow: 0 1px 4px rgba(15, 42, 36, 0.03) !important;
    padding: 18px 22px !important;
}

/* Form input elements */
.stTextInput > div > div > input,
.stNumberInput > div > div > input {
    border-radius: 8px !important;
    border: 1px solid #D5D1C8 !important;
    background-color: #FFFFFF !important;
    font-family: 'Geist', sans-serif !important;
}

.stTextInput > div > div > input:focus,
.stNumberInput > div > div > input:focus {
    border-color: #2F6F62 !important;
    box-shadow: 0 0 0 1px #2F6F62 !important;
}

/* Dataframe container */
[data-testid="stDataFrame"] {
    border-radius: 10px !important;
    border: 1px solid #E6E2D8 !important;
    overflow: hidden !important;
}

/* Clean sidebar */
[data-testid="stSidebar"] {
    background-color: #FFFFFF !important;
    border-right: 1px solid #E6E2D8 !important;
}

/* Tabs styling */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
}

.stTabs [data-baseweb="tab"] {
    font-family: 'Geist', sans-serif !important;
    font-weight: 500 !important;
    border-radius: 6px !important;
    padding: 8px 16px !important;
}

/* Custom fixed static components */
.disclaimer-banner {
    background-color: #EBF3F1;
    border: 1px solid #C4DCD6;
    border-radius: 10px;
    padding: 10px 16px;
    color: #0F2A24;
    font-size: 0.85rem;
    margin-bottom: 1.25rem;
    display: flex;
    align-items: center;
    gap: 8px;
}

.brand-badge {
    display: inline-block;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    background-color: #E4EFEA;
    color: #2F6F62;
    padding: 3px 8px;
    border-radius: 9999px;
    margin-bottom: 0.5rem;
}
"""
