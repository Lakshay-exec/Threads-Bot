"""
get_token.py
Automated token retriever, OAuth handler, and GitHub Secrets uploader for Meta Threads.

Supports both interactive prompts and CLI flags:
  python get_token.py --app-id <ID> --app-secret <SECRET>
  python get_token.py --token <TOKEN> [--app-secret <SECRET>]
"""
import argparse
import base64
import os
import subprocess
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse
import requests

try:
    from nacl import encoding as nacl_encoding, public as nacl_public
    HAS_NACL = True
except ImportError:
    HAS_NACL = False

BASE_GRAPH_URL = "https://graph.threads.net"
REDIRECT_URI = "http://localhost:5000/callback"
REPO_NAME = "Lakshay-exec/Threads-Bot"


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    auth_code = None

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if "code" in params:
            code = params["code"][0]
            if code.endswith("#_"):
                code = code[:-2]
            OAuthCallbackHandler.auth_code = code

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html = """
            <html>
                <body style="font-family: sans-serif; text-align: center; padding: 50px; background: #0f172a; color: #f8fafc;">
                    <h1 style="color: #22c55e;">Authentication Successful!</h1>
                    <p style="font-size: 18px;">Your Threads account is now connected. You can close this tab and return to your terminal.</p>
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
        return


def get_user_profile(token: str) -> dict:
    url = f"{BASE_GRAPH_URL}/v1.0/me"
    params = {"fields": "id,username", "access_token": token}
    res = requests.get(url, params=params, timeout=30)
    res.raise_for_status()
    return res.json()


def exchange_code_for_short_token(app_id: str, app_secret: str, code: str) -> str:
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
        raise ValueError(f"No access_token returned: {data}")
    return token


def exchange_for_long_lived_token(token: str, app_secret: str) -> str:
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
        raise ValueError(f"Failed to obtain 60-day token: {data}")
    return long_token


def save_to_env(token: str, user_id: str):
    env_lines = []
    if os.path.exists(".env"):
        with open(".env", "r", encoding="utf-8") as f:
            env_lines = f.readlines()

    updated = set()
    new_lines = []
    for line in env_lines:
        line_strip = line.strip()
        if line_strip.startswith("THREADS_ACCESS_TOKEN="):
            new_lines.append(f"THREADS_ACCESS_TOKEN={token}\n")
            updated.add("THREADS_ACCESS_TOKEN")
        elif line_strip.startswith("THREADS_USER_ID="):
            new_lines.append(f"THREADS_USER_ID={user_id}\n")
            updated.add("THREADS_USER_ID")
        else:
            new_lines.append(line)

    if "THREADS_ACCESS_TOKEN" not in updated:
        new_lines.append(f"THREADS_ACCESS_TOKEN={token}\n")
    if "THREADS_USER_ID" not in updated:
        new_lines.append(f"THREADS_USER_ID={user_id}\n")

    with open(".env", "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    print("Saved credentials to local .env file.")


def get_git_credential_token() -> str | None:
    try:
        p = subprocess.run(
            ["git", "credential", "fill"],
            input="protocol=https\nhost=github.com\n",
            text=True,
            capture_output=True,
        )
        for line in p.stdout.splitlines():
            if line.startswith("password="):
                return line.split("password=")[1].strip()
    except Exception:
        pass
    return None


def upload_to_github_secrets(secrets_dict: dict):
    if not HAS_NACL:
        print("Notice: pynacl not available; skipping direct GitHub Secrets upload.")
        return

    gh_token = get_git_credential_token()
    if not gh_token:
        print("Notice: GitHub token not found in git credentials; please add secrets manually.")
        return

    headers = {
        "Authorization": f"token {gh_token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Python",
    }

    try:
        pk_res = requests.get(f"https://api.github.com/repos/{REPO_NAME}/actions/secrets/public-key", headers=headers)
        pk_res.raise_for_status()
        pk_data = pk_res.json()
        key_id = pk_data["key_id"]
        raw_pk = pk_data["key"]

        public_key_obj = nacl_public.PublicKey(raw_pk.encode("utf-8"), nacl_encoding.Base64Encoder())
        sealed_box = nacl_public.SealedBox(public_key_obj)

        for secret_name, secret_val in secrets_dict.items():
            enc_val = base64.b64encode(sealed_box.encrypt(secret_val.encode("utf-8"))).decode("utf-8")
            put_url = f"https://api.github.com/repos/{REPO_NAME}/actions/secrets/{secret_name}"
            put_res = requests.put(put_url, headers=headers, json={"encrypted_value": enc_val, "key_id": key_id})
            if put_res.status_code in [201, 204]:
                print(f"Uploaded secret '{secret_name}' to GitHub Secrets for {REPO_NAME}!")
            else:
                print(f"Warning: Failed to upload '{secret_name}': {put_res.text}")
    except Exception as e:
        print(f"Could not upload secrets to GitHub automatically: {e}")


def execute_oauth_flow(app_id: str, app_secret: str):
    scopes = "threads_basic,threads_content_publish,threads_read_replies,threads_manage_replies"
    auth_url = (
        f"https://www.threads.net/oauth/authorize?"
        f"client_id={app_id}&redirect_uri={REDIRECT_URI}&scope={scopes}&response_type=code"
    )

    print(f"\nStarting local OAuth callback listener on {REDIRECT_URI}...")
    server = HTTPServer(("localhost", 5000), OAuthCallbackHandler)

    print(f"Opening browser for Threads authorization:\n{auth_url}\n")
    webbrowser.open(auth_url)

    print("Waiting for browser approval in Threads...")
    server.handle_request()

    code = OAuthCallbackHandler.auth_code
    if not code:
        print("Failed to capture authorization code.")
        sys.exit(1)

    print("Authorization approved! Exchanging for short-lived token...")
    short_token = exchange_code_for_short_token(app_id, app_secret, code)

    print("Upgrading to 60-day long-lived access token...")
    long_token = exchange_for_long_lived_token(short_token, app_secret)

    print("Fetching Threads user profile...")
    profile = get_user_profile(long_token)
    user_id = str(profile.get("id"))
    username = profile.get("username", "unknown")

    display_and_save(long_token, user_id, username)


def execute_token_flow(token: str, app_secret: str = ""):
    if app_secret:
        try:
            print("Upgrading provided token to 60-day long-lived token...")
            token = exchange_for_long_lived_token(token, app_secret)
            print("Successfully upgraded to 60-day token!")
        except Exception as e:
            print(f"Note: Using provided token ({e})")

    print("Verifying token and fetching Threads user profile...")
    profile = get_user_profile(token)
    user_id = str(profile.get("id"))
    username = profile.get("username", "unknown")

    display_and_save(token, user_id, username)


def display_and_save(token: str, user_id: str, username: str):
    print("\n" + "=" * 60)
    print("THREADS AUTHENTICATION SUCCESSFUL!")
    print("=" * 60)
    print(f"Threads Username     : @{username}")
    print(f"THREADS_USER_ID      : {user_id}")
    print(f"THREADS_ACCESS_TOKEN : {token}")
    print("=" * 60)

    save_to_env(token, user_id)
    upload_to_github_secrets({
        "THREADS_ACCESS_TOKEN": token,
        "THREADS_USER_ID": user_id,
    })


def main():
    parser = argparse.ArgumentParser(description="Meta Threads Token & OAuth Helper")
    parser.add_argument("--app-id", help="Meta Threads App ID")
    parser.add_argument("--app-secret", help="Meta Threads App Secret")
    parser.add_argument("--token", help="Direct Threads access token")

    args = parser.parse_args()

    if args.app_id and args.app_secret:
        execute_oauth_flow(args.app_id, args.app_secret)
        return

    if args.token:
        execute_token_flow(args.token, args.app_secret or "")
        return

    # Interactive menu
    print("=" * 60)
    print("Meta Threads Token Utility")
    print("=" * 60)
    print("1. Automatic Browser OAuth 2.0 (Launches browser & retrieves 60-day token)")
    print("2. Quick Token Validator (Paste token -> Resolves User ID & uploads)")
    print("=" * 60)
    choice = input("Select an option (1 or 2): ").strip()

    if choice == "1":
        app_id = input("Enter Threads App ID: ").strip()
        app_secret = input("Enter Threads App Secret: ").strip()
        if app_id and app_secret:
            execute_oauth_flow(app_id, app_secret)
        else:
            print("App ID and App Secret required.")
    elif choice == "2":
        token = input("Paste your Threads Access Token: ").strip()
        app_secret = input("Enter App Secret (optional, press Enter to skip): ").strip()
        if token:
            execute_token_flow(token, app_secret)
        else:
            print("Token required.")
    else:
        print("Invalid selection.")


if __name__ == "__main__":
    main()
