"""Jira / Atlassian Design System (ADS) UI Theme & Component Helpers for ResolveAI."""

from __future__ import annotations

from datetime import datetime
import streamlit as st

CUSTOM_CSS = """
<style>
/* ==========================================================================
   ATLASSIAN DESIGN SYSTEM (ADS) / JIRA CLOUD GLOBAL STYLES
   ========================================================================== */
@import url('https://fonts.googleapis.com/css2?family=Charlie+Text:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, 'Fira Sans', 'Droid Sans', 'Helvetica Neue', sans-serif !important;
    color: #172B4D !important;
}

/* Jira Canvas / Main Layout */
.main, .stApp {
    background-color: #FAFBFC !important; /* Jira background canvas */
}

.main .block-container {
    max-width: 1240px;
    padding-top: 1.5rem;
    padding-bottom: 3rem;
    padding-left: 2.25rem;
    padding-right: 2.25rem;
}

/* Headings */
h1, h2, h3, h4, h5, h6 {
    color: #172B4D !important; /* Jira dark slate */
    font-weight: 600 !important;
    letter-spacing: -0.01em !important;
}

/* Paragraphs & Markdown */
p, span, div, li {
    color: #172B4D;
}

/* ==========================================================================
   JIRA CLOUD LEFT NAVIGATION SIDEBAR
   ========================================================================== */
section[data-testid="stSidebar"] {
    background-color: #0747A6 !important; /* Authentic Atlassian Deep Blue */
    color: #DEEBFF !important;
    border-right: 1px solid #0C2B64 !important;
}

section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] div {
    color: #DEEBFF;
}

/* Sidebar navigation links */
section[data-testid="stSidebar"] div[data-testid="stSidebarNav"] {
    padding-top: 0.25rem;
}

section[data-testid="stSidebar"] div[data-testid="stSidebarNav"] a {
    color: #DEEBFF !important;
    border-radius: 3px !important;
    padding: 0.5rem 0.75rem !important;
    font-size: 0.875rem !important;
    font-weight: 500 !important;
    margin-bottom: 2px !important;
    transition: background-color 0.1s ease-in-out, color 0.1s ease-in-out !important;
}

section[data-testid="stSidebar"] div[data-testid="stSidebarNav"] a:hover {
    color: #FFFFFF !important;
    background-color: rgba(9, 30, 66, 0.48) !important;
}

section[data-testid="stSidebar"] div[data-testid="stSidebarNav"] a[aria-current="page"] {
    color: #FFFFFF !important;
    background-color: rgba(9, 30, 66, 0.72) !important;
    border-left: 3px solid #00B8D9 !important; /* Jira Teal Active Indicator */
    font-weight: 600 !important;
}

/* Jira Project / User Profile Card in Sidebar */
.jira-sidebar-project {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.5rem 0 1rem 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.15);
    margin-bottom: 0.85rem;
}

.jira-project-icon {
    width: 32px;
    height: 32px;
    border-radius: 4px;
    background: #0052CC;
    border: 1px solid rgba(255, 255, 255, 0.25);
    display: flex;
    align-items: center;
    justify-content: center;
    color: #FFFFFF;
    font-weight: 700;
    font-size: 1rem;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
}

.user-profile-badge {
    background: rgba(9, 30, 66, 0.48);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 4px;
    padding: 0.75rem 0.85rem;
    margin-bottom: 1rem;
}

.user-profile-name {
    color: #FFFFFF !important;
    font-weight: 600;
    font-size: 0.9rem;
    margin: 0;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.user-profile-role {
    color: #B3D4FF !important;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-weight: 500;
    margin-top: 0.2rem;
}

/* ==========================================================================
   USER-FRIENDLY JIRA INPUT FIELDS & FORM CONTROLS (FULL OVERRIDE)
   ========================================================================== */

/* Input Labels */
label[data-testid="stWidgetLabel"],
label[data-testid="stWidgetLabel"] p,
div[data-testid="stWidgetLabel"] p {
    font-size: 12px !important;
    font-weight: 600 !important;
    color: #5E6C84 !important; /* Jira N200 label grey */
    letter-spacing: 0.01em !important;
    margin-bottom: 4px !important;
    text-transform: none !important;
}

/* BaseWeb Input & Textarea Containers - RESTING STATE */
div[data-baseweb="input"],
div[data-baseweb="base-input"],
div[data-baseweb="textarea"] {
    background-color: #FAFBFC !important; /* Clean Jira neutral resting bg */
    border: 1px solid #DFE1E6 !important; /* Subtle Jira border */
    border-radius: 3px !important;
    transition: background-color 0.15s ease-in-out, border-color 0.15s ease-in-out, box-shadow 0.15s ease-in-out !important;
}

/* Inner containers that BaseWeb creates */
div[data-baseweb="input"] > div,
div[data-baseweb="base-input"] > div,
div[data-baseweb="textarea"] > div {
    background-color: transparent !important;
    border: none !important;
}

/* Text Inputs and Textareas */
div[data-baseweb="input"] input,
div[data-baseweb="base-input"] input,
div[data-baseweb="textarea"] textarea,
.stTextInput input,
.stTextArea textarea {
    background-color: transparent !important;
    color: #172B4D !important; /* High-contrast Jira Dark Slate */
    font-size: 14px !important;
    font-family: inherit !important;
    padding: 8px 10px !important;
    border: none !important;
    outline: none !important;
    caret-color: #0052CC !important;
}

/* Input Placeholders */
div[data-baseweb="input"] input::placeholder,
div[data-baseweb="base-input"] input::placeholder,
div[data-baseweb="textarea"] textarea::placeholder,
.stTextInput input::placeholder,
.stTextArea textarea::placeholder {
    color: #7A869A !important; /* Jira placeholder grey */
    opacity: 1 !important;
    font-size: 13.5px !important;
}

/* INPUT HOVER STATE (Jira signature subtle grey tint on hover) */
div[data-baseweb="input"]:hover,
div[data-baseweb="base-input"]:hover,
div[data-baseweb="textarea"]:hover {
    background-color: #EBECF0 !important;
    border-color: #C1C7D0 !important;
}

/* INPUT FOCUS STATE (Jira signature crisp white bg + Atlassian Blue border & ring) */
div[data-baseweb="input"]:focus-within,
div[data-baseweb="base-input"]:focus-within,
div[data-baseweb="textarea"]:focus-within {
    background-color: #FFFFFF !important;
    border: 2px solid #4C9AFF !important; /* Atlassian Focus Blue */
    box-shadow: 0 0 0 1px #4C9AFF !important;
}

/* SELECTBOX / DROPDOWN CONTROLS */
div[data-baseweb="select"] {
    background-color: #FAFBFC !important;
    border: 1px solid #DFE1E6 !important;
    border-radius: 3px !important;
    transition: all 0.15s ease-in-out !important;
}

div[data-baseweb="select"]:hover {
    background-color: #EBECF0 !important;
    border-color: #C1C7D0 !important;
}

div[data-baseweb="select"]:focus-within {
    background-color: #FFFFFF !important;
    border: 2px solid #4C9AFF !important;
    box-shadow: 0 0 0 1px #4C9AFF !important;
}

div[data-baseweb="select"] * {
    color: #172B4D !important;
    font-size: 14px !important;
}

div[data-baseweb="select"] svg {
    fill: #6B778C !important;
}

/* Select Dropdown Popover Menus */
ul[data-baseweb="menu"],
div[data-baseweb="popover"] {
    background-color: #FFFFFF !important;
    border: 1px solid #DFE1E6 !important;
    border-radius: 4px !important;
    box-shadow: 0 4px 8px -2px rgba(9, 30, 66, 0.25), 0 0 1px rgba(9, 30, 66, 0.31) !important;
}

li[data-baseweb="menu-item"] {
    color: #172B4D !important;
    padding: 8px 12px !important;
    font-size: 13.5px !important;
    transition: background-color 0.1s ease !important;
}

li[data-baseweb="menu-item"]:hover {
    background-color: #EBECF0 !important;
    color: #172B4D !important;
}

li[data-baseweb="menu-item"][aria-selected="true"] {
    background-color: #DEEBFF !important;
    color: #0052CC !important;
    font-weight: 600 !important;
}

/* CHAT INPUT FIELD */
[data-testid="stChatInput"] {
    background-color: #FFFFFF !important;
    border: 1px solid #DFE1E6 !important;
    border-radius: 4px !important;
    box-shadow: 0 1px 3px rgba(9, 30, 66, 0.08) !important;
    padding: 4px 8px !important;
}

[data-testid="stChatInput"]:focus-within {
    border: 2px solid #4C9AFF !important;
    box-shadow: 0 0 0 1px #4C9AFF !important;
}

[data-testid="stChatInput"] textarea {
    color: #172B4D !important;
    background-color: transparent !important;
    font-size: 14px !important;
}

[data-testid="stChatInputSubmitButton"] {
    color: #0052CC !important;
}

[data-testid="stChatInputSubmitButton"]:hover {
    background-color: #DEEBFF !important;
    border-radius: 3px !important;
}

/* FILE UPLOADER */
div[data-testid="stFileUploader"] section {
    background-color: #FAFBFC !important;
    border: 1px dashed #DFE1E6 !important;
    border-radius: 4px !important;
    padding: 1.25rem !important;
}

div[data-testid="stFileUploader"] section:hover {
    background-color: #EBECF0 !important;
    border-color: #4C9AFF !important;
}

/* CHECKBOX & RADIO */
div[data-testid="stCheckbox"] label span:first-child,
div[data-testid="stRadio"] label span:first-child {
    border-color: #DFE1E6 !important;
}

/* ==========================================================================
   JIRA BUTTONS
   ========================================================================== */

/* Primary Button */
div[data-testid="stButton"] button[kind="primary"],
div[data-testid="stFormSubmitButton"] button[kind="primary"] {
    background-color: #0052CC !important; /* Jira Brand Blue */
    border: none !important;
    color: #FFFFFF !important;
    border-radius: 3px !important;
    font-weight: 500 !important;
    font-size: 14px !important;
    padding: 6px 14px !important;
    box-shadow: none !important;
    transition: background-color 0.1s ease-out !important;
}

div[data-testid="stButton"] button[kind="primary"]:hover,
div[data-testid="stFormSubmitButton"] button[kind="primary"]:hover {
    background-color: #0065FF !important;
    color: #FFFFFF !important;
}

div[data-testid="stButton"] button[kind="primary"]:active,
div[data-testid="stFormSubmitButton"] button[kind="primary"]:active {
    background-color: #0747A6 !important;
}

/* Secondary / Default Button */
div[data-testid="stButton"] button:not([kind="primary"]),
div[data-testid="stFormSubmitButton"] button:not([kind="primary"]) {
    background-color: rgba(9, 30, 66, 0.04) !important;
    border: 1px solid #DFE1E6 !important;
    color: #42526E !important;
    border-radius: 3px !important;
    font-weight: 500 !important;
    font-size: 14px !important;
    padding: 6px 14px !important;
    box-shadow: none !important;
    transition: background-color 0.1s ease-out, color 0.1s ease-out !important;
}

div[data-testid="stButton"] button:not([kind="primary"]):hover,
div[data-testid="stFormSubmitButton"] button:not([kind="primary"]):hover {
    background-color: #EBECF0 !important;
    color: #172B4D !important;
    border-color: #C1C7D0 !important;
}

div[data-testid="stButton"] button:not([kind="primary"]):active,
div[data-testid="stFormSubmitButton"] button:not([kind="primary"]):active {
    background-color: #DEEBFF !important;
    color: #0052CC !important;
}

/* Sidebar Buttons */
section[data-testid="stSidebar"] div[data-testid="stButton"] button {
    background-color: rgba(255, 255, 255, 0.1) !important;
    border: 1px solid rgba(255, 255, 255, 0.2) !important;
    color: #FFFFFF !important;
}

section[data-testid="stSidebar"] div[data-testid="stButton"] button:hover {
    background-color: rgba(255, 255, 255, 0.2) !important;
    color: #FFFFFF !important;
}

/* ==========================================================================
   PAGE HEADER & JIRA ISSUE BREADCRUMBS
   ========================================================================== */
.page-header-container {
    margin-bottom: 1.25rem;
    padding-bottom: 0.75rem;
    border-bottom: 1px solid #DFE1E6;
}

.page-title {
    font-size: 1.5rem;
    font-weight: 600;
    color: #172B4D;
    margin: 0;
    letter-spacing: -0.015em;
    display: flex;
    align-items: center;
    gap: 0.6rem;
}

.page-subtitle {
    font-size: 0.85rem;
    color: #6B778C;
    margin-top: 0.25rem;
    margin-bottom: 0;
}

/* ==========================================================================
   JIRA STAT METRIC CARDS
   ========================================================================== */
.stat-card {
    background: #FFFFFF;
    border: 1px solid #DFE1E6;
    border-radius: 4px;
    padding: 1rem 1.15rem;
    box-shadow: 0 1px 1px rgba(9, 30, 66, 0.25), 0 0 1px 0 rgba(9, 30, 66, 0.31);
    height: 100%;
    transition: box-shadow 0.15s ease;
}

.stat-card:hover {
    box-shadow: 0 4px 8px -2px rgba(9, 30, 66, 0.25), 0 0 1px rgba(9, 30, 66, 0.31);
}

.stat-label {
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #5E6C84;
    margin-bottom: 0.3rem;
}

.stat-value {
    font-size: 1.7rem;
    font-weight: 700;
    color: #172B4D;
    line-height: 1.2;
}

.stat-hint {
    font-size: 0.75rem;
    color: #6B778C;
    margin-top: 0.3rem;
}

/* ==========================================================================
   JIRA LOZENGES (AUTHENTIC ATLASSIAN STATUS & PRIORITY BADGES)
   ========================================================================== */
.badge {
    display: inline-flex;
    align-items: center;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 11px;
    font-weight: 700;
    line-height: 1.2;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    border: 1px solid transparent;
}

/* TO DO / OPEN / BACKLOG */
.badge-open, .badge-todo, .badge-backlog {
    background-color: #DFE1E6 !important;
    color: #42526E !important;
    border-color: #C1C7D0 !important;
}

/* IN PROGRESS */
.badge-in_progress, .badge-in-progress, .badge-inprogress {
    background-color: #DEEBFF !important;
    color: #0747A6 !important;
    border-color: #B3D4FF !important;
}

/* PENDING / IN REVIEW / MEDIUM */
.badge-pending, .badge-in_review, .badge-medium {
    background-color: #FFF0B3 !important;
    color: #172B4D !important;
    border-color: #FFE380 !important;
}

/* DONE / RESOLVED / CLOSED */
.badge-resolved, .badge-done, .badge-closed {
    background-color: #E3FCEF !important;
    color: #006644 !important;
    border-color: #ABF5D1 !important;
}

/* ESCALATED / CRITICAL / BLOCKER */
.badge-escalated, .badge-critical, .badge-blocker {
    background-color: #FFEBE6 !important;
    color: #BF2600 !important;
    border-color: #FFBDAD !important;
}

/* HIGH / MAJOR */
.badge-high, .badge-major {
    background-color: #FFFAE6 !important;
    color: #FF8B00 !important;
    border-color: #FFE380 !important;
}

/* LOW / MINOR */
.badge-low, .badge-minor {
    background-color: #EAE6FF !important;
    color: #403294 !important;
    border-color: #C0B6F2 !important;
}

/* ==========================================================================
   JIRA PANELS, CARDS & EXPANDERS
   ========================================================================== */
.content-card {
    background: #FFFFFF;
    border: 1px solid #DFE1E6;
    border-radius: 4px;
    padding: 1.15rem;
    box-shadow: 0 1px 1px rgba(9, 30, 66, 0.25), 0 0 1px 0 rgba(9, 30, 66, 0.31);
    margin-bottom: 1.15rem;
}

/* Streamlit Builtin Container Borders */
div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] {
    background: #FFFFFF !important;
    border: 1px solid #DFE1E6 !important;
    border-radius: 4px !important;
    box-shadow: 0 1px 1px rgba(9, 30, 66, 0.15) !important;
}

/* Streamlit Expanders */
details[data-testid="stExpander"] {
    background: #FFFFFF !important;
    border: 1px solid #DFE1E6 !important;
    border-radius: 4px !important;
    box-shadow: 0 1px 1px rgba(9, 30, 66, 0.08) !important;
    margin-bottom: 0.75rem !important;
}

details[data-testid="stExpander"] summary {
    background-color: #FAFBFC !important;
    color: #172B4D !important;
    font-weight: 600 !important;
    font-size: 0.875rem !important;
    padding: 0.65rem 1rem !important;
    border-radius: 3px !important;
    transition: background-color 0.1s ease-in-out !important;
}

details[data-testid="stExpander"] summary:hover {
    background-color: #EBECF0 !important;
}

details[data-testid="stExpander"][open] summary {
    border-bottom: 1px solid #DFE1E6 !important;
}

/* Streamlit Tabs */
div[data-baseweb="tab-list"] {
    border-bottom: 2px solid #DFE1E6 !important;
    gap: 0.5rem !important;
}

button[data-baseweb="tab"] {
    color: #5E6C84 !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    padding: 8px 12px !important;
    border-radius: 3px 3px 0 0 !important;
}

button[data-baseweb="tab"]:hover {
    color: #0052CC !important;
    background-color: #EBECF0 !important;
}

button[data-baseweb="tab"][aria-selected="true"] {
    color: #0052CC !important;
    font-weight: 600 !important;
    border-bottom: 2px solid #0052CC !important;
}

/* Empty State */
.empty-state {
    text-align: center;
    padding: 2.5rem 1.5rem;
    background: #FFFFFF;
    border: 1px dashed #DFE1E6;
    border-radius: 4px;
    margin: 1rem 0;
}

.empty-state-title {
    font-size: 1rem;
    font-weight: 600;
    color: #172B4D;
    margin-top: 0.5rem;
    margin-bottom: 0.25rem;
}

.empty-state-desc {
    font-size: 0.85rem;
    color: #6B778C;
    max-width: 440px;
    margin: 0 auto;
}

/* Citations & Evidence Box */
.citation-item {
    background: #FAFBFC;
    border: 1px solid #DFE1E6;
    border-radius: 3px;
    padding: 0.75rem 1rem;
    margin-bottom: 0.5rem;
}

.citation-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.35rem;
}

.citation-title {
    font-weight: 600;
    font-size: 0.85rem;
    color: #0052CC;
}

.citation-score {
    font-size: 0.75rem;
    color: #0052CC;
    font-weight: 600;
    background: #DEEBFF;
    padding: 0.15rem 0.45rem;
    border-radius: 3px;
}

.citation-snippet {
    font-size: 0.8rem;
    color: #344563;
    line-height: 1.45;
}

/* Chat Messages */
[data-testid="stChatMessage"] {
    border-radius: 4px;
    padding: 1rem;
    margin-bottom: 0.75rem;
    border: 1px solid #DFE1E6;
    background-color: #FFFFFF;
    box-shadow: 0 1px 2px rgba(9, 30, 66, 0.08);
}

/* Escalation Callout (Jira Critical / Warning Banner) */
.escalation-callout {
    background-color: #FFEBE6;
    border-left: 4px solid #DE350B;
    padding: 0.85rem 1.15rem;
    border-radius: 0 4px 4px 0;
    margin: 0.75rem 0;
}

.escalation-title {
    color: #BF2600;
    font-weight: 600;
    font-size: 0.9rem;
    margin: 0 0 0.25rem 0;
}

.escalation-desc {
    color: #42526E;
    font-size: 0.825rem;
    margin: 0;
}

/* Diagnostic / Trace Panel */
.dev-panel {
    background-color: #091E42;
    color: #DEEBFF;
    border-radius: 3px;
    padding: 0.75rem 1rem;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: 0.75rem;
    margin-top: 0.5rem;
}

/* Code Snippets & Tags */
code {
    background-color: #F4F5F7 !important;
    border: 1px solid #DFE1E6 !important;
    color: #172B4D !important;
    padding: 0.15rem 0.35rem !important;
    border-radius: 3px !important;
    font-size: 0.85em !important;
}

/* Hide streamlit default branding */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
</style>
"""


def apply_theme() -> None:
    """Inject global Jira / Atlassian Design System CSS."""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def render_header(title: str, subtitle: str, badge: str | None = None) -> None:
    """Render a standardized Jira-style page header with optional lozenge."""
    badge_html = f'<span class="badge badge-open" style="margin-left:0.6rem;">{badge}</span>' if badge else ""
    st.markdown(
        f"""
        <div class="page-header-container">
            <h1 class="page-title">{title} {badge_html}</h1>
            <p class="page-subtitle">{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_stat_card(label: str, value: str | int, hint: str = "") -> None:
    """Render a Jira enterprise metric stat card."""
    hint_html = f'<div class="stat-hint">{hint}</div>' if hint else ""
    st.markdown(
        f"""
        <div class="stat-card">
            <div class="stat-label">{label}</div>
            <div class="stat-value">{value}</div>
            {hint_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def get_status_badge_html(status: str) -> str:
    """Return HTML for an authentic Jira Lozenge status badge."""
    raw = (status or "open").lower().replace(" ", "_").replace("-", "_")
    if raw in ("resolved", "done", "closed"):
        css = "badge-resolved"
    elif raw in ("in_progress", "inprogress", "progress"):
        css = "badge-in_progress"
    elif raw in ("pending", "in_review", "review"):
        css = "badge-pending"
    elif raw in ("escalated", "critical", "blocker"):
        css = "badge-escalated"
    else:
        css = "badge-open"
    return f'<span class="badge {css}">{status.upper()}</span>'


def get_priority_badge_html(priority: str) -> str:
    """Return HTML for an authentic Jira Lozenge priority badge."""
    p_lower = (priority or "medium").lower()
    if p_lower in ("critical", "blocker"):
        css = "badge-critical"
    elif p_lower in ("high", "major"):
        css = "badge-high"
    elif p_lower == "low":
        css = "badge-low"
    else:
        css = "badge-medium"
    return f'<span class="badge {css}">{priority.upper()}</span>'


def render_empty_state(title: str, message: str, icon: str = "inbox") -> None:
    """Render a clean Jira-style empty state card."""
    st.markdown(
        f"""
        <div class="empty-state">
            <div style="font-size: 1.75rem; color: #6B778C;">◻</div>
            <div class="empty-state-title">{title}</div>
            <div class="empty-state-desc">{message}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def format_datetime(dt_val: str | datetime | None) -> str:
    """Format ISO timestamp to readable UTC date/time in Jira format."""
    if not dt_val:
        return "—"
    if isinstance(dt_val, str):
        try:
            dt = datetime.fromisoformat(dt_val.replace("Z", "+00:00"))
            return dt.strftime("%b %d, %Y, %I:%M %p")
        except Exception:
            return dt_val[:16].replace("T", " ")
    return dt_val.strftime("%b %d, %Y, %I:%M %p")
