import re
from io import BytesIO

import numpy as np
import pandas as pd


def extract_domain_name(url):
    """
    Extracts the main domain name from a URL, removing 'www.' prefix
    and top-level domain suffixes (like .com, .org, etc.).
    Example: 'www.prachachart.com' -> 'prachachart'
    """
    if pd.isna(url) or not isinstance(url, str):
        return None

    url = re.sub(r"https?://", "", url)
    url = re.sub(r"^www\.", "", url)
    url = url.split("/")[0]

    parts = url.split(".")
    if len(parts) >= 2:
        if len(parts) > 2 and len(parts[-1]) <= 3 and len(parts[-2]) <= 3:
            return parts[-3]
        else:
            return parts[-2]
    elif len(parts) == 1:
        return parts[0]
    return None


def apply_source_type_url_replacement(df):
    """
    Replaces values in 'extra_author_attributes.name' with cleaned URLs
    from the 'url' column, but only for specific 'source_type' values.
    Returns the modified DataFrame and a boolean mask indicating modified rows.
    """
    df = df.copy()

    allowed_source_types = [
        "BLOG,BLOG_OTHER",
        "ONLINENEWS,ONLINENEWS_OTHER",
        "ONLINENEWS,ONLINENEWS_NEWSPAPER",
        "MESSAGEBOARD,MESSAGEBOARD_OTHER",
        "NEWSLETTER,NEWSLETTER_SUBSTACK",
        "ONLINENEWS,ONLINENEWS_PRESSRELEASES",
        "ONLINENEWS,ONLINENEWS_MAGAZINE",
        "ONLINENEWS,ONLINENEWS_TVRADIO",
        "ONLINENEWS,ONLINENEWS_AGENCY",
        "OTHER",
    ]

    mask = df["source_type"].isin(allowed_source_types)
    df.loc[mask, "extra_author_attributes.name"] = df.loc[mask, "url"].apply(
        extract_domain_name
    )
    df["is_url_replaced"] = mask

    return df


def update_speaker_tags(df, speakertype_dict):
    """
    Tags every row with a speaker type using a 3-step fallback strategy.
    Rows that already have a speaker type are skipped.

    Step 1: Match author name against speaker dictionary (exact, case-insensitive).
    Step 2: Tag isComment rows as 'Consumer Voice'.
    Step 3: Fallback - tag remaining rows as 'Influencer & Page'.
    """
    df = df.copy()

    df["tags_customer"] = df["tags_customer"].fillna("").astype(str)
    df["tags_internal"] = df["tags_internal"].fillna("").astype(str)

    lowercase_speakertype_dict = {
        str(k).strip().lower(): v for k, v in speakertype_dict.items()
    }

    # Step 1: Dictionary match
    mask_no_speaker = ~df["tags_customer"].str.contains("Type of Speaker", na=False)
    author_clean = (
        df["extra_author_attributes.name"].astype(str).str.strip().str.lower()
    )
    mapped_tags = author_clean.map(lowercase_speakertype_dict)

    step1_rows = mask_no_speaker & mapped_tags.notna()
    tags_to_add = mapped_tags[step1_rows]

    df.loc[step1_rows, "tags_customer"] = np.where(
        df.loc[step1_rows, "tags_customer"] == "",
        tags_to_add,
        df.loc[step1_rows, "tags_customer"] + "," + tags_to_add,
    )

    # Step 2: Tag isComment rows as 'Consumer Voice'
    mask_no_speaker = ~df["tags_customer"].str.contains("Type of Speaker", na=False)
    is_comment_mask = df["tags_internal"].str.contains("isComment", case=False, na=False)

    step2_rows = mask_no_speaker & is_comment_mask
    tag_consumer = "Type of Speaker/Consumer Voice"

    df.loc[step2_rows, "tags_customer"] = np.where(
        df.loc[step2_rows, "tags_customer"] == "",
        tag_consumer,
        df.loc[step2_rows, "tags_customer"] + "," + tag_consumer,
    )

    # Step 3: Fallback - tag remaining as 'Influencer & Page'
    mask_leftover = ~df["tags_customer"].str.contains("Type of Speaker", na=False)
    tag_influencer = "Type of Speaker/Influencer & Page"

    df.loc[mask_leftover, "tags_customer"] = np.where(
        df.loc[mask_leftover, "tags_customer"] == "",
        tag_influencer,
        df.loc[mask_leftover, "tags_customer"] + "," + tag_influencer,
    )

    return df


def load_speaker_dict(file_bytes):
    """
    Load speaker dictionary from Excel bytes.
    Returns dict: cleaned_username -> 'Type of Speaker/<Speaker Type>'
    """
    df = pd.read_excel(BytesIO(file_bytes))

    df["Username_clean"] = (
        df["Username"].astype(str).str.strip().str.lower()
    )

    speakertype_dict = dict(
        zip(
            df["Username_clean"],
            "Type of Speaker/" + df["Speaker Type"].astype(str),
        )
    )

    return speakertype_dict


def dict_df_to_dict(dict_df):
    """
    Convert a speaker dict DataFrame to a lookup dict.
    Expects columns: Username, Speaker Type
    """
    cleaned = dict_df["Username"].astype(str).str.strip().str.lower()
    speakertype_dict = dict(
        zip(
            cleaned,
            "Type of Speaker/" + dict_df["Speaker Type"].astype(str),
        )
    )
    return speakertype_dict


def process(speaker_dict_bytes, raw_data_bytes):
    """
    Takes file bytes for speaker dict and raw data,
    returns processed DataFrame with speaker tags in tags_customer column.

    Returns:
        tuple: (processed DataFrame, stats dict)
    """
    speakertype_dict = load_speaker_dict(speaker_dict_bytes)
    return _process_raw(raw_data_bytes, speakertype_dict)


def process_with_dict(raw_data_bytes, speakertype_dict):
    """
    Takes raw data bytes and an existing speaker dict,
    returns processed DataFrame with speaker tags.

    Returns:
        tuple: (processed DataFrame, stats dict)
    """
    return _process_raw(raw_data_bytes, speakertype_dict)


def _process_raw(raw_data_bytes, speakertype_dict):
    df = pd.read_excel(BytesIO(raw_data_bytes))

    if "Content" in df.columns:
        df.rename(columns={"Content": "Sample Content"}, inplace=True)

    df = apply_source_type_url_replacement(df)

    tagged_before = (
        df["tags_customer"]
        .fillna("")
        .astype(str)
        .str.contains("Type of Speaker", na=False)
        .sum()
    )

    df = update_speaker_tags(df, speakertype_dict)

    tagged_after = (
        df["tags_customer"]
        .fillna("")
        .astype(str)
        .str.contains("Type of Speaker", na=False)
        .sum()
    )

    stats = {
        "total_rows": len(df),
        "dict_loaded": len(speakertype_dict),
        "newly_tagged": tagged_after - tagged_before,
    }

    return df, stats
