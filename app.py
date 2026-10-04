#!/usr/bin/env python3
"""
Kids Movies by Nandu10 — Stremio catalog addon (catalog + YouTube streams).

Young-kids-safe catalog (under-12): only Animation (16) / Family (10751)
titles. Horror/Thriller genre items, adult/violent keyword matches, and a
manually reviewed list of teen/adult animation are removed at data build
time (see kids_data.json meta). 12+ content is excluded — when in doubt,
it was left out.

Data: kids_data.json (filtered from mega_data.json — Msone + Movie Mirror
+ Team GOAT combined). Malayalam subtitles available via the separate
per-site subtitle addons.

YouTube sections (Mythology / Cartoons / Stories) stream directly via
YouTube watch URLs.

Row order:
  1. Mythology (Ramayana, Mahabharata, Krishna — YouTube)
  2. New Releases
  3. Ages 0-6: Movies
  4. Ages 0-6: Series
  5. Ages 6-12: Movies
  6. Ages 6-12: Series
  7. Cartoons (YouTube)
  8. YouTube Stories (moral, Panchatantra, Karuna)
  9. By genre
  10. By language

Routes:
  /kids/manifest.json
  /kids/catalog/<type>/<id>.json[?skip=N | /skip=N.json | /search=<q>.json]
  /kids/meta/<type>/<id>.json
  /kids/stream/<type>/<id>.json   (YouTube items)
"""
import json
import os
from collections import Counter

from flask import Flask, jsonify, request, Response

app = Flask(__name__)

POSTER = "https://image.tmdb.org/t/p/w500"
BG = "https://image.tmdb.org/t/p/w780"
YT_THUMB = "https://i.ytimg.com/vi/{}/hqdefault.jpg"
YT_WATCH = "https://www.youtube.com/watch?v={}"

TMDB_GENRES = {
    28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy", 80: "Crime",
    99: "Documentary", 18: "Drama", 10751: "Family", 14: "Fantasy",
    36: "History", 27: "Horror", 10402: "Music", 9648: "Mystery",
    10749: "Romance", 878: "Science Fiction", 10770: "TV Movie",
    53: "Thriller", 10752: "War", 37: "Western", 10759: "Action & Adventure",
    10762: "Kids", 10763: "News", 10764: "Reality", 10765: "Sci-Fi & Fantasy",
    10766: "Soap", 10767: "Talk", 10768: "War & Politics",
}

LANG_NAMES = {
    "english": "English", "korean": "Korean", "hindi": "Hindi",
    "japanese": "Japanese", "french": "French", "spanish": "Spanish",
    "mandarin": "Mandarin", "telugu": "Telugu", "tamil": "Tamil",
    "malayalam": "Malayalam", "cantonese": "Cantonese",
    "indonesian": "Indonesian", "thai": "Thai", "german": "German",
    "italian": "Italian", "russian": "Russian", "portuguese": "Portuguese",
    "dutch": "Dutch", "swedish": "Swedish", "danish": "Danish",
    "norwegian": "Norwegian", "finnish": "Finnish", "polish": "Polish",
    "turkish": "Turkish", "arabic": "Arabic", "persian": "Persian",
    "urdu": "Urdu", "bengali": "Bengali", "punjabi": "Punjabi",
    "marathi": "Marathi", "kannada": "Kannada", "gujarati": "Gujarati",
    "vietnamese": "Vietnamese", "tagalog": "Tagalog", "filipino": "Filipino",
    "malay": "Malay", "hebrew": "Hebrew", "greek": "Greek",
    "ukrainian": "Ukrainian", "chinese": "Chinese", "czech": "Czech",
    "serbian": "Serbian", "romanian": "Romanian", "hungarian": "Hungarian",
    "dzongkha": "Dzongkha",
}

SITE_LABEL = {"msone": "Msone", "moviemirror": "Movie Mirror",
              "teamgoat": "Team GOAT"}

# ---------------- YouTube sections ----------------
# Curated Malayalam kids videos (verified via YouTube search).
YOUTUBE_MYTHOLOGY = [
    {"yt": "tFtFc8hcgtM", "name": "രാമായണം | അണ്ണാറക്കണ്ണനും തന്നാലായത്",
     "en": "Ramayana Story", "channel": "STORY TIME", "cat": "Ramayana"},
    {"yt": "5rQyUsvrD84", "name": "ശ്രീരാമന്റെ ജനനം | Birth of Lord Rama",
     "en": "Birth of Lord Rama", "channel": "HopBudz", "cat": "Ramayana"},
    {"yt": "agLo-B_jO8k", "name": "ബാല രാമായണം",
     "en": "Bala Ramayanam for Kids", "channel": "JoMedia - Kids Tunes Tv",
     "cat": "Ramayana"},
    {"yt": "1vKoqsLyTSc", "name": "അർജ്ജുനന്റെ ലക്ഷ്യബോധം | മഹാഭാരത കഥ",
     "en": "Arjuna's Focus - Mahabharata", "channel": "Kathayulla Kathakal",
     "cat": "Mahabharata"},
    {"yt": "bPL-DHiqwjc", "name": "കാരുണ്യം എന്ന ധർമ്മം | മഹാഭാരത കഥകൾ",
     "en": "Karunyam - Mahabharata Moral Story",
     "channel": "Kathayulla Kathakal", "cat": "Mahabharata"},
    {"yt": "Gx49h1WxsHA", "name": "കൃഷ്ണന്റെ കഥ",
     "en": "Krishna Story for Children", "channel": "mcvideosanimation",
     "cat": "Krishna"},
    {"yt": "N_hhk9kbHv4", "name": "കൃഷ്ണ കഥകൾ",
     "en": "Krishna Stories", "channel": "Pebbles Malayalam",
     "cat": "Krishna"},
    {"yt": "1PmsCRcFm9c", "name": "ശ്രീകൃഷ്ണന്റെ ജനനം",
     "en": "Birth of Krishna - Janmashtami Story", "channel": "Mythoverse",
     "cat": "Krishna"},
]

YOUTUBE_STORIES = [
    {"yt": "V8Y1v8B_xcI", "name": "ഗുണപാഠ കഥകൾ",
     "en": "Moral Stories for Kids", "channel": "Sargam Kids",
     "cat": "Moral Stories"},
    {"yt": "_70T2xLP7dk", "name": "കുട്ടി കഥകൾ",
     "en": "Kids Moral Stories", "channel": "Sargam Kids",
     "cat": "Moral Stories"},
    {"yt": "iyRgMGzWBAA", "name": "മരത്തിലെ പഴം",
     "en": "Marathile Pazham - Moral Story", "channel": "Sargam Kids Malayalam",
     "cat": "Moral Stories"},
    {"yt": "ds2QJ61vM8A", "name": "ഗുണപാഠ കഥകൾ",
     "en": "Gunapada Kathakal", "channel": "Sargam Kids Malayalam",
     "cat": "Moral Stories"},
    {"yt": "zW1o_Ay9KAQ", "name": "കുട്ടികളുടെ കഥകൾ",
     "en": "Kids Moral Stories", "channel": "Sargam Kids Malayalam",
     "cat": "Moral Stories"},
    {"yt": "N_xMj9F0wWk", "name": "പഞ്ചതന്ത്രം കഥകൾ",
     "en": "Panchatantra Stories", "channel": "Koo Koo TV Malayalam",
     "cat": "Panchatantra"},
    {"yt": "HAcTTQRRdoQ", "name": "പഞ്ചതന്ത്രം കഥകൾ",
     "en": "Panchatantra Moral Stories", "channel": "Koo Koo TV Malayalam",
     "cat": "Panchatantra"},
    {"yt": "kRMGYUfx5lc", "name": "കുട്ടനും മുട്ടനും | പഞ്ചതന്ത്രം",
     "en": "Panchatantra Story", "channel": "Manjadi", "cat": "Panchatantra"},
    {"yt": "UdNYoIzUkl4", "name": "തെനാലി രാമൻ കഥകൾ",
     "en": "Tenali Raman Stories", "channel": "MagicBox Malayalam",
     "cat": "Moral Stories"},
    {"yt": "74F7bgdOHog", "name": "താറാവും ലോഭി ചെന്നായും",
     "en": "Duck and the Greedy Wolf", "channel": "KidsOne Malayalam",
     "cat": "Moral Stories"},
]

YOUTUBE_CARTOONS = [
    {"yt": "Bv5bi836G-4", "name": "തൊപ്പിക്കുട",
     "en": "Thoppikkuda - Kids Cartoon", "channel": "Sargam Kids",
     "cat": "Cartoon"},
    {"yt": "Yx_XxXiRHQc", "name": "അപ്പുവും മാളുവും",
     "en": "Appuvum Maluvum - Cartoon Story", "channel": "Sargam Kids",
     "cat": "Cartoon"},
    {"yt": "3wR5sr7YTYI", "name": "വീട്ടിൽ അതിഥി",
     "en": "Stories for Children", "channel": "Sony YAY! Malayalam",
     "cat": "Cartoon"},
    {"yt": "d0kndkIB69s", "name": "കൂട്ടുകാരുടെ കഥകൾ",
     "en": "Friendship Stories", "channel": "Sargam Kids", "cat": "Cartoon"},
]


def _yt_meta(v, row_name):
    name = v["name"] + (f" | {v['en']}" if v.get("en") else "")
    return {
        "id": f"yt:{v['yt']}",
        "type": "movie",
        "name": name,
        "poster": YT_THUMB.format(v["yt"]),
        "background": YT_THUMB.format(v["yt"]),
        "description": (f"{v['cat']} \u2014 {v['channel']}\n"
                        f"Malayalam kids video from YouTube.").strip(),
        "genres": [v["cat"], row_name],
        "releaseInfo": "",
    }


# ---------------- data ----------------
_kids_data = None
_kids_defs = None
_kids_metas = {}
_kids_by_id = None


def kids_load():
    global _kids_data
    if _kids_data is None:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "kids_data.json")
        with open(p, encoding="utf-8") as f:
            _kids_data = json.load(f)
    return _kids_data


def all_items():
    return kids_load().get("items", [])


def lang_name(slug):
    return LANG_NAMES.get(slug, slug.replace("-", " ").replace("_", " ").title())


def kids_catalog_defs():
    """Ordered home-page rows. Cached."""
    global _kids_defs
    if _kids_defs is not None:
        return _kids_defs
    items = all_items()
    movies = [it for it in items if it["media"] == "movie"]
    series = [it for it in items if it["media"] == "tv"]

    cats = [
        # 1. Mythology FIRST (user priority)
        {"id": "kids_mythology", "type": "movie",
         "name": "\U0001F549\uFE0F Mythology",
         "kind": "yt_mythology"},
        # 2. New Releases
        {"id": "kids_new", "type": "movie", "name": "New Releases",
         "kind": "latest_all"},
        # 3-6. Age groups
        {"id": "kids_age06_movies", "type": "movie",
         "name": "Ages 0-6: Movies", "kind": "age",
         "age": "0-6", "media": "movie"},
        {"id": "kids_age06_series", "type": "series",
         "name": "Ages 0-6: Series", "kind": "age",
         "age": "0-6", "media": "tv"},
        {"id": "kids_age612_movies", "type": "movie",
         "name": "Ages 6-12: Movies", "kind": "age",
         "age": "6-12", "media": "movie"},
        {"id": "kids_age612_series", "type": "series",
         "name": "Ages 6-12: Series", "kind": "age",
         "age": "6-12", "media": "tv"},
        # 7. Cartoons (YouTube)
        {"id": "kids_cartoons", "type": "movie",
         "name": "\U0001F4FA Cartoons", "kind": "yt_cartoons"},
        # 8. YouTube Stories
        {"id": "kids_stories", "type": "movie",
         "name": "\U0001F4D6 YouTube Stories", "kind": "yt_stories"},
    ]
    # 9. Genre rows grouped: for each genre, Kids Movies then Kids Series
    mg = Counter(g for it in movies for g in (it.get("genre_ids") or [])
                 if g != 99 and g in TMDB_GENRES)
    sg = Counter(g for it in series for g in (it.get("genre_ids") or [])
                 if g != 99 and g in TMDB_GENRES)
    all_genres = Counter()
    all_genres.update(mg)
    all_genres.update(sg)
    for gid, _ in all_genres.most_common():
        gname = TMDB_GENRES[gid]
        if mg.get(gid):
            cats.append({"id": f"kids_mgenre_{gid}", "type": "movie",
                         "name": f"{gname}: Kids Movies",
                         "kind": "genre", "genre_id": gid, "media": "movie"})
        if sg.get(gid):
            cats.append({"id": f"kids_sgenre_{gid}", "type": "series",
                         "name": f"{gname}: Kids Series",
                         "kind": "genre", "genre_id": gid, "media": "tv"})
    # 10. Language rows grouped (10+ titles only)
    ml = Counter(it["lang"] for it in movies if it.get("lang"))
    sl = Counter(it["lang"] for it in series if it.get("lang"))
    all_langs = Counter()
    all_langs.update(ml)
    all_langs.update(sl)
    for lang, cnt in all_langs.most_common():
        if cnt < 10:
            continue
        lname = lang_name(lang)
        if ml.get(lang, 0) >= 10:
            cats.append({"id": f"kids_mlang_{lang}", "type": "movie",
                         "name": f"{lname}: Kids Movies",
                         "kind": "lang", "lang": lang, "media": "movie"})
        if sl.get(lang, 0) >= 10:
            cats.append({"id": f"kids_slang_{lang}", "type": "series",
                         "name": f"{lname}: Kids Series",
                         "kind": "lang", "lang": lang, "media": "tv"})
    _kids_defs = cats
    return cats


def _items_for_cat(cat):
    items = all_items()
    kind = cat["kind"]
    if kind == "latest_all":
        return items  # pre-sorted newest-first
    if kind == "age":
        return [it for it in items
                if it["media"] == cat["media"]
                and it.get("age_group") == cat["age"]]
    if kind == "genre":
        return [it for it in items
                if it["media"] == cat["media"]
                and cat["genre_id"] in (it.get("genre_ids") or [])]
    if kind == "lang":
        return [it for it in items
                if it["media"] == cat["media"] and it.get("lang") == cat["lang"]]
    return []


def _yt_metas_for(kind):
    if kind == "yt_mythology":
        return [_yt_meta(v, "Mythology") for v in YOUTUBE_MYTHOLOGY]
    if kind == "yt_cartoons":
        return [_yt_meta(v, "Cartoons") for v in YOUTUBE_CARTOONS]
    if kind == "yt_stories":
        return [_yt_meta(v, "Stories") for v in YOUTUBE_STORIES]
    return []


def _to_meta(it):
    disp = it["name"] + (f" / {it['name_ml']}" if it.get("name_ml") else "")
    labels = [SITE_LABEL[s] for s in it.get("sources", []) if s in SITE_LABEL]
    urls = "\n".join(it.get("post_urls", {}).values())
    desc = (it.get("overview") or "")
    desc += ("\n\n\U0001F4DD Malayalam subtitles: " + ", ".join(labels)
             if labels else "")
    if urls:
        desc += "\n" + urls
    return {
        "id": it["card_id"],
        "type": "movie" if it["media"] == "movie" else "series",
        "name": disp,
        "poster": f"{POSTER}{it['poster_path']}" if it.get("poster_path") else None,
        "background": f"{BG}{it['backdrop_path']}" if it.get("backdrop_path") else None,
        "description": desc.strip(),
        "releaseInfo": str(it.get("year") or ""),
        "genres": [TMDB_GENRES[g] for g in (it.get("genre_ids") or [])
                   if g in TMDB_GENRES],
    }


def kids_metas(cid):
    if cid in _kids_metas:
        return _kids_metas[cid]
    cat = next(c for c in kids_catalog_defs() if c["id"] == cid)
    kind = cat["kind"]
    if kind.startswith("yt_"):
        metas = _yt_metas_for(kind)
    else:
        metas = [_to_meta(it) for it in _items_for_cat(cat)]
        metas = [m for m in metas if m.get("poster")]
    _kids_metas[cid] = metas
    return metas


def kids_by_id():
    global _kids_by_id
    if _kids_by_id is None:
        idx = {}
        for it in all_items():
            idx[it["card_id"]] = it
            if it.get("imdb_id"):
                idx[it["imdb_id"]] = it
            if it.get("tmdb_id"):
                idx[f"tmdb:{it['tmdb_id']}"] = it
        for v in YOUTUBE_MYTHOLOGY + YOUTUBE_STORIES + YOUTUBE_CARTOONS:
            idx[f"yt:{v['yt']}"] = {"_youtube": v}
        _kids_by_id = idx
    return _kids_by_id


def _top_lines(items, n=8):
    return "\n".join(
        f"\u2022 {it['name']}"
        + (f" / {it['name_ml']}" if it.get("name_ml") else "")
        + (f" ({it['year']})" if it.get("year") else "")
        for it in items[:n])


# ---------------- routes ----------------
@app.route("/kids/manifest.json")
def kids_manifest():
    return jsonify({
        "id": "com.kidscatalog.malayalam",
        "version": "1.0.0",
        "name": "Kids Movies by Nandu10",
        "description": "Young-kids-safe movies, series, cartoons, mythology "
                       "and stories with Malayalam subtitles \u2014 from "
                       "Msone + Movie Mirror + Team GOAT and YouTube "
                       "(TMDB metadata)",
        "logo": f"{request.url_root.rstrip('/')}/static/logo.png",
        "types": ["movie", "series"],
        "idPrefixes": ["tt", "tmdb:", "kids:", "yt:"],
        "resources": ["catalog", "meta", "stream"],
        "catalogs": [
            {"type": c["type"], "id": c["id"], "name": c["name"],
             "extra": [{"name": "skip", "isRequired": False},
                       {"name": "search", "isRequired": False}]}
            for c in kids_catalog_defs()
        ],
    })


@app.route("/kids/catalog/<ctype>/<cid>.json")
@app.route("/kids/catalog/<ctype>/<cid>/skip=<int:skip>.json")
@app.route("/kids/catalog/<ctype>/<cid>/search=<path:search>.json")
def kids_catalog(ctype, cid, skip=0, search=None):
    # Handle search as query param too
    if search is None:
        search = request.args.get("search")
    cat = next((c for c in kids_catalog_defs() if c["id"] == cid), None)
    if not cat:
        return jsonify({"metas": []}), 404
    try:
        metas = kids_metas(cid)
        # Filter by search query
        if search:
            q = search.lower()
            metas = [m for m in metas
                     if q in (m.get("name") or "").lower()]
    except Exception as e:
        return jsonify({"metas": [], "error": str(e)}), 502
    if "skip" not in request.view_args:
        try:
            skip = int(request.args.get("skip", "0"))
        except ValueError:
            skip = 0
    return jsonify({"metas": metas[skip:skip + 20]})


@app.route("/kids/meta/<mtype>/<mid>.json")
def kids_meta(mtype, mid):
    # 1. YouTube ids
    if mid.startswith("yt:"):
        entry = kids_by_id().get(mid)
        if not entry:
            return jsonify({"meta": {}})
        v = entry["_youtube"]
        row = next((r for r in ("Mythology", "Stories", "Cartoons")
                    if any(x["yt"] == v["yt"] for x in
                            (YOUTUBE_MYTHOLOGY if r == "Mythology"
                             else YOUTUBE_STORIES if r == "Stories"
                             else YOUTUBE_CARTOONS))), "Video")
        meta = _yt_meta(v, row)
        return jsonify({"meta": {k: v2 for k, v2 in meta.items() if v2}})
    # 2. catalog ids -> catalog-level meta
    cat = next((c for c in kids_catalog_defs() if c["id"] == mid), None)
    if cat:
        kind = cat["kind"]
        if kind.startswith("yt_"):
            items = _yt_metas_for(kind)
            first = items[0] if items else None
            meta = {
                "id": cat["id"],
                "type": cat["type"],
                "name": cat["name"],
                "poster": first["poster"] if first else None,
                "description": (f"{len(items)} videos in {cat['name']}.").strip(),
            }
            return jsonify({"meta": {k: v for k, v in meta.items() if v}})
        items = _items_for_cat(cat)
        first = items[0] if items else None
        meta = {
            "id": cat["id"],
            "type": cat["type"],
            "name": cat["name"],
            "poster": (f"{POSTER}{first['poster_path']}"
                       if first and first.get("poster_path") else None),
            "background": (f"{BG}{first['backdrop_path']}"
                           if first and first.get("backdrop_path") else None),
            "description": (f"{len(items)} kids titles in {cat['name']}."
                            f"\n\nTop titles:\n{_top_lines(items)}").strip(),
        }
        return jsonify({"meta": {k: v for k, v in meta.items() if v}})
    # 3. title ids: tt..., tmdb:..., kids card ids
    it = kids_by_id().get(mid)
    if not it or "_youtube" in it:
        return jsonify({"meta": {}})
    meta = _to_meta(it)
    meta = {k: v for k, v in meta.items() if v}
    return jsonify({"meta": meta})


@app.route("/kids/stream/<stype>/<sid>.json")
def kids_stream(stype, sid):
    # YouTube items -> YouTube watch URL (plays via YouTube addon / external)
    if sid.startswith("yt:"):
        vid = sid[3:]
        entry = kids_by_id().get(sid)
        title = "YouTube"
        if entry and "_youtube" in entry:
            v = entry["_youtube"]
            title = f"{v['name']} | {v['channel']}"
        return jsonify({"streams": [
            {"url": YT_WATCH.format(vid),
             "title": f"\U0001F3AC {title}"},
        ]})
    return jsonify({"streams": []})


@app.route("/")
def index():
    base = request.host_url.rstrip("/")
    return Response(
        f"""<h2>Kids Movies by Nandu10 \U0001F9D2</h2>
        <p>Young-kids-safe catalog with Malayalam subtitles.</p>
        <p>Install in Stremio / Nuvio:<br>
        <code>{base}/kids/manifest.json</code></p>""",
        mimetype="text/html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
