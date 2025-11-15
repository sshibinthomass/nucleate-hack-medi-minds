import os
import base64
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("gmail")

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

    GMAIL_AVAILABLE = True
except ImportError:
    GMAIL_AVAILABLE = False
    print(
        "Warning: Gmail API libraries not installed. Install with: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client"
    )


class GmailService:
    """Service for sending emails via Gmail API."""

    SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

    def __init__(self):
        self.service = None
        self._authenticate()

    def _authenticate(self) -> None:
        """Authenticate with Gmail API."""
        if not GMAIL_AVAILABLE:
            print("Gmail API libraries not available")
            return

        creds = None
        # Get paths relative to backend directory
        current_file = Path(__file__).resolve()
        backend_dir = (
            current_file.parent.parent.parent.parent
        )  # Go up to backend directory
        token_path = os.getenv(
            "GMAIL_TOKEN_PATH", str(backend_dir / "gmail_token.json")
        )

        # Try to find client secret file in backend directory
        credentials_path = os.getenv("GMAIL_CREDENTIALS_PATH")
        if not credentials_path:
            # Look for client_secret*.json files in backend directory
            client_secret_files = list(backend_dir.glob("client_secret*.json"))
            if client_secret_files:
                credentials_path = str(client_secret_files[0])
            else:
                credentials_path = str(backend_dir / "client_secret.json")

        # Load existing token if available
        if os.path.exists(token_path):
            try:
                creds = Credentials.from_authorized_user_file(token_path, self.SCOPES)
            except Exception as e:
                print(f"Error loading token: {e}")

        # If no valid credentials, try to get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    print(f"Error refreshing token: {e}")
                    creds = None

            if not creds:
                if not os.path.exists(credentials_path):
                    print(f"Gmail credentials not found at {credentials_path}")
                    print("Please set GMAIL_CREDENTIALS_PATH environment variable")
                    return

                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        credentials_path, self.SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                except Exception as e:
                    print(f"Error during OAuth flow: {e}")
                    return

            # Save credentials for next time
            try:
                with open(token_path, "w") as token:
                    token.write(creds.to_json())
            except Exception as e:
                print(f"Error saving token: {e}")

        if creds:
            try:
                self.service = build("gmail", "v1", credentials=creds)
                print("Gmail service authenticated successfully")
            except Exception as e:
                print(f"Error building Gmail service: {e}")

    def send_email(
        self, to: str, subject: str, body: str, body_type: str = "plain"
    ) -> dict:
        """
        Send an email via Gmail.

        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body content
            body_type: 'plain' or 'html'

        Returns:
            dict with status and message
        """
        if not self.service:
            return {
                "status": "error",
                "message": "Gmail service not authenticated. Please check credentials.",
            }

        try:
            # Create message
            message = MIMEMultipart("alternative")
            message["to"] = to
            message["subject"] = subject

            # Add body
            if body_type == "html":
                part = MIMEText(body, "html")
            else:
                part = MIMEText(body, "plain")

            message.attach(part)

            # Encode message
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

            # Send message
            send_message = (
                self.service.users()
                .messages()
                .send(userId="me", body={"raw": raw_message})
                .execute()
            )

            return {
                "status": "success",
                "message": f"Email sent successfully to {to}",
                "message_id": send_message.get("id"),
            }

        except HttpError as error:
            return {
                "status": "error",
                "message": f"Gmail API error: {error.content.decode('utf-8') if hasattr(error, 'content') else str(error)}",
            }
        except Exception as e:
            return {"status": "error", "message": f"Error sending email: {str(e)}"}


# Initialize Gmail service
gmail_service = GmailService()


@mcp.tool()
async def gmail_send_email(
    to: str, subject: str, body: str, body_type: str = "plain"
) -> str:
    """
    Send an email via Gmail.

    All emails are sent to shibint85@gmail.com regardless of the 'to' parameter.

    Args:
        to: Recipient email (ignored, always sends to shibint85@gmail.com)
        subject: Email subject
        body: Email body content
        body_type: 'plain' or 'html' (default: 'plain')

    Returns:
        JSON string with status and message
    """
    import json

    # Override recipient to always send to shibint85@gmail.com
    recipient_email = "shibint85@gmail.com"

    result = gmail_service.send_email(recipient_email, subject, body, body_type)
    return json.dumps(result, indent=2)


def test_send_email(
    to: str = "test@example.com",
    subject: str = "Test Email",
    body: str = "This is a test email.",
) -> dict:
    """
    Default test function to send a test email.

    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body

    Returns:
        dict with status and message
    """
    return gmail_service.send_email(to, subject, body, "plain")


if __name__ == "__main__":
    import sys

    # If run with --test argument, run test function
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        print("Running Gmail test...")
        result = test_send_email()
        import json

        print(json.dumps(result, indent=2))
    else:
        # Run the MCP server
        mcp.run()
