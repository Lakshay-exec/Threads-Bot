"""
get_token.py
Automated token retriever and validator for Meta Threads.

Features:
1. Quick Token Exchange & ID Resolver:
   Paste any token generated from Meta Developer Portal to verify it,
   automatically exchange it for a 60-day long-lived token, and resolve
   your numeric THREADS_USER_ID instantly.
2. Automated OAuth 2.0 Browser Flow:
   Provide your Meta App ID and App Secret to launch your browser,
   authorize your Threads account, and automatically retrieve:
   - 60-day long-lived THREADS_ACCESS_TOKEN
   - Numeric THREADS_USER_ID
3. Auto-save credentials to .env file for local testing.
"""
import os
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse
import requests

BASE_GRAPH_URL = "https://graph.threads.net"
REDIRECT_URI = "http://localhost:5000/callback"


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    auth_code = None

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if "code" in params:
            code = params["code"][0]
            # Meta appends '#_' to auth codes which must be removed
            if code.endswith("#_"):
                code = code[:-2]
            OAuthCallbackHandler.auth_code = code

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html = """
            <html>
                <body style="font-family: sans-serif; text-align: center; padding: 50px;">
                    <h1 style="color: #28a745;">Authorization Successful!</h1>
                    <p>You can close this tab and return to your terminal.</p>
                </body>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
        else:
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Authorization failed or code missing.")

    def log_message(self, format, *args):
        # Suppress server logging for clean terminal output
        return


def get_user_profile(token: str) -> dict:
    """Fetches user ID and username from Meta Threads Graph API."""
    url = f"{BASE_GRAPH_URL}/v1.0/me"
    params = {
        "fields": "id,username",
        "access_token": token,
    }
    res = requests.get(url, params=params, timeout=30)
    res.raise_for_status()
    return res.json()


def exchange_code_for_short_token(app_id: str, app_secret: str, code: str) -> str:
    """Exchanges an authorization code for a short-lived user token."""
    url = f"{BASE_GRAPH_URL}/oauth/access_token"
    payload = {
        "client_id": app_id,
        "client_secret": app_secret,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
        "code": code,
    }
    res = requests.post(url, data=payload, timeout=30)
    res.raise_for_status()
    data = res.json()
    token = data.get("access_token")
    if not token:
        raise ValueError(f"No access_token in response: {data}")
    return token


def exchange_for_long_lived_token(token: str, app_secret: str) -> str:
    """Exchanges a short-lived token for a 60-day long-lived access token."""
    url = f"{BASE_GRAPH_URL}/access_token"
    params = {
        "grant_type": "th_exchange_token",
        "client_secret": app_secret,
        "access_token": token,
    }
    res = requests.get(url, params=params, timeout=30)
    res.raise_for_status()
    data = res.json()
    long_token = data.get("access_token")
    if not long_token:
        raise ValueError(f"Failed to get long-lived token: {data}")
    return long_token


def save_to_env(token: str, user_id: str, gemini_key: str = ""):
    """Saves or updates .env with the retrieved credentials."""
    env_lines = []
    if os.path.exists(".env"):
        with open(".env", "r", encoding="utf-8") as f:
            env_lines = f.readlines()

    updated_keys = set()
    new_lines = []
    for line in env_lines:
        line_strip = line.strip()
        if line_strip.startswith("THREADS_ACCESS_TOKEN="):
            new_lines.append(f"THREADS_ACCESS_TOKEN={token}\n")
            updated_keys.add("THREADS_ACCESS_TOKEN")
        elif line_strip.startswith("THREADS_USER_ID="):
            new_lines.append(f"THREADS_USER_ID={user_id}\n")
            updated_keys.add("THREADS_USER_ID")
        elif line_strip.startswith("GEMINI_API_KEY=") and gemini_key:
            new_lines.append(f"GEMINI_API_KEY={gemini_key}\n")
            updated_keys.add("GEMINI_API_KEY")
        else:
            new_lines.append(line)

    if "THREADS_ACCESS_TOKEN" not in updated_keys:
        new_lines.append(f"THREADS_ACCESS_TOKEN={token}\n")
    if "THREADS_USER_ID" not in updated_keys:
        new_lines.append(f"THREADS_USER_ID={user_id}\n")
    if gemini_key and "GEMINI_API_KEY" not in updated_keys:
        new_lines.append(f"GEMINI_API_KEY={gemini_key}\n")

    with open(".env", "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    print("Saved credentials to local .env file.")


def run_oauth_flow():
    """Runs automated browser OAuth flow."""
    print("\n--- Meta Threads Automated OAuth 2.0 Flow ---")
    print("Find your App ID & App Secret in Meta for Developers > App settings > Basic")
    app_id = input("Enter Threads App ID: ").strip()
    app_secret = input("Enter Threads App Secret: ").strip()

    if not app_id or not app_secret:
        print("Error: App ID and App Secret are required.")
        return

    scopes = "threads_basic,threads_content_publish,threads_read_replies,threads_manage_replies"
    auth_url = (
        f"https://threads.net/oauth/authorize?"
        f"client_id={app_id}&redirect_uri={REDIRECT_URI}&scope={scopes}&response_type=code"
    )

    print(f"\nStarting temporary local callback server on {REDIRECT_URI}...")
    server = HTTPServer(("localhost", 5000), OAuthCallbackHandler)

    print(f"Opening browser to authorize Threads: {auth_url}\n")
    webbrowser.open(auth_url)

    print("Waiting for you to click 'Authorize' in your browser...")
    server.handle_request()

    code = OAuthCallbackHandler.auth_code
    if not code:
        print("Failed to capture authorization code.")
        return

    print("Captured authorization code! Exchanging for short-lived token...")
    short_token = exchange_code_for_short_token(app_id, app_secret, code)

    print("Exchanging for 60-day long-lived token...")
    long_token = exchange_for_long_lived_token(short_token, app_secret)

    print("Retrieving Threads User ID...")
    profile = get_user_profile(long_token)
    user_id = profile.get("id")
    username = profile.get("username", "unknown")

    print("\n" + "=" * 60)
    print("TOKEN RETRIEVAL SUCCESSFUL!")
    print("=" * 60)
    print(f"Threads Username : @{username}")
    print(f"THREADS_USER_ID  : {user_id}")
    print(f"THREADS_ACCESS_TOKEN : {long_token}")
    print("=" * 60)

    save = input("\nSave these to .env file for local testing? (y/n): ").strip().lower()
    if save == "y":
        save_to_env(long_token, str(user_id))

    print("\nNext step: Add these to your GitHub Repository Secrets:")
    print("https://github.com/Lakshay-exec/Threads-Bot/settings/secrets/actions")


def run_quick_resolve():
    """Validates an existing token and fetches the User ID."""
    print("\n--- Quick Token Validator & ID Resolver ---")
    token = input("Paste your Threads Access Token: ").strip()

    if not token:
        print("Error: Token cannot be empty.")
        return

    # Check if user also has app secret for 60-day exchange
    app_secret = input("Enter App Secret (optional, press Enter to skip): ").strip()
    if app_secret:
        try:
            print("Attempting exchange for 60-day long-lived token...")
            token = exchange_for_long_lived_token(token, app_secret)
            print("Upgraded to 60-day long-lived token!")
        except Exception as e:
            print(f"Notice: Using provided token directly ({e})")

    try:
        print("Verifying token with Meta Threads API...")
        profile = get_user_profile(token)
        user_id = profile.get("id")
        username = profile.get("username", "unknown")

        print("\n" + "=" * 60)
        print("TOKEN VALIDATION SUCCESSFUL!")
        print("=" * 60)
        print(f"Threads Username : @{username}")
        print(f"THREADS_USER_ID  : {user_id}")
        print(f"THREADS_ACCESS_TOKEN : {token}")
        print("=" * 60)

        save = input("\nSave these to .env file for local testing? (y/n): ").strip().lower()
        if save == "y":
            save_to_env(token, str(user_id))

        print("\nAdd these values to GitHub Secrets:")
        print("https://github.com/Lakshay-exec/Threads-Bot/settings/secrets/actions")

    except Exception as e:
        print(f"Error validating token: {e}")


def main():
    print("=" * 60)
    print("Meta Threads Token Utility")
    print("=" * 60)
    print("1. Automatic Browser OAuth 2.0 (Launches browser & retrieves 60-day token)")
    print("2. Quick Token Validator (Paste token -> Resolves User ID & validates)")
    print("=" * 60)
    choice = input("Select an option (1 or 2): ").strip()

    if choice == "1":
        run_oauth_flow()
    elif choice == "2":
        run_quick_resolve()
    else:
        print("Invalid choice. Exiting.")


if __name__ == "__main__":
    main()
