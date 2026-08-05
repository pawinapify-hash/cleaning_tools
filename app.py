import json
import os
import pickle
import secrets
from io import BytesIO

import gspread
import pandas as pd
import streamlit as st
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as OAuthCredentials
from google_auth_oauthlib.flow import Flow

from monthly_cleaning import process_monthly_cleaning
from speaker_tagger import dict_df_to_dict, process_with_dict

import hashlib
import base64

SPEAKER_TYPES = ["Brand Voice", "Consumer Voice", "Influencer & Page", "Publisher"]
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
OAUTH_CLIENT_FILE = "oauth_client.json"
TOKEN_FILE = "token.pickle"
FIXED_SHEET_URL = "https://docs.google.com/spreadsheets/d/1Hoy7EfkckFdCAWW8ELa3qc41iHpOeJPeOQqjIcfQWRc/edit?gid=1690969829#gid=1690969829"


def load_oauth_config():
    try:
        if "oauth" in st.secrets:
            return {
                "web": {
                    "client_id": st.secrets["oauth"]["client_id"],
                    "client_secret": st.secrets["oauth"]["client_secret"],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            }
    except Exception:
        pass

    if os.path.exists(OAUTH_CLIENT_FILE):
        with open(OAUTH_CLIENT_FILE) as f:
            return json.load(f)

    return None


def get_redirect_uri():
    if os.name != "nt":
        return "https://speakertype-tagging.streamlit.app"
    addr = os.environ.get("STREAMLIT_SERVER_ADDRESS", "")
    if addr and addr != "localhost":
        return "https://speakertype-tagging.streamlit.app"
    return "http://localhost:8511"


def get_credentials():
    creds = None

    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            with open(TOKEN_FILE, "wb") as f:
                pickle.dump(creds, f)
        except Exception:
            creds = None

    if not creds or not creds.valid:
        query_params = st.query_params
        if "code" in query_params:
            oauth_config = load_oauth_config()
            if oauth_config:
                try:
                    flow = Flow.from_client_config(
                        oauth_config,
                        scopes=SCOPES,
                        redirect_uri=get_redirect_uri(),
                    )
                    verifier = None
                    raw_state = query_params.get("state")
                    if raw_state:
                        try:
                            verifier = base64.urlsafe_b64decode(
                                raw_state.encode()
                            ).decode()
                        except Exception:
                            pass
                    flow.fetch_token(
                        code=query_params["code"], code_verifier=verifier
                    )
                    creds = flow.credentials
                    if os.path.exists(TOKEN_FILE):
                        os.remove(TOKEN_FILE)
                    with open(TOKEN_FILE, "wb") as f:
                        pickle.dump(creds, f)
                    st.query_params.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Auth failed: {type(e).__name__}: {e}")
                    st.stop()

    return creds


def read_dict_from_gsheet(spreadsheet_url, creds):
    client = gspread.authorize(creds)
    sheet = client.open_by_url(spreadsheet_url).sheet1
    records = sheet.get_all_records()
    if not records:
        return pd.DataFrame(columns=["Username", "Speaker Type"])
    df = pd.DataFrame(records)
    df = df[["Username", "Speaker Type"]].dropna(subset=["Username"])
    return df


# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Cleaning Tools",
    page_icon="🧹",
    layout="wide",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }
    .stFileUploader section { width: 100%; }
    .stFileUploader [data-testid="stFileUploadDropzone"] { width: 100%; }
    .stTabs [data-baseweb="tab-list"] { gap: 0; }
    .stTabs [data-baseweb="tab"] {
        flex: 1 1 0; justify-content: center; font-size: 1.1rem; font-weight: 600; padding: 0.75rem 0;
    }
    [data-testid="stSidebar"] { min-width: 240px !important; max-width: 260px !important; }
    [data-testid="stMetricLabel"] { overflow: visible !important; text-overflow: unset !important; white-space: normal !important; word-break: break-all !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Auth & sheet setup (shared)
# ---------------------------------------------------------------------------
st.session_state.sheet_url = FIXED_SHEET_URL
oauth_config = load_oauth_config()
creds = get_credentials()
if creds and creds.valid:
    st.session_state.creds = creds
ready = bool(st.session_state.get("creds"))

# ---------------------------------------------------------------------------
# Sign-in screen
# ---------------------------------------------------------------------------
if not ready:
    st.title("🧹 Cleaning Tools")

    if oauth_config is None:
        st.warning(
            f"No OAuth config found. Add `{OAUTH_CLIENT_FILE}` "
            "to the project folder, or set `[oauth]` in Streamlit secrets."
        )
    else:
        flow = Flow.from_client_config(
            oauth_config,
            scopes=SCOPES,
            redirect_uri=get_redirect_uri(),
        )
        code_verifier = secrets.token_urlsafe(64)
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).rstrip(b"=").decode()
        state = base64.urlsafe_b64encode(code_verifier.encode()).decode()
        auth_url, _ = flow.authorization_url(
            prompt="consent",
            access_type="offline",
            state=state,
            code_challenge=code_challenge,
            code_challenge_method="S256",
        )

        st.info("Sign in with your Google account to get started.")
        st.markdown(
            f"""<a href="{auth_url}" target="_blank" 
            style="display:inline-block;padding:0.75rem 2rem;font-size:1.1rem;
            background:#f0f2f6;border:1px solid #d1d5db;border-radius:0.5rem;
            text-decoration:none;color:#15426f;cursor:pointer;">
            🔑 Sign in with Google</a>""",
            unsafe_allow_html=True,
        )
        st.caption("You only need to do this once.")
    st.stop()

# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("🧹 Cleaning Tools")
    feature = st.radio(
        "Select Feature",
        ["🏷️ Speaker Tag Updater", "📊 Monthly Cleaning Process"],
        label_visibility="collapsed",
    )
    st.divider()

# ===========================================================================
# Feature: Speaker Tag Updater
# ===========================================================================
if feature == "🏷️ Speaker Tag Updater":
    st.title("🏷️ Speaker Tag Updater")

    tab_process, tab_config = st.tabs(["📤 Process", "⚙️ Configuration"])

    with tab_process:
        raw_file = st.file_uploader(
            "Drag and drop your TalkWalker raw data Excel here",
            type=["xlsx", "xls"],
        )

        if st.button(
            "⚡ Process",
            type="primary",
            disabled=(raw_file is None),
        ):
            with st.spinner("Reading dictionary from Google Sheets..."):
                try:
                    dict_df = read_dict_from_gsheet(
                        st.session_state.sheet_url, st.session_state.creds
                    )
                    speakertype_dict = dict_df_to_dict(dict_df)
                except Exception as e:
                    st.error(
                        f"Failed to read Google Sheet. "
                        f"Make sure your account has access.\n\nError: {e}"
                    )
                    st.stop()

            with st.spinner("Processing..."):
                df, stats = process_with_dict(raw_file.read(), speakertype_dict)

            st.success(
                f"Done. {stats['total_rows']:,} rows processed. "
                f"Dictionary: {len(speakertype_dict)} entries."
            )

            tags_col = df["tags_customer"].astype(str)

            type_counts = {}
            for speaker_type in SPEAKER_TYPES:
                type_counts[speaker_type] = tags_col.str.contains(
                    f"Type of Speaker/{speaker_type}", na=False
                ).sum()

            col_a, col_b = st.columns(2)
            with col_a:
                with st.container(border=True):
                    st.metric("Total Rows", f"{stats['total_rows']:,}")
            with col_b:
                with st.container(border=True):
                    st.metric("Newly Tagged", f"{stats['newly_tagged']:,}")

            st.caption("Tags by speaker type")
            c1, c2, c3, c4 = st.columns(4)
            for col, (stype, count) in zip([c1, c2, c3, c4], type_counts.items()):
                with col:
                    with st.container(border=True):
                        st.metric(stype, f"{count:,}")

            st.subheader("Data Preview")
            st.dataframe(df.head(100), use_container_width=True)

            output = BytesIO()
            with pd.ExcelWriter(
                output,
                engine="xlsxwriter",
                engine_kwargs={"options": {"strings_to_urls": False}},
            ) as writer:
                df.to_excel(writer, index=False)
            output.seek(0)

            st.download_button(
                label="⬇️ Download Tagged Excel",
                data=output,
                file_name=raw_file.name.replace(".", "_tagged."),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
            )

    with tab_config:
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Status", "Connected")
        with col2:
            st.markdown(
                f'<a href="{FIXED_SHEET_URL}" target="_blank">'
                '<button style="width:100%;padding:0.5rem;font-size:1rem;cursor:pointer;">'
                "📝 Open Dictionary Sheet</button></a>",
                unsafe_allow_html=True,
            )
            st.caption("Opens the dictionary Google Sheet in a new tab")

# ===========================================================================
# Feature: Monthly Cleaning Process
# ===========================================================================
elif feature == "📊 Monthly Cleaning Process":
    st.title("📊 Monthly Cleaning Process")

    col_ref, col_target = st.columns(2)
    with col_ref:
        ref_file = st.file_uploader(
            "Reference file (Excel)",
            type=["xlsx", "xls"],
            key="ref_file",
        )
    with col_target:
        target_file = st.file_uploader(
            "Target file (Excel)",
            type=["xlsx", "xls"],
            key="target_file",
        )

    st.divider()

    st.subheader("Subtasks")
    do_sentiment = st.checkbox("1. Update Sticker Sentiment", value=True)
    do_campaign = st.checkbox("2. Remove Campaign Rows", value=True)
    do_hide = st.checkbox("3. Remove Hide", value=True)

    any_selected = do_sentiment or do_campaign or do_hide
    needs_ref = do_sentiment or do_campaign
    files_ok = any_selected and target_file is not None and (
        not needs_ref or ref_file is not None
    )

    if st.button("⚡ Process", type="primary", disabled=not files_ok):
        tasks = {
            "update_sticker_sentiment": do_sentiment,
            "remove_campaign_rows": do_campaign,
            "remove_hide": do_hide,
        }

        ref_bytes = ref_file.read() if ref_file else None
        target_bytes = target_file.read()

        with st.spinner("Processing..."):
            try:
                result_df, all_stats = process_monthly_cleaning(
                    ref_bytes, target_bytes, tasks
                )
                st.session_state.mc_result = result_df
                st.session_state.mc_stats = all_stats
                st.session_state.mc_filename = target_file.name
            except Exception as e:
                st.error(f"Processing failed: {e}")
                st.stop()

    if "mc_result" in st.session_state:
        st.divider()
        st.success(f"Done. {len(st.session_state.mc_result):,} rows remaining.")

        for task_name, stats in st.session_state.mc_stats.items():
            with st.container(border=True):
                if "updated" in stats:
                    st.subheader(f"{task_name}: {stats['updated']:,} updated")
                elif "removed" in stats:
                    st.subheader(f"{task_name}: {stats['removed']:,} removed")

                if stats.get("unmatched", 0) > 0:
                    st.warning(
                        f"{stats['unmatched']:,} reference URLs not found in target file"
                    )

                dist = stats.get("distribution", {})
                if dist:
                    cols = st.columns(len(dist))
                    for col, (label, count) in zip(cols, dist.items()):
                        with col:
                            st.metric(str(label), f"{count:,}")

        output = BytesIO()
        with pd.ExcelWriter(
            output,
            engine="xlsxwriter",
            engine_kwargs={"options": {"strings_to_urls": False}},
        ) as writer:
            st.session_state.mc_result.to_excel(writer, index=False)
        output.seek(0)

        out_name = (
            st.session_state.mc_filename or "output.xlsx"
        ).replace(".", "_cleaned.")

        st.download_button(
            label="⬇️ Download Cleaned File",
            data=output,
            file_name=out_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )
