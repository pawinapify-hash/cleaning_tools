from io import BytesIO

import pandas as pd

MESSAGE_TYPES = {
    "Message type/compliment": "Positiver",
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


def process_monthly_cleaning(ref_data_bytes, target_data_bytes, tasks):
    ref_df = pd.read_excel(BytesIO(ref_data_bytes))
    target_df = pd.read_excel(BytesIO(target_data_bytes))

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

    return target_df, all_stats
