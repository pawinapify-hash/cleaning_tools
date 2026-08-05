================================================================================
  Cleaning Tools
================================================================================

A Streamlit web app with two main features:
  1. Speaker Tag Updater - tags TalkWalker export data with speaker types
  2. Monthly Cleaning Process - coming soon


FEATURES
--------

Speaker Tag Updater
~~~~~~~~~~~~~~~~~~~
Tags TalkWalker export data with speaker types (Brand Voice, Consumer Voice,
Influencer & Page, Publisher) using a dictionary stored in Google Sheets.

Process:
  a) Preprocesses author names by extracting domain names from URLs
     for certain source types (blogs, online news, newsletters, etc.).
  b) Matches author names against the dictionary (exact, case-insensitive).
  c) Tags "isComment" rows as Consumer Voice.
  d) Fallback: tags remaining rows as Influencer & Page.

Monthly Cleaning Process
~~~~~~~~~~~~~~~~~~~~~~~~
Coming soon.


PROJECT FILES
-------------
app.py                  Streamlit web app (UI + Google OAuth)
speaker_tagger.py       Core tagging logic (process_with_dict(), update_speaker_tags())
requirements.txt        Python dependencies
README.txt              This file
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
   - Download the JSON > rename to oauth_client.json > place in this folder

3. Enable the Google Sheets API:
   - https://console.cloud.google.com/apis/library/sheets.googleapis.com

4. Create .streamlit/secrets.toml from oauth_client.json:
      [oauth]
      client_id = "..."
      client_secret = "..."

5. Run the app:
      streamlit run app.py --server.port 8511

6. Open http://localhost:8511 in your browser.


STREAMLIT CLOUD DEPLOYMENT
--------------------------
1. Deploy this repo to Streamlit Cloud.

2. Go to your app's Settings > Secrets and paste:
      [oauth]
      client_id = "..."
      client_secret = "..."

3. The app auto-detects the environment and uses the correct
   redirect URI:
      Local:       http://localhost:8511
      Deployed:    https://speakertype-tagging.streamlit.app

4. Make sure both URIs are in the OAuth client authorized redirect
   URIs in Google Cloud Console.


GOOGLE SHEET
------------
The Speaker Tag Updater reads from a fixed Google Sheet URL
(FIXED_SHEET_URL in app.py). The sheet must have these columns
in the first worksheet:

    Username      Speaker Type
    ----------    ----------------
    SCG News      Brand Voice
    prachachart   Publisher
    ...

The user's Google account must have Viewer access to the sheet.


NOTE
----
Rows that already contain a "Type of Speaker" tag in tags_customer
are left untouched. The "Newly Tagged" metric counts only rows tagged
during the current run, excluding pre-existing tags.
