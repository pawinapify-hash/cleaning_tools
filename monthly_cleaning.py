from io import BytesIO

import pandas as pd

MESSAGE_TYPES = {
    "Message type/compliment": "Positive",
    "Message type/information": "Neutral",
    "Message type/participation": "Neutral",
    "Message type/complaint": "Negative",
}


def update_sticker_sentiment(ref_df, target_df):
    target_df = target_df.copy()

    mask_blank_content = ref_df["content"].isna() | (ref_df["content"].astype(str).str.strip() == "")
    mask_message_type = ref_df["tags_customer"].fillna("").str.contains("Message type/", na=False)
    relevant = ref_df[mask_blank_content & mask_message_type]

    if relevant.empty:
        return target_df, {"updated": 0, "distribution": {}, "unmatched": 0}

    tags = relevant["tags_customer"].fillna("")
    sentiment = pd.Series(None, index=relevant.index, dtype=object)
    for key, value in MESSAGE_TYPES.items():
        sentiment[tags.str.contains(key, na=False, regex=False)] = value

    distribution = sentiment.value_counts().to_dict()

    url_series = relevant["url"].astype(str).str.strip()
    url_map = pd.Series(sentiment.values, index=url_series).dropna()

    target_urls = target_df["URL"].astype(str).str.strip()
    matched = target_urls.isin(url_map.index)
    target_df.loc[matched, "Sentiment"] = target_urls[matched].map(url_map)

    unmatched = len(url_map) - matched.sum()

    return target_df, {"updated": matched.sum(), "distribution": distribution, "unmatched": unmatched}


def remove_campaign_rows(ref_df, target_df):
    campaign_mask = ref_df["tags_customer"].fillna("").str.contains("Campaign/", na=False)
    campaign_rows = ref_df[campaign_mask]

    if campaign_rows.empty:
        return target_df, {"removed": 0, "distribution": {}, "unmatched": 0}

    campaign_tags = campaign_rows["tags_customer"].str.extract(r"(Campaign/[^,]+)", expand=False)
    distribution = campaign_tags.value_counts().to_dict()

    campaign_urls = set(campaign_rows["url"].astype(str).str.strip())
    target_urls = target_df["URL"].astype(str).str.strip()

    before = len(target_df)
    matched = target_urls.isin(campaign_urls)
    target_df = target_df[~matched]
    after = len(target_df)

    unmatched = len(campaign_urls) - matched.sum()

    return target_df, {"removed": before - after, "distribution": distribution, "unmatched": unmatched}


def remove_hide(target_df):
    before = len(target_df)

    col_show_corp = "ShowCorporate"
    col_show_cbm = "ShowCBM/SCGP/SCGC/SCGD"

    has_both = (col_show_corp in target_df.columns) and (col_show_cbm in target_df.columns)
    if not has_both:
        return target_df, {"removed": 0}

    hide_mask = (
        (target_df[col_show_corp].astype(str).str.strip() == "Hide")
        & (target_df[col_show_cbm].astype(str).str.strip() == "Hide")
    )
    target_df = target_df[~hide_mask]
    after = len(target_df)

    return target_df, {"removed": before - after}


def match_comment_pillar_to_post(target_df):
    target_df = target_df.copy()

    required_cols = ["URL", "ParentURL", "Category", "Sub Category"]
    missing_cols = [col for col in required_cols if col not in target_df.columns]
    if missing_cols:
        return target_df, {
            "updated": 0,
            "unmatched": 0,
            "missing_columns": missing_cols,
            "post_summary": pd.DataFrame(columns=["Post URL", "Updated Comments"]),
            "changed_examples": pd.DataFrame(),
            "unmatched_label": "comments have ParentURL but no matching post URL",
        }

    target_df["_mc_row_id"] = range(len(target_df))

    parent_clean = target_df["ParentURL"].astype(str).str.strip()
    parent_has_value = target_df["ParentURL"].notna() & (parent_clean != "")

    post_clean = target_df["URL"].astype(str).str.strip()
    post_has_value = target_df["URL"].notna() & (post_clean != "")

    post_lookup = (
        target_df.loc[post_has_value, ["URL", "Category", "Sub Category"]]
        .assign(_url_clean=post_clean[post_has_value])
        .drop_duplicates(subset="_url_clean", keep="first")
        .set_index("_url_clean")
    )

    matched_mask = parent_has_value & parent_clean.isin(post_lookup.index)
    unmatched = int(parent_has_value.sum() - matched_mask.sum())

    if matched_mask.sum() == 0:
        target_df.drop(columns=["_mc_row_id"], inplace=True)
        return target_df, {
            "updated": 0,
            "unmatched": unmatched,
            "post_summary": pd.DataFrame(columns=["Post URL", "Updated Comments"]),
            "changed_examples": pd.DataFrame(),
            "unmatched_label": "comments have ParentURL but no matching post URL",
        }

    mapped_category = parent_clean[matched_mask].map(post_lookup["Category"])
    mapped_sub_category = parent_clean[matched_mask].map(post_lookup["Sub Category"])

    before_category = target_df.loc[matched_mask, "Category"].copy()
    before_sub_category = target_df.loc[matched_mask, "Sub Category"].copy()

    before_category_cmp = before_category.fillna("").astype(str)
    before_sub_cmp = before_sub_category.fillna("").astype(str)
    after_category_cmp = mapped_category.fillna("").astype(str)
    after_sub_cmp = mapped_sub_category.fillna("").astype(str)

    changed_rows = (before_category_cmp != after_category_cmp) | (before_sub_cmp != after_sub_cmp)

    target_df.loc[matched_mask, "Category"] = mapped_category.values
    target_df.loc[matched_mask, "Sub Category"] = mapped_sub_category.values

    changed_index = mapped_category.index[changed_rows]
    updated = int(len(changed_index))

    if updated == 0:
        target_df.drop(columns=["_mc_row_id"], inplace=True)
        return target_df, {
            "updated": 0,
            "unmatched": unmatched,
            "post_summary": pd.DataFrame(columns=["Post URL", "Updated Comments"]),
            "changed_examples": pd.DataFrame(),
            "unmatched_label": "comments have ParentURL but no matching post URL",
        }

    changed_examples = pd.DataFrame(
        {
            "_mc_row_id": target_df.loc[changed_index, "_mc_row_id"].values,
            "ParentURL": target_df.loc[changed_index, "ParentURL"].astype(str).str.strip().values,
            "Comment URL": target_df.loc[changed_index, "URL"].values,
            "Category (Before)": before_category.loc[changed_index].values,
            "Category (After)": target_df.loc[changed_index, "Category"].values,
            "Sub Category (Before)": before_sub_category.loc[changed_index].values,
            "Sub Category (After)": target_df.loc[changed_index, "Sub Category"].values,
        }
    )

    post_summary = (
        changed_examples.groupby("ParentURL", dropna=False)
        .size()
        .reset_index(name="Updated Comments")
        .rename(columns={"ParentURL": "Post URL"})
        .sort_values("Updated Comments", ascending=False)
        .reset_index(drop=True)
    )

    target_df.drop(columns=["_mc_row_id"], inplace=True)

    return target_df, {
        "updated": updated,
        "unmatched": unmatched,
        "post_summary": post_summary,
        "changed_examples": changed_examples,
        "unmatched_label": "comments have ParentURL but no matching post URL",
    }


def find_duplicate_urls(target_df):
    target_df = target_df.copy()

    if "URL" not in target_df.columns:
        return pd.DataFrame(columns=["Delete"])

    target_df["_row_id"] = range(len(target_df))

    url_clean = target_df["URL"].astype(str).str.strip()
    non_blank = target_df["URL"].notna() & (url_clean != "")
    dup_mask = non_blank & url_clean.duplicated(keep=False)

    dup_df = target_df.loc[dup_mask].copy()
    if dup_df.empty:
        return dup_df

    dup_df.insert(0, "Delete", False)
    dup_df = dup_df.sort_values(["URL", "_row_id"], kind="stable")
    dup_df.reset_index(drop=True, inplace=True)
    return dup_df


def process_monthly_cleaning(ref_data_bytes, target_data_bytes, tasks):
    target_df = pd.read_excel(BytesIO(target_data_bytes))

    needs_ref = tasks.get("update_sticker_sentiment") or tasks.get("remove_campaign_rows")
    ref_df = None
    if needs_ref:
        if ref_data_bytes is None:
            raise ValueError("Reference file is required for selected subtasks")
        ref_df = pd.read_excel(BytesIO(ref_data_bytes))

    all_stats = {}

    if tasks.get("update_sticker_sentiment"):
        target_df, stats = update_sticker_sentiment(ref_df, target_df)
        all_stats["Sticker Sentiment"] = stats

    if tasks.get("remove_campaign_rows"):
        target_df, stats = remove_campaign_rows(ref_df, target_df)
        all_stats["Campaign Rows"] = stats

    if tasks.get("remove_hide"):
        target_df, stats = remove_hide(target_df)
        all_stats["Hide Rows"] = stats

    if tasks.get("match_comment_pillar_to_post"):
        target_df, stats = match_comment_pillar_to_post(target_df)
        all_stats["Match Comment Pillar to Post"] = stats

    return target_df, all_stats
