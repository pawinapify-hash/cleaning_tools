================================================================================
  Cleaning Tools
================================================================================

A Streamlit web app with two production-ready features:
  1. Speaker Tag Updater
  2. Monthly Cleaning Process


FEATURES
--------

Speaker Tag Updater
~~~~~~~~~~~~~~~~~~~
Tags TalkWalker export data with speaker types (Brand Voice, Consumer Voice,
Influencer & Page, Publisher) using a dictionary stored in Google Sheets.

Process:
  a) Preprocesses author names by extracting domain names from URLs
     for selected source types (blog, online news, newsletter, etc.).
  b) Matches author names against dictionary values (exact, case-insensitive).
  c) Tags rows with "isComment" as Consumer Voice.
  d) Fallback: tags remaining rows as Influencer & Page.

Monthly Cleaning Process
~~~~~~~~~~~~~~~~~~~~~~~~
Monthly Cleaning is now available with 4 main subtasks:

  1) Update Sticker Sentiment
     - Uses the Reference file to update "Sentiment" in the Target file
       by matching URL.
     - Applies sentiment from Message type tags:
         Message type/compliment    -> Positive
         Message type/information   -> Neutral
         Message type/participation -> Neutral
         Message type/complaint     -> Negative

  2) Remove Campaign Rows
     - Removes rows from the Target file when URL matches Reference rows
       that contain "Campaign/" tags.

  3) Remove Hide
     - Removes rows where both columns are "Hide":
         ShowCorporate
         ShowCBM/SCGP/SCGC/SCGD

  4) Duplicate URL Check
     - Finds duplicate links from column "URL" after core cleaning tasks finish.
     - Shows only duplicate URL rows in an editable review table.
     - Users can edit values directly, mark rows for deletion, then click
       "Confirm Duplicate Review" before export is unlocked.
     - If this feature is enabled and duplicates are found, output export is
       blocked until confirmation is completed.

After processing, users can download the cleaned output file directly from UI.


PROJECT FILES
-------------
app.py                  Streamlit web app (UI + Google OAuth + both features)
speaker_tagger.py       Speaker tagging core logic
monthly_cleaning.py     Monthly cleaning core logic (4 subtasks incl. duplicate review)
requirements.txt        Python dependencies
readme.txt              This file
.streamlit/             Streamlit config and secrets
.gitignore              Excludes secrets, tokens, and temp files


LOCAL SETUP
-----------
1. Install dependencies:
      pip install -r requirements.txt

2. Create a Google Cloud OAuth 2.0 client:
   - Go to https://console.cloud.google.com/apis/credentials
   - Create OAuth 2.0 Client ID > Web application
   - Add authorized redirect URIs:
        http://localhost:8511
        https://speakertype-tagging.streamlit.app
   - Add authorized JavaScript origins:
        http://localhost:8511
        https://speakertype-tagging.streamlit.app
   - Download the JSON file, rename to oauth_client.json,
     and place it in the project root

3. Enable the Google Sheets API:
   - https://console.cloud.google.com/apis/library/sheets.googleapis.com

4. Create .streamlit/secrets.toml:
      [oauth]
      client_id = "..."
      client_secret = "..."

5. Run the app:
      streamlit run app.py --server.port 8511

6. Open http://localhost:8511 in your browser.


MONTHLY CLEANING INPUT REQUIREMENTS
-----------------------------------
Reference file should include at least:
  - url
  - content
  - tags_customer

Target file should include at least:
  - URL
  - Sentiment                    (for sentiment update)
  - ShowCorporate                (for Remove Hide)
  - ShowCBM/SCGP/SCGC/SCGD       (for Remove Hide)


STREAMLIT CLOUD DEPLOYMENT
--------------------------
1. Deploy this repo to Streamlit Cloud.

2. Go to your app's Settings > Secrets and paste:
      [oauth]
      client_id = "..."
      client_secret = "..."

3. The app auto-detects redirect URI:
      Local:       http://localhost:8511
      Deployed:    https://speakertype-tagging.streamlit.app

4. Make sure both URIs are listed in the OAuth client authorized
   redirect URIs in Google Cloud Console.


GOOGLE SHEET (SPEAKER TAG UPDATER)
----------------------------------
Speaker Tag Updater reads from a fixed Google Sheet URL
(FIXED_SHEET_URL in app.py). The first worksheet must contain:

    Username      Speaker Type
    ----------    ----------------
    SCG News      Brand Voice
    prachachart   Publisher
    ...

The signed-in Google account must have Viewer access to this sheet.


NOTES
-----
- Existing "Type of Speaker" tags in tags_customer are preserved.
- "Newly Tagged" counts only tags added in the current run.
- Monthly Cleaning shows per-task stats (updated/removed), tag distribution,
  and unmatched reference URL count when applicable.
- Duplicate URL Check requires review confirmation before final export when
  duplicate rows are found.
