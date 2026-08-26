"""
Twitter/X Upload Script (Official X v2 API)

Posts reels to @VelJapanese using the official X v2 endpoints:
- Media upload: v2 chunked upload on https://api.x.com (OAuth2 user token)
- Posting:      xdk (official X Python SDK) with the OAuth2 user token

OAuth 1.0a (TWITTER_*) is kept as an automatic fallback so posting never breaks.
"""

import os
import sys
import time
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

# Configure UTF-8 encoding for console output (Windows fix)
if sys.platform == 'win32':
    import codecs
    try:
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    except Exception:
        pass

# Load environment variables
load_dotenv()

# Current official X platform host for v2
X_HOST = "https://api.x.com"

X_OAUTH2_SCOPE = ["tweet.write", "media.write", "offline.access"]


def _ensure_oauth2_access_token():
    """Return a fresh OAuth2 access token for @VelJapanese via xdk refresh."""
    from xdk.oauth2_auth import OAuth2PKCEAuth

    cid = os.getenv("X_CLIENT_ID", "").strip()
    csec = os.getenv("X_CLIENT_SECRET", "").strip()
    at = os.getenv("X_OAUTH2_ACCESS_TOKEN", "").strip()
    rt = os.getenv("X_OAUTH2_REFRESH_TOKEN", "").strip()
    if not all([cid, csec, at, rt]):
        raise ValueError("[twitter] Missing X OAuth2 credentials in .env")

    token = {
        "access_token": at,
        "refresh_token": rt,
        "token_type": "bearer",
        "expires_at": time.time() + 3600,
    }
    auth = OAuth2PKCEAuth(
        client_id=cid,
        client_secret=csec,
        redirect_uri="https://localhost",
        token=token,
        scope=X_OAUTH2_SCOPE,
    )
    # Refresh to guarantee a valid, non-expired access token
    auth.refresh_token()
    new_token = auth.access_token
    if not new_token:
        raise ValueError("[twitter] OAuth2 refresh returned no access token")
    return new_token


def _chunked_upload_x(video_path, access_token):
    """Upload a video using the official v2 chunked media endpoint."""
    video_path_obj = Path(video_path)
    total_bytes = video_path_obj.stat().st_size
    headers = {"Authorization": f"Bearer {access_token}"}

    # 1. INIT
    print("[twitter] [info] INIT media upload...")
    r = requests.post(
        X_HOST + "/2/media/upload",
        params={
            "command": "INIT",
            "total_bytes": total_bytes,
            "media_type": "video/mp4",
            "media_category": "tweet_video",
        },
        headers=headers,
    )
    r.raise_for_status()
    media_id = r.json()["data"]["id"]
    print(f"[twitter] [info] Media ID: {media_id}")

    # 2. APPEND (chunked)
    print("[twitter] [info] APPEND media chunks...")
    segment = 0
    with open(video_path_obj, "rb") as f:
        while True:
            chunk = f.read(4 * 1024 * 1024)
            if not chunk:
                break
            ra = requests.post(
                X_HOST + "/2/media/upload",
                params={
                    "command": "APPEND",
                    "media_id": media_id,
                    "segment_index": segment,
                },
                data=chunk,
                headers={**headers, "Content-Type": "application/octet-stream"},
            )
            ra.raise_for_status()
            segment += 1
    print(f"[twitter] [info] Uploaded {segment} chunk(s)")

    # 3. FINALIZE
    print("[twitter] [info] FINALIZE media upload...")
    rf = requests.post(
        X_HOST + "/2/media/upload",
        params={"command": "FINALIZE", "media_id": media_id},
        headers=headers,
    )
    rf.raise_for_status()

    # 4. Wait for processing
    print("[twitter] [info] Waiting for video processing...")
    deadline = time.time() + 300
    while time.time() < deadline:
        rs = requests.get(
            X_HOST + "/2/media/upload",
            params={"command": "STATUS", "media_id": media_id},
            headers=headers,
        )
        info = rs.json().get("data", {}).get("processing_info")
        if not info:
            break
        state = info.get("state")
        if state == "succeeded":
            print("[twitter] [info] Video processing succeeded.")
            break
        if state == "failed":
            raise RuntimeError(f"[twitter] [error] Media processing failed: {info}")
        time.sleep(info.get("check_after_secs", 5))
    else:
        raise RuntimeError("[twitter] [error] Media processing timed out")

    return media_id


def _post_x(text, media_id, access_token):
    """Post the tweet using the official xdk SDK (OAuth2 user token)."""
    from xdk import Client
    from xdk.schemas import CreatePostsRequest, CreatePostsMedia

    cid = os.getenv("X_CLIENT_ID", "").strip()
    csec = os.getenv("X_CLIENT_SECRET", "").strip()
    rt = os.getenv("X_OAUTH2_REFRESH_TOKEN", "").strip()
    token = {
        "access_token": access_token,
        "refresh_token": rt,
        "token_type": "bearer",
        "expires_at": time.time() + 3600,
    }
    client = Client(
        client_id=cid,
        client_secret=csec,
        token=token,
        scope=X_OAUTH2_SCOPE,
    )
    resp = client.posts.create(
        body=CreatePostsRequest(
            text=text[:280],
            media=CreatePostsMedia(media_ids=[media_id]),
        )
    )
    return resp.data.id


def upload_to_twitter(video_path, caption):
    """Upload a reel to X using the official v2 API (OAuth2 + xdk)."""
    video_path_obj = Path(video_path)
    if not video_path_obj.exists():
        raise FileNotFoundError(f"[twitter] [error] Video file not found: {video_path}")

    # --- Official path: OAuth2 user token via xdk + v2 chunked media ---
    try:
        print("[twitter] [info] Using official X v2 OAuth2 path...")
        access_token = _ensure_oauth2_access_token()
        media_id = _chunked_upload_x(video_path, access_token)
        tweet_id = _post_x(caption, media_id, access_token)
        url = f"https://x.com/i/web/status/{tweet_id}"
        print(f"[twitter] [success] Posted to X (official): {url}")
        return {"id": tweet_id, "url": url, "platform": "twitter"}
    except Exception as e:
        print(f"[twitter] [warn] Official OAuth2 path failed: {e}")
        print("[twitter] [info] Falling back to OAuth 1.0a...")
        return _legacy_upload_to_twitter(video_path, caption)


# ---------------------------------------------------------------------------
# Legacy OAuth 1.0a path (fallback). Posts to the official api.x.com host.
# ---------------------------------------------------------------------------
import tweepy
from tweepy.auth import OAuth1UserHandler

tweepy.client.BaseClient.request = (
    lambda self, method, route, params=None, json=None, user_auth=False: _x_request(
        self, method, route, params, json, user_auth
    )
)


def _x_request(self, method, route, params=None, json=None, user_auth=False):
    host = X_HOST
    headers = {"User-Agent": self.user_agent}
    auth = None
    if user_auth:
        auth = OAuth1UserHandler(
            self.consumer_key, self.consumer_secret,
            self.access_token, self.access_token_secret
        )
        auth = auth.apply_auth()
    else:
        headers["Authorization"] = f"Bearer {self.bearer_token}"

    with self.session.request(
        method, host + route, params=params, json=json,
        headers=headers, auth=auth
    ) as response:
        if response.status_code == 401:
            raise tweepy.errors.Unauthorized(response)
        if response.status_code == 403:
            raise tweepy.errors.Forbidden(response)
        if response.status_code == 429:
            raise tweepy.errors.TooManyRequests(response)
        if response.status_code >= 500:
            raise tweepy.errors.TwitterServerError(response)
        if not 200 <= response.status_code < 300:
            raise tweepy.errors.HTTPException(response)
        return response


def _legacy_upload_to_twitter(video_path, caption):
    api_key = os.getenv('TWITTER_API_KEY', '').strip()
    api_secret = os.getenv('TWITTER_API_SECRET', '').strip()
    access_token = os.getenv('TWITTER_ACCESS_TOKEN', '').strip()
    access_secret = os.getenv('TWITTER_ACCESS_SECRET', '').strip()

    if not all([api_key, api_secret, access_token, access_secret]):
        raise ValueError("[twitter] Missing Twitter OAuth1 credentials in .env")

    print("[twitter] [info] Uploading to X (OAuth1 fallback)...")
    video_path_obj = Path(video_path)
    file_size_mb = video_path_obj.stat().st_size / (1024 * 1024)
    print(f"[twitter] Video size: {file_size_mb:.2f} MB")

    try:
        auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_secret)
        api_v1 = tweepy.API(auth)
        client = tweepy.Client(
            consumer_key=api_key, consumer_secret=api_secret,
            access_token=access_token, access_token_secret=access_secret
        )

        media = api_v1.media_upload(
            filename=str(video_path_obj),
            media_category='tweet_video',
            chunked=True
        )
        print(f"[twitter] [success] Video uploaded! Media ID: {media.media_id}")

        deadline = time.time() + 300
        while time.time() < deadline:
            status = api_v1.get_media_upload_status(media.media_id)
            pinfo = getattr(status, 'processing_info', None)
            if not pinfo:
                break
            state = pinfo.get('state')
            if state == 'succeeded':
                print("[twitter] Video processing succeeded.")
                break
            if state == 'failed':
                raise RuntimeError(f"[twitter] [error] Media processing failed: {pinfo}")
            time.sleep(pinfo.get('check_after_secs', 5))
        else:
            raise RuntimeError("[twitter] [error] Media processing timed out")

        response = client.create_tweet(
            text=caption[:280],
            media_ids=[media.media_id]
        )
        tweet_id = response.data['id']
        tweet_url = f"https://x.com/i/web/status/{tweet_id}"
        print(f"[twitter] [success] Posted to X: {tweet_url}")
        return {'id': tweet_id, 'url': tweet_url, 'platform': 'twitter'}

    except Exception as e:
        print(f"[twitter] [error] Unexpected error: {e}")
        raise


if __name__ == '__main__':
    video_file = Path('final_video.mp4')
    if video_file.exists():
        upload_to_twitter(video_file, "Test Upload #XAPI")
    else:
        print("[twitter] No test video found.")
