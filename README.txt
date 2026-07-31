================================================================================
  Speaker Tag Updater
================================================================================

A Streamlit web app that tags TalkWalker export data with speaker types
(Brand Voice, Consumer Voice, Influencer & Page, Publisher) using a
dictionary stored in Google Sheets.


HOW IT WORKS
------------
1. User signs in with their Google account (one time).
2. App reads the speaker dictionary from a Google Sheet.
3. User drops a TalkWalker raw data Excel file.
4. App tags every row using a 3-step fallback strategy:
   a) Match author name against the dictionary (exact, case-insensitive).
   b) Tag "isComment" rows as Consumer Voice.
   c) Fallback: tag remaining rows as Influencer & Page.
5. User downloads the tagged Excel file.


PROJECT FILES
-------------
app.py                  Streamlit web app (UI + Google OAuth)
speaker_tagger.py       Core tagging logic (process(), update_speaker_tags())
requirements.txt        Python dependencies
README.txt              This file

.gitignore              Excludes secrets, tokens, and temp files

update_speakerdict_from_raw_data.ipynb   Original notebook (legacy)
SpeakerTypeDict/        Local dictionary folder (legacy, not used by app)
Input/                  Local input folder (legacy, not used by app)
Output/                 Local output folder (legacy, not used by app)


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
The app reads from a fixed Google Sheet URL (FIXED_SHEET_URL in app.py).
The sheet must have these columns in the first worksheet:

    Username      Speaker Type
    ----------    ----------------
    SCG News      Brand Voice
    prachachart   Publisher
    ...

The user's Google account must have Viewer access to the sheet.


NOTE
----
Rows that already contain a "Type of Speaker" tag in tags_customer
(from TalkWalker) are left untouched. The "Newly Tagged" metric counts
only rows tagged during the current run, excluding pre-existing tags.
