import os
from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st

from speaker_tagger import dict_df_to_dict, process_with_dict

DICT_DIR = "SpeakerTypeDict"
DICT_FILE = None
SPEAKER_TYPES = ["Brand Voice", "Consumer Voice", "Influencer & Page", "Publisher"]


def find_dict_file():
    if not os.path.isdir(DICT_DIR):
        return None
    for f in sorted(os.listdir(DICT_DIR)):
        if f.endswith((".xlsx", ".xls")) and not f.startswith("~"):
            return os.path.join(DICT_DIR, f)
    return None


def load_dict_df(filepath):
    df = pd.read_excel(filepath)
    df = df[["Username", "Speaker Type"]].dropna(subset=["Username"])
    return df


def save_dict_df(df, filepath):
    df.to_excel(filepath, index=False)


def find_duplicates(df):
    stripped = df["Username"].astype(str).str.strip().str.lower()
    dup_mask = stripped.duplicated(keep=False)
    dup_values = stripped[dup_mask].unique()
    dup_rows = df[dup_mask]
    return dup_values, dup_rows


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
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
    }
    .stTabs [data-baseweb="tab"] {
        flex: 1 1 0;
        justify-content: center;
        font-size: 1.1rem;
        font-weight: 600;
        padding: 0.75rem 0;
    }
    .stFileUploader section {
        width: 100%;
    }
    .stFileUploader [data-testid="stFileUploadDropzone"] {
        width: 100%;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Session state init
# ---------------------------------------------------------------------------
if "dict_df" not in st.session_state:
    DICT_FILE = find_dict_file()
    if DICT_FILE:
        st.session_state.dict_df = load_dict_df(DICT_FILE)
        st.session_state.dict_file = DICT_FILE
    else:
        st.session_state.dict_df = pd.DataFrame(columns=["Username", "Speaker Type"])
        st.session_state.dict_file = os.path.join(DICT_DIR, "SpeakerTypeDict.xlsx")

st.session_state.speakertype_dict = dict_df_to_dict(st.session_state.dict_df)

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
st.title("🏷️ Speaker Tag Updater")
st.caption("Tag TalkWalker export data with speaker types")

tab_process, tab_dict = st.tabs(["📤 Process", "📖 Speaker Dictionary"])

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
        disabled=(raw_file is None or len(st.session_state.speakertype_dict) == 0),
    ):
        with st.spinner("Processing..."):
            df, stats = process_with_dict(
                raw_file.read(), st.session_state.speakertype_dict
            )

        st.success(f"Done. {stats['total_rows']:,} rows processed.")

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            with st.container(border=True):
                st.metric("Total Rows", f"{stats['total_rows']:,}")
        with col_b:
            with st.container(border=True):
                st.metric("Dict Entries", stats["dict_loaded"])
        with col_c:
            with st.container(border=True):
                st.metric("Columns", len(df.columns))

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
# Tab 2: Speaker Dictionary
# ===========================================================================
with tab_dict:
    dict_path = st.session_state.dict_file
    if os.path.exists(dict_path):
        st.caption(f"Dictionary file: {dict_path}")

    col1, col2, col3 = st.columns(3)
    with col1:
        with st.container(border=True):
            st.metric("Total Entries", len(st.session_state.dict_df))
    full_df = st.session_state.dict_df.copy()

    dup_values, _ = find_duplicates(full_df)
    with col2:
        with st.container(border=True):
            st.metric("Duplicate Usernames", len(dup_values))

    mtime = os.path.getmtime(dict_path) if dict_path and os.path.exists(dict_path) else None
    with col3:
        with st.container(border=True):
            st.metric("Last Saved", datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %H:%M") if mtime else "-")

    if len(dup_values) > 0:
        dup_usernames = ", ".join(sorted(dup_values)[:10])
        suffix = "..." if len(dup_values) > 10 else ""
        st.warning(
            f"**{len(dup_values)} duplicate usernames found.** "
            f"Only the first match is used during processing. "
            f"Duplicates: {dup_usernames}{suffix}"
        )

    st.divider()

    # Search
    search = st.text_input(
        "🔍 Search",
        value="",
        placeholder="Filter by username or speaker type...",
        key="dict_search",
    )

    if search:
        mask = (
            full_df["Username"]
            .astype(str)
            .str.contains(search, case=False, na=False)
            | full_df["Speaker Type"]
            .astype(str)
            .str.contains(search, case=False, na=False)
        )
        results = full_df[mask]
        st.caption(f"{len(results)} match(es)")
        st.dataframe(
            results,
            use_container_width=True,
            hide_index=True,
            height=min(35 * len(results) + 38, 300),
        )
        st.divider()

    # Editor
    st.subheader(f"📝 Edit Dictionary ({len(full_df)} entries)")

    editor_df = full_df.reset_index(drop=True)
    editor_df["Username"] = editor_df["Username"].astype(str)
    editor_df["Speaker Type"] = editor_df["Speaker Type"].fillna("").astype(str)

    editor_key = f"dict_editor_{len(full_df)}_{hash(tuple(editor_df['Username']))}"
    edited_df = st.data_editor(
        editor_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Username": st.column_config.TextColumn(),
            "Speaker Type": st.column_config.SelectboxColumn(
                options=SPEAKER_TYPES
            ),
        },
        key=editor_key,
    )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("💾 Save", use_container_width=True, type="primary"):
            os.makedirs(DICT_DIR, exist_ok=True)
            save_dict_df(edited_df, st.session_state.dict_file)
            st.session_state.dict_df = edited_df
            st.session_state.speakertype_dict = dict_df_to_dict(edited_df)
            st.success("Saved")
            st.rerun()

    with c2:
        if st.button("↩️ Reset", use_container_width=True):
            DICT_FILE = find_dict_file()
            if DICT_FILE:
                st.session_state.dict_df = load_dict_df(DICT_FILE)
                st.session_state.dict_file = DICT_FILE
                st.session_state.speakertype_dict = dict_df_to_dict(
                    st.session_state.dict_df
                )
                st.rerun()

    with c3:
        with st.popover("📥 Import", use_container_width=True):
            uploaded_dict = st.file_uploader(
                "Upload dictionary Excel",
                type=["xlsx", "xls"],
                key="dict_upload",
                label_visibility="collapsed",
            )
            if uploaded_dict:
                new_df = pd.read_excel(uploaded_dict)
                new_df = new_df[["Username", "Speaker Type"]].dropna(
                    subset=["Username"]
                )
                os.makedirs(DICT_DIR, exist_ok=True)
                save_dict_df(new_df, st.session_state.dict_file)
                st.session_state.dict_df = new_df
                st.session_state.speakertype_dict = dict_df_to_dict(new_df)
                st.success(f"Imported and saved {len(new_df)} entries")
                st.rerun()

    with c4:
        buf = BytesIO()
        edited_df.to_excel(buf, index=False)
        st.download_button(
            label="📤 Export",
            data=buf.getvalue(),
            file_name="SpeakerTypeDict.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
