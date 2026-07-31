import json
import os
import pickle
from io import BytesIO

import gspread
import pandas as pd
import streamlit as st
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as OAuthCredentials
from google_auth_oauthlib.flow import Flow

from speaker_tagger import dict_df_to_dict, process_with_dict

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
                    flow.fetch_token(code=query_params["code"])
                    creds = flow.credentials
                    with open(TOKEN_FILE, "wb") as f:
                        pickle.dump(creds, f)
                    st.markdown(
                        '<meta http-equiv="refresh" content="0; url=/">',
                        unsafe_allow_html=True,
                    )
                    st.success("Signed in. Redirecting...")
                    st.stop()
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
    page_title="Speaker Tag Updater",
    page_icon="🏷️",
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
# Tabs
# ---------------------------------------------------------------------------
st.title("🏷️ Speaker Tag Updater")

tab_process, tab_config = st.tabs(["📤 Process", "⚙️ Configuration"])

# ===========================================================================
# Tab 1: Process
# ===========================================================================
with tab_process:
    raw_file = st.file_uploader(
        "Drag and drop your TalkWalker raw data Excel here",
        type=["xlsx", "xls"],
    )

    if st.button(
        "⚡ Process",
        type="primary",
        disabled=(raw_file is None or not ready),
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

# ===========================================================================
# Tab 2: Configuration
# ===========================================================================
with tab_config:
    if oauth_config is None:
        st.warning(
            f"No OAuth config found. Add `{OAUTH_CLIENT_FILE}` "
            "to the project folder, or set `[oauth]` in Streamlit secrets."
        )
    elif creds and creds.valid:
        st.success("✅ Signed in with Google")

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Status", "Connected")
        with col2:
            st.markdown(
                f'<a href="{FIXED_SHEET_URL}" target="_blank">'
                '<button style="width:100%;padding:0.5rem;font-size:1rem;cursor:pointer;">'
                "📝 Edit Source</button></a>",
                unsafe_allow_html=True,
            )
            st.caption("Opens the dictionary Google Sheet in a new tab")
    else:
        flow = Flow.from_client_config(
            oauth_config,
            scopes=SCOPES,
            redirect_uri=get_redirect_uri(),
        )
        auth_url, _ = flow.authorization_url(
            prompt="consent",
            access_type="offline",
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
