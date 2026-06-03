# -*- coding: utf-8 -*-
"""でんき見直し診断 — IG(Graph API) ＋ Threads(Threads API) 自動投稿。
依存なし(urllib)。トークンは env(CI) か .secrets/*.json(ローカル)。

IG   : https://graph.instagram.com/v23.0   (Instagram Business Login／FBページ不要)
Threads: https://graph.threads.net/v1.0

secrets:
  .secrets/ig.json       {"ig_user_id":"...","access_token":"IGAA..."}
  .secrets/threads.json  {"threads_user_id":"...","access_token":"THAA..."}
公開https URLのメディアが必須(サーバー側fetch)。長期トークンは60日、refreshで延長。
"""
import os, json, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
IG_GRAPH = "https://graph.instagram.com/v23.0"
TH_GRAPH = "https://graph.threads.net/v1.0"

# ---------- creds ----------
def _creds(kind):
    if kind == "ig":
        tok, uid = os.environ.get("IG_ACCESS_TOKEN"), os.environ.get("IG_USER_ID")
        if tok and uid: return uid, tok
        with open(os.path.join(HERE, ".secrets", "ig.json")) as f:
            c = json.load(f); return c["ig_user_id"], c["access_token"]
    else:
        tok, uid = os.environ.get("TH_ACCESS_TOKEN"), os.environ.get("TH_USER_ID")
        if tok and uid: return uid, tok
        with open(os.path.join(HERE, ".secrets", "threads.json")) as f:
            c = json.load(f); return c["threads_user_id"], c["access_token"]

# ---------- http ----------
def _post(base, path, params):
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(f"{base}/{path}", data=data, method="POST")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

def _get(base, path, params):
    url = f"{base}/{path}?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url) as r:
        return json.loads(r.read())

# ================= Instagram =================
def ig_carousel(image_urls, caption):
    ig, t = _creds("ig")
    kids = []
    for u in image_urls:
        r = _post(IG_GRAPH, f"{ig}/media",
                  {"image_url": u, "is_carousel_item": "true", "access_token": t})
        kids.append(r["id"])
    cont = _post(IG_GRAPH, f"{ig}/media",
                 {"media_type": "CAROUSEL", "children": ",".join(kids),
                  "caption": caption, "access_token": t})
    time.sleep(3)
    return _post(IG_GRAPH, f"{ig}/media_publish",
                 {"creation_id": cont["id"], "access_token": t})

def ig_image(image_url, caption):
    ig, t = _creds("ig")
    cont = _post(IG_GRAPH, f"{ig}/media",
                 {"image_url": image_url, "caption": caption, "access_token": t})
    time.sleep(3)
    return _post(IG_GRAPH, f"{ig}/media_publish",
                 {"creation_id": cont["id"], "access_token": t})

def ig_reel(video_url, caption, cover_url=None, timeout=300):
    ig, t = _creds("ig")
    p = {"media_type": "REELS", "video_url": video_url, "caption": caption,
         "share_to_feed": "true", "access_token": t}
    if cover_url: p["cover_url"] = cover_url
    cont = _post(IG_GRAPH, f"{ig}/media", p); cid = cont["id"]; w = 0
    while w < timeout:
        st = _get(IG_GRAPH, cid, {"fields": "status_code", "access_token": t})
        if st.get("status_code") == "FINISHED": break
        if st.get("status_code") == "ERROR": raise RuntimeError(f"reel error: {st}")
        time.sleep(5); w += 5
    return _post(IG_GRAPH, f"{ig}/media_publish", {"creation_id": cid, "access_token": t})

def ig_whoami():
    ig, t = _creds("ig")
    return _get(IG_GRAPH, ig, {"fields": "user_id,username,account_type,media_count,followers_count",
                               "access_token": t})

def ig_refresh():
    p = os.path.join(HERE, ".secrets", "ig.json")
    with open(p) as f: c = json.load(f)
    res = _get("https://graph.instagram.com", "refresh_access_token",
               {"grant_type": "ig_refresh_token", "access_token": c["access_token"]})
    c["access_token"] = res["access_token"]
    with open(p, "w") as f: json.dump(c, f, indent=2, ensure_ascii=False)
    return {"refreshed": True, "days": round(res.get("expires_in", 0)/86400, 1)}

# ================= Threads =================
def th_text(text):
    uid, t = _creds("threads")
    cont = _post(TH_GRAPH, f"{uid}/threads",
                 {"media_type": "TEXT", "text": text, "access_token": t})
    time.sleep(3)
    return _post(TH_GRAPH, f"{uid}/threads_publish",
                 {"creation_id": cont["id"], "access_token": t})

def th_image(image_url, text):
    uid, t = _creds("threads")
    cont = _post(TH_GRAPH, f"{uid}/threads",
                 {"media_type": "IMAGE", "image_url": image_url, "text": text, "access_token": t})
    time.sleep(3)
    return _post(TH_GRAPH, f"{uid}/threads_publish",
                 {"creation_id": cont["id"], "access_token": t})

def th_carousel(image_urls, text):
    uid, t = _creds("threads")
    kids = []
    for u in image_urls:
        r = _post(TH_GRAPH, f"{uid}/threads",
                  {"media_type": "IMAGE", "image_url": u, "is_carousel_item": "true", "access_token": t})
        kids.append(r["id"])
    cont = _post(TH_GRAPH, f"{uid}/threads",
                 {"media_type": "CAROUSEL", "children": ",".join(kids), "text": text, "access_token": t})
    time.sleep(3)
    return _post(TH_GRAPH, f"{uid}/threads_publish",
                 {"creation_id": cont["id"], "access_token": t})

def th_whoami():
    uid, t = _creds("threads")
    return _get(TH_GRAPH, uid, {"fields": "id,username,threads_profile_picture_url", "access_token": t})

def th_refresh():
    p = os.path.join(HERE, ".secrets", "threads.json")
    with open(p) as f: c = json.load(f)
    res = _get(TH_GRAPH, "refresh_access_token",
               {"grant_type": "th_refresh_token", "access_token": c["access_token"]})
    c["access_token"] = res["access_token"]
    with open(p, "w") as f: json.dump(c, f, indent=2, ensure_ascii=False)
    return {"refreshed": True, "days": round(res.get("expires_in", 0)/86400, 1)}

if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    fn = {"ig-whoami": ig_whoami, "ig-refresh": ig_refresh,
          "th-whoami": th_whoami, "th-refresh": th_refresh}.get(cmd)
    if fn: print(json.dumps(fn(), ensure_ascii=False, indent=2))
    else: print("usage: publisher.py [ig-whoami|ig-refresh|th-whoami|th-refresh]")
