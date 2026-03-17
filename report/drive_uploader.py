"""
Google Drive uploader — saves the generated .docx to Drive as a native
Google Doc (so it's directly editable in your browser) or as a Word file.

Uses the same service account as the Sheets client.
Share your target Drive folder with the service account email to grant write access.
"""

import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
]

SERVICE_ACCOUNT_PATH = os.getenv("GOOGLE_SERVICE_ACCOUNT_PATH", "config/service_account.json")
DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")  # optional target folder


def _get_drive_service():
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_PATH, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)


def upload_report(local_path: str, report_filename: str) -> str:
    """
    Upload a .docx file to Google Drive.

    - If GOOGLE_DRIVE_FOLDER_ID is set, file lands in that folder.
    - The file is uploaded as a native Google Doc (MIME conversion) so you
      can edit it directly in Google Docs without downloading.
    - Returns the URL of the uploaded Google Doc.
    """
    service = _get_drive_service()

    file_metadata = {
        "name": report_filename,
        # Convert to Google Docs format for in-browser editing
        "mimeType": "application/vnd.google-apps.document",
    }
    if DRIVE_FOLDER_ID:
        file_metadata["parents"] = [DRIVE_FOLDER_ID]

    media = MediaFileUpload(
        local_path,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        resumable=True,
    )

    uploaded = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id,webViewLink",
    ).execute()

    file_id = uploaded.get("id")
    url = uploaded.get("webViewLink", f"https://docs.google.com/document/d/{file_id}/edit")
    print(f"[drive] Uploaded → {url}")
    return url


def list_existing_reports(name_prefix: str = "Deal Desk Daily Report") -> list[dict]:
    """
    List existing reports in Drive matching the name prefix.
    Useful for deduplication or linking previous reports.
    """
    service = _get_drive_service()
    query = f"name contains '{name_prefix}' and trashed = false"
    if DRIVE_FOLDER_ID:
        query += f" and '{DRIVE_FOLDER_ID}' in parents"

    results = service.files().list(
        q=query,
        fields="files(id, name, createdTime, webViewLink)",
        orderBy="createdTime desc",
    ).execute()
    return results.get("files", [])
