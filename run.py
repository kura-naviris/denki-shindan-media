# -*- coding: utf-8 -*-
"""次の未投稿アイテムを1件投稿する。GitHub Actionsから定期実行。
  python3 run.py ig        # ig_queue.json の先頭未投稿をIGへ
  python3 run.py threads   # threads_queue.json の先頭未投稿をThreadsへ
DRY_RUN=1 で公開せずコンテナ生成のみ（IGの安全テスト）。

このスクリプトは「投稿リポ(denki-shindan-media)」の中で動く前提。
メディアは既にリポ内 media/<subdir>/ にある → raw URLを組み立てて投稿。
"""
import os, sys, json, datetime, subprocess
import publisher

HERE = os.path.dirname(os.path.abspath(__file__))
OWNER = os.environ.get("MEDIA_OWNER", "kura-naviris")
REPO  = os.environ.get("MEDIA_REPO", "denki-shindan-media")
RAW   = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main"
DRY   = os.environ.get("DRY_RUN") == "1"

def log(m):
    line = f"{datetime.datetime.now().isoformat(timespec='seconds')} {m}"
    print(line)
    with open(os.path.join(HERE, "post.log"), "a") as f: f.write(line + "\n")

def urls_for(files):
    return [f"{RAW}/{p}" for p in files]

def commit_queue(qfile):
    subprocess.run(["git", "-C", HERE, "add", qfile], check=True, capture_output=True, text=True)
    try:
        subprocess.run(["git", "-C", HERE, "commit", "-m", f"mark posted in {qfile}"],
                       check=True, capture_output=True, text=True)
        subprocess.run(["git", "-C", HERE, "push", "origin", "main"],
                       check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        if "nothing to commit" not in (e.stdout + e.stderr): raise

def run(platform):
    qname = "ig_queue.json" if platform == "ig" else "threads_queue.json"
    qpath = os.path.join(HERE, qname)
    with open(qpath) as f: q = json.load(f)
    pending = [p for p in q["posts"] if not p.get("posted")]
    if not pending:
        log(f"[{platform}] no pending posts"); return 0
    post = pending[0]; pid = post["id"]; ptype = post.get("type", "carousel")
    log(f"[{platform}] START {pid} type={ptype} dry={DRY}")

    if platform == "ig":
        urls = urls_for(post["files"])
        cap = post.get("caption", "")
        if DRY:
            ig, t = publisher._creds("ig")
            r = publisher._post(publisher.IG_GRAPH, f"{ig}/media",
                                {"image_url": urls[0], "caption": cap, "access_token": t})
            log(f"[ig] DRY container {r}"); return 0
        if ptype == "carousel":  res = publisher.ig_carousel(urls, cap)
        elif ptype == "image":   res = publisher.ig_image(urls[0], cap)
        elif ptype == "reel":    res = publisher.ig_reel(urls[0], cap, post.get("cover_url"))
        else: log(f"[ig] bad type {ptype}"); return 1
    else:
        txt = post.get("text", "")
        if ptype == "text":      res = publisher.th_text(txt)
        elif ptype == "image":   res = publisher.th_image(urls_for(post["files"])[0], txt)
        elif ptype == "carousel":res = publisher.th_carousel(urls_for(post["files"]), txt)
        else: log(f"[threads] bad type {ptype}"); return 1

    post["posted"] = True
    post["published_id"] = res.get("id")
    post["published_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    with open(qpath, "w") as f: json.dump(q, f, indent=2, ensure_ascii=False)
    commit_queue(qname)
    left = sum(1 for p in q["posts"] if not p.get("posted"))
    log(f"[{platform}] DONE {pid} id={res.get('id')} | {left} left")
    return 0

if __name__ == "__main__":
    plat = sys.argv[1] if len(sys.argv) > 1 else ""
    if plat not in ("ig", "threads"):
        print("usage: run.py [ig|threads]"); sys.exit(1)
    try: sys.exit(run(plat))
    except Exception as e:
        log(f"[{plat}] FATAL {type(e).__name__}: {e}"); sys.exit(1)
