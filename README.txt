================================================================================
  update_speakerdict_from_raw_data.ipynb
================================================================================

SUMMARY
-------
This notebook processes a TalkWalker raw data export (Excel) and assigns a "Type of Speaker"
tag to every row in the tags_customer column.

It uses a speaker-type dictionary (username -> speaker type) as the primary source of truth,
then applies two fallback rules to tag any remaining untagged rows.

Rows that already contain a "Type of Speaker" tag (from TalkWalker or previous runs) are
left untouched — they are never overwritten or duplicated.


FOLDER STRUCTURE
----------------
Run the notebook from this directory:

  update_speakertype/
  |-- update_speakerdict_from_raw_data.ipynb   <-- this file
  |
  |-- SpeakerTypeDict/                         <-- speaker dictionary Excel file(s)
  |     |-- SpeakerTypeDict_YYYYMMDD.xlsx
  |
  |-- Input/                                   <-- TalkWalker raw data Excel file(s)
  |     |-- SCG_TalkWalkerRaw_X-Y.xlsx
  |
  |-- Output/                                  <-- processed output (auto-created)
        |-- SCG_TalkWalkerRaw_X-Y.xlsx


HOW TO RUN
----------
1. Place the speaker dictionary Excel in  SpeakerTypeDict/
2. Place the TalkWalker raw export Excel in  Input/
3. Open the notebook and run all cells (Run > Run All)
4. The output file appears in  Output/  (same filename as input)


STEP-BY-STEP EXPLANATION
------------------------

[Cell 1] Imports
    pandas, os, numpy

[Cell 2] Directory setup
    BASE_DIR = current working directory (the folder containing this notebook)
    speaker_dict_dir  = BASE_DIR / SpeakerTypeDict
    rawdata_dir       = BASE_DIR / Input
    output_dir        = BASE_DIR / Output

[Cell 3] Load speaker type dictionary
    - Reads the first .xlsx/.xls file in SpeakerTypeDict/
    - Normalizes the "Username" column: strip whitespace, lowercase
    - Builds a lookup dict:  cleaned_username -> "Type of Speaker/<Speaker Type>"
      Example:  "scg news" -> "Type of Speaker/Brand voice"

[Cell 4] Load raw data
    - Reads the first .xlsx/.xls file in Input/
    - If no file is found, creates an empty DataFrame (no processing)

[Cell 5] URL-to-author-name replacement
    - For certain source types (blogs, online news, message boards, newsletters, etc.)
      that often have unreliable author names, this step replaces the
      extra_author_attributes.name field with the domain name extracted from the
      article URL.
    - Example:  www.prachachart.com  ->  prachachart
    - Affected source_types:
        BLOG,BLOG_OTHER
        ONLINENEWS,ONLINENEWS_OTHER / _NEWSPAPER / _PRESSRELEASES /
          _MAGAZINE / _TVRADIO / _AGENCY
        MESSAGEBOARD,MESSAGEBOARD_OTHER
        NEWSLETTER,NEWSLETTER_SUBSTACK
        OTHER
    - Adds a boolean column "is_url_replaced" to track which rows were modified.

[Cell 6] update_speaker_tags() function definition
    This is the core logic. It tags every row with a speaker type using a
    3-step fallback strategy. Rows that already have a speaker type are skipped.

    Step 1 — Dictionary match
      Match the cleaned author name (extra_author_attributes.name) against the
      speaker type dictionary from Cell 3. Exact match only (case-insensitive).
      If the row has no speaker type tag yet:
        - append the mapped speaker type to tags_customer

    Step 2 — Comment detection
      Rows still missing a speaker type are checked for "isComment" in the
      tags_internal column. If found:
        - tag as "Type of Speaker/Consumer Voice"

    Step 3 — Fallback
      All remaining rows that still have no speaker type:
        - tag as "Type of Speaker/Influencer & Page"

    Notes:
      - NaN tags_customer values are treated as empty strings.
      - The "Type of Speaker" check is re-evaluated after each step so that
        rows tagged in an earlier step are not re-tagged in a later step.
      - If tags_customer already has other (non-speaker) tags, the new speaker
        tag is appended with a comma separator.

[Cell 7] Execute tagging
    Calls update_speaker_tags() on the loaded raw data with the loaded dictionary.

[Cell 8] Save output
    Writes the updated DataFrame to Output/ with the same filename as the input.
    The strings_to_urls=False option suppresses xlsxwriter warnings about Excel's
    65,530 URL-per-worksheet limit (URLs are still written as plain text).


NOTES
-----
- This notebook was originally designed for Google Colab. It has been modified to
  run locally using the folder structure described above.
- The output is always a single Excel file matching the input filename.
- If a row already has 2 speaker types from the source data (e.g. Brand voice,Publisher),
  they are preserved as-is. The script only tags rows that have zero speaker types.
