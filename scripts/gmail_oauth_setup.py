"""
One-time local authorization for Gmail API access.

Run this on your OWN machine (not in a cloud session) — it opens a real
browser window for you to approve access, which a headless environment
can't do. Produces a refresh token you paste into the cloud environment's
variables once; you don't run this again unless the token gets revoked.

Prerequisites (Google Cloud Console, console.cloud.google.com):
1. Create a project (or use an existing one).
2. APIs & Services > Library > enable the "Gmail API".
3. APIs & Services > OAuth consent screen > configure it (External user
   type is fine for a personal Gmail account), add the
   "https://www.googleapis.com/auth/gmail.send" scope, and add your own
   Gmail address as a test user.
4. APIs & Services > Credentials > Create Credentials > OAuth client ID >
   Application type "Desktop app". Note the Client ID and Client Secret.

Usage:
    python scripts/gmail_oauth_setup.py --client-id YOUR_ID --client-secret YOUR_SECRET

Prints the refresh token to save as GMAIL_REFRESH_TOKEN, alongside
GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET, in the cloud environment's
variables (see docs/setup.md).
"""
import argparse
import http.server
import json
import threading
import urllib.parse
import urllib.request
import webbrowser

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/gmail.send"
PORT = 8765
REDIRECT_URI = f"http://localhost:{PORT}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--client-secret", required=True)
    args = parser.parse_args()

    auth_code = {}

    class CallbackHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            if "code" in params:
                auth_code["value"] = params["code"][0]
                self.wfile.write(b"<html><body>Authorized. You can close this tab and return to the terminal.</body></html>")
            else:
                self.wfile.write(b"<html><body>No authorization code received.</body></html>")

        def log_message(self, format, *args):
            pass  # keep the terminal quiet

    server = http.server.HTTPServer(("localhost", PORT), CallbackHandler)
    server_thread = threading.Thread(target=server.handle_request, daemon=True)
    server_thread.start()

    auth_params = urllib.parse.urlencode({
        "client_id": args.client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",  # forces a refresh token even on re-authorization
    })
    auth_url = f"{AUTH_URL}?{auth_params}"

    print(f"Opening your browser to authorize Gmail access:\n{auth_url}\n")
    print("(If a browser doesn't open automatically, paste that URL into one.)")
    webbrowser.open(auth_url)

    server_thread.join(timeout=120)
    if "value" not in auth_code:
        print("Timed out waiting for authorization. Try again.")
        return

    token_request = urllib.request.Request(
        TOKEN_URL,
        data=urllib.parse.urlencode({
            "client_id": args.client_id,
            "client_secret": args.client_secret,
            "code": auth_code["value"],
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
        }).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(token_request, timeout=30) as response:
        tokens = json.loads(response.read())

    if "refresh_token" not in tokens:
        print("No refresh token in the response — this can happen on a repeat "
              "authorization. Revoke the app's access at "
              "https://myaccount.google.com/permissions and run this again.")
        print(json.dumps(tokens, indent=2))
        return

    print("\nSuccess. Save these as environment variables in the cloud environment:\n")
    print(f"GMAIL_CLIENT_ID={args.client_id}")
    print(f"GMAIL_CLIENT_SECRET={args.client_secret}")
    print(f"GMAIL_REFRESH_TOKEN={tokens['refresh_token']}")


if __name__ == "__main__":
    main()
