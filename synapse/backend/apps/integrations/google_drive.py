"""
backend.apps.integrations.google_drive
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Google Drive service layer — OAuth2 flow + Drive API operations.

Phase 6.1 — Google Drive Integration (Week 17)

Tools implemented:
  - upload_to_drive(file_path, folder_name)
  - list_drive_files(folder_name)
  - create_drive_folder(folder_name)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Google OAuth2 scopes required
SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.environ.get(
    "GOOGLE_REDIRECT_URI",
    "http://localhost:8000/api/v1/integrations/drive/callback/",
)


# ── OAuth2 Flow ────────────────────────────────────────────────────────────────


def get_oauth2_authorization_url(state: str = "") -> str:
    """
    Build the Google OAuth2 authorization URL that the user visits to grant Drive access.
    Returns the URL string.
    """
    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [GOOGLE_REDIRECT_URI],
            }
        },
        scopes=SCOPES,
    )
    flow.redirect_uri = GOOGLE_REDIRECT_URI

    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )
    return authorization_url


def exchange_code_for_credentials(code: str) -> dict:
    """
    Exchange the OAuth2 authorization code for credentials.
    Returns a dict suitable for passing to GoogleDriveToken.set_credentials().
    """
    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [GOOGLE_REDIRECT_URI],
            }
        },
        scopes=SCOPES,
    )
    flow.redirect_uri = GOOGLE_REDIRECT_URI
    flow.fetch_token(code=code)

    creds = flow.credentials
    return {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes) if creds.scopes else SCOPES,
    }


def get_user_email(credentials_dict: dict) -> str:
    """Fetch the authenticated Google user's email address."""
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = _build_credentials(credentials_dict)
        service = build("oauth2", "v2", credentials=creds)
        user_info = service.userinfo().get().execute()
        return user_info.get("email", "")
    except Exception as exc:
        logger.warning("Could not fetch Google user email: %s", exc)
        return ""


# ── Drive API helpers ──────────────────────────────────────────────────────────


def _build_credentials(credentials_dict: dict):
    """Build a google.oauth2.credentials.Credentials from a stored dict."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    creds = Credentials(
        token=credentials_dict.get("token"),
        refresh_token=credentials_dict.get("refresh_token"),
        token_uri=credentials_dict.get(
            "token_uri", "https://oauth2.googleapis.com/token"
        ),
        client_id=credentials_dict.get("client_id", GOOGLE_CLIENT_ID),
        client_secret=credentials_dict.get("client_secret", GOOGLE_CLIENT_SECRET),
        scopes=credentials_dict.get("scopes", SCOPES),
    )

    # Auto-refresh if expired
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    return creds


def _get_drive_service(credentials_dict: dict):
    """Return an authenticated Google Drive API service object."""
    from googleapiclient.discovery import build

    creds = _build_credentials(credentials_dict)
    return build("drive", "v3", credentials=creds)


# ── Tool: create_drive_folder ──────────────────────────────────────────────────


def create_drive_folder(folder_name: str, credentials_dict: dict) -> str:
    """
    Create a folder in the user's Google Drive (if it doesn't already exist).
    Returns the folder ID.
    """
    service = _get_drive_service(credentials_dict)

    # Search for existing folder
    query = (
        f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder'"
        " and trashed=false"
    )
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])
    if files:
        folder_id = files[0]["id"]
        logger.info("Drive folder '%s' already exists: %s", folder_name, folder_id)
        return folder_id

    # Create new folder
    metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    folder = service.files().create(body=metadata, fields="id").execute()
    folder_id = folder.get("id")
    logger.info("Created Drive folder '%s': %s", folder_name, folder_id)
    return folder_id


# ── Tool: upload_to_drive ──────────────────────────────────────────────────────


def upload_to_drive(
    file_path: str,
    folder_name: str,
    credentials_dict: dict,
    file_name: Optional[str] = None,
) -> dict:
    """
    Upload a local file to a named Google Drive folder.

    Args:
        file_path:       Absolute path to the local file.
        folder_name:     Name of the Drive folder to upload into (created if missing).
        credentials_dict: Decrypted credentials from GoogleDriveToken.
        file_name:       Override the filename in Drive (defaults to basename).

    Returns:
        dict with {id, name, webViewLink, webContentLink}
    """
    import mimetypes

    from googleapiclient.http import MediaFileUpload

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    service = _get_drive_service(credentials_dict)
    folder_id = create_drive_folder(folder_name, credentials_dict)

    mime_type, _ = mimetypes.guess_type(str(path))
    mime_type = mime_type or "application/octet-stream"

    drive_name = file_name or path.name
    metadata = {
        "name": drive_name,
        "parents": [folder_id],
    }

    media = MediaFileUpload(str(path), mimetype=mime_type, resumable=True)
    uploaded = (
        service.files()
        .create(
            body=metadata,
            media_body=media,
            fields="id,name,webViewLink,webContentLink",
        )
        .execute()
    )

    logger.info(
        "Uploaded '%s' to Drive folder '%s': %s",
        drive_name,
        folder_name,
        uploaded.get("id"),
    )
    return uploaded


# ── Tool: list_drive_files ─────────────────────────────────────────────────────


def list_drive_files(folder_name: str, credentials_dict: dict) -> list[dict]:
    """
    List files inside a named Google Drive folder.

    Returns a list of dicts: {id, name, mimeType, size, modifiedTime, webViewLink}
    """
    service = _get_drive_service(credentials_dict)

    # Find folder id
    query = (
        f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder'"
        " and trashed=false"
    )
    results = service.files().list(q=query, fields="files(id, name)").execute()
    folders = results.get("files", [])
    if not folders:
        return []

    folder_id = folders[0]["id"]

    # List files in folder
    file_query = f"'{folder_id}' in parents and trashed=false"
    file_results = (
        service.files()
        .list(
            q=file_query,
            fields="files(id,name,mimeType,size,modifiedTime,webViewLink)",
            orderBy="modifiedTime desc",
        )
        .execute()
    )
    return file_results.get("files", [])


# ── Tool: export_as_google_doc ─────────────────────────────────────────────────


def export_as_google_doc(
    file_path: str,
    folder_name: str,
    credentials_dict: dict,
    doc_title: Optional[str] = None,
) -> dict:
    """
    Upload a DOCX/PDF file to Google Drive and convert it to a native Google Doc.
    Returns dict with {id, name, webViewLink}.
    """
    import mimetypes

    from googleapiclient.http import MediaFileUpload

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    service = _get_drive_service(credentials_dict)
    folder_id = create_drive_folder(folder_name, credentials_dict)

    mime_type, _ = mimetypes.guess_type(str(path))
    mime_type = mime_type or "application/octet-stream"

    name = doc_title or path.stem

    metadata = {
        "name": name,
        "parents": [folder_id],
        "mimeType": "application/vnd.google-apps.document",  # Convert to Google Doc
    }

    media = MediaFileUpload(str(path), mimetype=mime_type, resumable=True)
    uploaded = (
        service.files()
        .create(
            body=metadata,
            media_body=media,
            fields="id,name,webViewLink,webContentLink",
        )
        .execute()
    )

    logger.info("Exported '%s' as Google Doc: %s", name, uploaded.get("id"))
    return uploaded
