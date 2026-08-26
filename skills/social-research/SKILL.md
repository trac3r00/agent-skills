---
name: social-research
description: Finds and extracts content from social platforms — X/Twitter posts and profiles via the public syndication API (no auth), Threads posts via public web endpoints where available, and Reddit/HN/Bluesky via official public APIs. Uses the ultimate-browsing Tier 1.5 platform-native readers with honest documentation of what each platform exposes without a login. Use for researching people, topics, or conversations on social platforms without a browser.
when_to_use: "Find what X said about Y", "search Twitter for Z", "pull this person's recent posts", "what's on HN about this". NOT a posting tool (read-only) and NOT a login bypass — content behind auth walls is documented as inaccessible, never scraped around.
version: 1.0.0
license: MIT
metadata:
  agentskills:
    tags: [social, twitter, x, threads, reddit, research]
---

# Social Research

Read-only social content discovery through the platforms' own public
endpoints — no headless browser, no login, no scraping around walls.

## Platform capabilities (honest matrix)

| Platform | No-auth access | How |
|---|---|---|
| X/Twitter | Profiles, recent posts | Public syndication API (`syndication.twitter.com`) — rate-limited (429 when hot; retry with backoff) |
| Threads | Public profiles/posts only | `threads.net/@user` public web pages; no public search API — search is not possible without auth, documented as such |
| Reddit | Full search, posts, comments | Official `.json` endpoints (`reddit.com/r/X/search.json`) |
| Hacker News | Full search, items | Firebase API (`hacker-news.firebaseio.com`) + Algolia search (`hn.algolia.com`) |
| Bluesky | Profiles, posts, search | Public AT Protocol API (`public.api.bsky.app`) |

## X/Twitter via syndication

```bash
# User timeline (no auth):
curl -s "https://syndication.twitter.com/srv/timeline-profile/screen-name/USERNAME?dnt=true"
# Returns HTML with embedded tweets; parse text from it.
# 429 = rate limited: back off, don't hammer.
```

## Reddit search

```bash
curl -s "https://www.reddit.com/search.json?q=QUERY&limit=10" -H "User-Agent: research"
curl -s "https://www.reddit.com/r/SUBREDDIT/hot.json?limit=10" -H "User-Agent: research"
```

## Hacker News search

```bash
curl -s "https://hn.algolia.com/api/v1/search?query=QUERY&tags=story"
curl -s "https://hacker-news.firebaseio.com/v0/topstories.json"
```

## Bluesky

```bash
curl -s "https://public.api.bsky.app/xrpc/app.bsky.actor.searchActors?q=QUERY"
curl -s "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts?q=QUERY"
```

## Threads — the honest limitation

Threads has no public search API and no syndication endpoint. Public profile
pages (`threads.net/@username`) render post content in HTML for logged-out
viewers in some regions, but availability varies. Searching Threads content
without a Meta account is not possible — this skill documents the limitation
rather than pretending a workaround exists. For Threads-specific needs, the
user's logged-in browser session (via a browser automation skill) is the
only legitimate path.

## Pairs with

`ultimate-browsing` (escalate to Tier 2 stealth browser when public
endpoints are insufficient and you have legitimate access).
