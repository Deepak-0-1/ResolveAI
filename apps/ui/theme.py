"""Enterprise UI Design System & Component Helpers for ResolveAI."""

from __future__ import annotations

from datetime import datetime
import streamlit as st

CUSTOM_CSS = """
<style>
/* Import Inter font */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

/* Main workspace background and layout */
.main .block-container {
    max-width: 1200px;
    padding-top: 1.75rem;
    padding-bottom: 2.5rem;
    padding-left: 2rem;
    padding-right: 2rem;
}

/* Dark Navy Sidebar */
section[data-testid="stSidebar"] {
    background-color: #0F172A !important;
    color: #E2E8F0 !important;
    border-right: 1px solid #1E293B;
}

section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] div {
    color: #E2E8F0;
}

/* Sidebar navigation links */
section[data-testid="stSidebar"] div[data-testid="stSidebarNav"] {
    padding-top: 0.5rem;
}

section[data-testid="stSidebar"] div[data-testid="stSidebarNav"] a {
    color: #94A3B8 !important;
    border-radius: 6px;
    transition: all 0.15s ease-in-out;
    margin-bottom: 2px;
}

section[data-testid="stSidebar"] div[data-testid="stSidebarNav"] a:hover {
    color: #FFFFFF !important;
    background-color: #1E293B !important;
}

section[data-testid="stSidebar"] div[data-testid="stSidebarNav"] a[aria-current="page"] {
    color: #FFFFFF !important;
    background-color: #1E293B !important;
    border-left: 3px solid #3B82F6;
    font-weight: 600;
}

/* User Profile Badge in Sidebar */
.user-profile-badge {
    background: #1E293B;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 0.85rem 1rem;
    margin-bottom: 1.25rem;
}

.user-profile-name {
    color: #F8FAFC !important;
    font-weight: 600;
    font-size: 0.95rem;
    margin: 0;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.user-profile-role {
    color: #94A3B8 !important;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-weight: 500;
    margin-top: 0.2rem;
}

/* Page Header */
.page-header-container {
    margin-bottom: 1.5rem;
    padding-bottom: 0.75rem;
    border-bottom: 1px solid #E2E8F0;
}

.page-title {
    font-size: 1.6rem;
    font-weight: 700;
    color: #0F172A;
    margin: 0;
    letter-spacing: -0.02em;
    display: flex;
    align-items: center;
    gap: 0.6rem;
}

.page-subtitle {
    font-size: 0.875rem;
    color: #64748B;
    margin-top: 0.25rem;
    margin-bottom: 0;
}

/* Stat Cards */
.stat-card {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    padding: 1.25rem;
    box-shadow: 0 1px 3px 0 rgba(15, 23, 42, 0.04);
    height: 100%;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.stat-card:hover {
    box-shadow: 0 4px 6px -1px rgba(15, 23, 42, 0.07);
}

.stat-label {
    font-size: 0.775rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #64748B;
    margin-bottom: 0.35rem;
}

.stat-value {
    font-size: 1.75rem;
    font-weight: 700;
    color: #0F172A;
    line-height: 1.2;
}

.stat-hint {
    font-size: 0.75rem;
    color: #94A3B8;
    margin-top: 0.35rem;
}

/* Badges */
.badge {
    display: inline-flex;
    align-items: center;
    padding: 0.2rem 0.55rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 600;
    line-height: 1;
    border: 1px solid transparent;
}

.badge-open {
    background-color: #EFF6FF;
    color: #1D4ED8;
    border-color: #BFDBFE;
}

.badge-pending {
    background-color: #FFFBEB;
    color: #B45309;
    border-color: #FDE68A;
}

.badge-escalated {
    background-color: #FEF2F2;
    color: #B91C1C;
    border-color: #FECACA;
}

.badge-resolved {
    background-color: #ECFDF5;
    color: #047857;
    border-color: #A7F3D0;
}

.badge-closed {
    background-color: #F1F5F9;
    color: #475569;
    border-color: #CBD5E1;
}

.badge-critical {
    background-color: #FEF2F2;
    color: #DC2626;
    border-color: #FCA5A5;
}

.badge-high {
    background-color: #FFF7ED;
    color: #C2410C;
    border-color: #FDBA74;
}

.badge-medium {
    background-color: #FEFCE8;
    color: #A16207;
    border-color: #FEF08A;
}

.badge-low {
    background-color: #F0FDF4;
    color: #15803D;
    border-color: #BBF7D0;
}

/* Card Containers */
.content-card {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    padding: 1.25rem;
    box-shadow: 0 1px 3px 0 rgba(15, 23, 42, 0.04);
    margin-bottom: 1.25rem;
}

/* Empty State */
.empty-state {
    text-align: center;
    padding: 2.5rem 1.5rem;
    background: #FFFFFF;
    border: 1px dashed #CBD5E1;
    border-radius: 8px;
    margin: 1rem 0;
}

.empty-state-title {
    font-size: 1rem;
    font-weight: 600;
    color: #334155;
    margin-top: 0.5rem;
    margin-bottom: 0.25rem;
}

.empty-state-desc {
    font-size: 0.85rem;
    color: #64748B;
    max-width: 420px;
    margin: 0 auto;
}

/* Citations & Sources Box */
.citation-item {
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 6px;
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
    color: #1E293B;
}

.citation-score {
    font-size: 0.75rem;
    color: #2563EB;
    font-weight: 600;
    background: #EFF6FF;
    padding: 0.15rem 0.45rem;
    border-radius: 4px;
}

.citation-snippet {
    font-size: 0.8rem;
    color: #475569;
    line-height: 1.45;
}

/* Activity item */
.activity-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem 0;
    border-bottom: 1px solid #F1F5F9;
}

.activity-item:last-child {
    border-bottom: none;
}

/* Clean buttons */
div[data-testid="stButton"] button {
    border-radius: 6px;
    font-weight: 500;
    padding: 0.4rem 0.9rem;
    transition: all 0.15s ease-in-out;
}

/* Primary submit button */
div[data-testid="stButton"] button[kind="primary"] {
    background-color: #2563EB !important;
    border-color: #2563EB !important;
    color: #FFFFFF !important;
}

div[data-testid="stButton"] button[kind="primary"]:hover {
    background-color: #1D4ED8 !important;
    border-color: #1D4ED8 !important;
}

/* Chat bubble enhancements */
[data-testid="stChatMessage"] {
    border-radius: 8px;
    padding: 1rem;
    margin-bottom: 0.75rem;
    border: 1px solid #E2E8F0;
    background-color: #FFFFFF;
}

/* Escalation Callout */
.escalation-callout {
    background-color: #FFF1F2;
    border-left: 4px solid #E11D48;
    padding: 0.85rem 1.15rem;
    border-radius: 0 6px 6px 0;
    margin: 0.75rem 0;
}

.escalation-title {
    color: #9F1239;
    font-weight: 600;
    font-size: 0.9rem;
    margin: 0 0 0.25rem 0;
}

.escalation-desc {
    color: #881337;
    font-size: 0.825rem;
    margin: 0;
}

/* Diagnostic / Dev Panel */
.dev-panel {
    background-color: #0F172A;
    color: #E2E8F0;
    border-radius: 6px;
    padding: 0.75rem 1rem;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: 0.75rem;
    margin-top: 0.5rem;
}

/* Hide streamlit default branding */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
</style>
"""


def apply_theme() -> None:
    """Inject global design system CSS."""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def render_header(title: str, subtitle: str, badge: str | None = None) -> None:
    """Render a standardized page header with optional badge."""
    badge_html = f'<span class="badge badge-open" style="font-size:0.8rem; margin-left:0.5rem;">{badge}</span>' if badge else ""
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
    """Render an enterprise stat metric card."""
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
    """Return HTML for a status badge."""
    status_lower = (status or "open").lower()
    css_class = f"badge-{status_lower}" if status_lower in ("open", "pending", "escalated", "resolved", "closed") else "badge-open"
    return f'<span class="badge {css_class}">{status.upper()}</span>'


def get_priority_badge_html(priority: str) -> str:
    """Return HTML for a priority badge."""
    p_lower = (priority or "medium").lower()
    css_class = f"badge-{p_lower}" if p_lower in ("low", "medium", "high", "critical") else "badge-medium"
    return f'<span class="badge {css_class}">{priority.upper()}</span>'


def render_empty_state(title: str, message: str, icon: str = "inbox") -> None:
    """Render a clean empty state card."""
    st.markdown(
        f"""
        <div class="empty-state">
            <div style="font-size: 2rem; color: #94A3B8;">●</div>
            <div class="empty-state-title">{title}</div>
            <div class="empty-state-desc">{message}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def format_datetime(dt_val: str | datetime | None) -> str:
    """Format ISO timestamp to readable UTC date/time."""
    if not dt_val:
        return "—"
    if isinstance(dt_val, str):
        try:
            # Handle standard ISO strings
            dt = datetime.fromisoformat(dt_val.replace("Z", "+00:00"))
            return dt.strftime("%b %d, %Y %H:%M")
        except Exception:
            return dt_val[:16].replace("T", " ")
    return dt_val.strftime("%b %d, %Y %H:%M")
