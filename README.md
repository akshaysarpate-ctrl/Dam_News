# Dam Failure News Watch

Collects news articles and YouTube videos about dam failures, breaches and inundation in
India, in 13 languages, and shows them as a list of links you can filter by 1 month,
3 months, 6 months and 1 year. Click a headline to open the original article or video.

## 1. Set up (once)

```
pip install -r requirements.txt
copy .env.example .env        (Windows)   |   cp .env.example .env   (Mac/Linux)
```

Open `.env` and add keys if you have them:

| Key | What it adds | Where to get it |
|---|---|---|
| `YOUTUBE_API_KEY` | YouTube videos | console.cloud.google.com, enable "YouTube Data API v3" (free quota) |
| `ANTHROPIC_API_KEY` | AI check that removes irrelevant items and fills in state, district and dam name | console.anthropic.com |

Without keys it still collects news from Google News and GDELT using keyword scoring.

## 2. Check the feeds work

```
python collect.py --test
```

This tries one search per language and prints how many items came back. If a language shows
0 items, open `keywords.json` and change its `"edition"` to `{"hl": "en-IN", "gl": "IN", "ceid": "IN:en"}`
(Google News does not have an edition for every language; the native-language search
words still work with the English edition).

## 3. First collection

```
python collect.py --days 365
```

This takes 20 to 40 minutes because it searches month by month, politely. Use `--days 30`
for a quicker start. Then start the website:

```
python app.py
```

Open http://127.0.0.1:5000

To preview the layout with fake data before collecting: `python seed_demo.py`
(remove it with `python seed_demo.py --clear`).

## 4. Search any date range from the website

Above the results there is a **Search the internet for a date range** box.

1. Pick a **From** and **To** date (up to one year at a time).
2. Optionally open "Languages to search" and untick languages you do not need (fewer is faster).
3. Press **Search the internet**. A progress bar appears. The search runs in the background,
   so you can leave the page open or come back later.
4. When it finishes the page reloads and shows every story for those dates. New stories
   are saved in your database, so next time they appear instantly.

**Show saved results only** skips the internet and just filters what is already stored.
The 1 month, 3 months, 6 months and 1 year tabs also show the dates they cover, so you can
press **Search the internet** on any of them to refresh that period.

Allow roughly 2 minutes per month of dates. If Google starts refusing requests, set
`SEARCH_WORKERS=1` in `.env`. GDELT only covers about the last 3 months and YouTube needs a key,
and the page tells you when either was skipped.

The same thing from the command line: `python collect.py --from 2026-06-01 --to 2026-08-15`

## 5. Daily updates

**Windows:** Task Scheduler, Create Basic Task, Daily, action "Start a program", program
`run_daily.bat` (in this folder). Output goes to `collect.log`.

**Mac/Linux:** `crontab -e` and add `0 7 * * * cd /path/to/dam_news && python collect.py >> collect.log 2>&1`

The daily run looks back 3 days, so a missed day is still covered.

## 6. Improving the results

- **Keywords:** edit `keywords.json`. Each language has `queries` (what is searched),
  `dam_terms` and `failure_terms` (used for scoring). Please have a native speaker
  review each language's list: I drafted them and regional usage varies. Add words
  such as local names for a dam, tank or bund as you find them.
- **What counts as a match:** items with a dam word and a failure word are "relevant".
  Items with only a dam word are "possible matches", hidden unless you tick
  "Include possible matches".
- **River embankments:** in many states, news says "dam" or "bund" for river flood
  embankments. The AI check drops those by default; set `INCLUDE_RIVER_EMBANKMENTS=1`
  in `.env` to keep them.
- **State filter:** English-language stories get a state from place names. Regional-language
  stories only get a state if the AI check is on.
- **CSV export:** the link at the bottom of the results downloads the current view for reports.

## Known limits

- Google News returns at most about 100 items per search; the collector splits long
  look-backs into monthly windows to work around this, but very old stories can be missed.
  Running it daily builds a complete archive from now on.
- Links from Google News go through a Google redirect and then open the publisher's page.
- Some publishers' pages may be paywalled.
- Similar stories from different outlets are all listed (only exact duplicates are removed).
- GDELT looks back about 3 months only.

## Files

| File | Purpose |
|---|---|
| `keywords.json` | Search words per language (edit this most) |
| `collect.py` | Collector: daily run, date ranges, used by the website too |
| `jobs.py` | Runs the website's internet search in the background |
| `collectors/` | Google News, YouTube, GDELT |
| `filters.py` | Keyword scoring, state tagging |
| `classify.py` | Optional AI check |
| `db.py` | SQLite database (`dam_news.db`) and duplicate removal |
| `app.py`, `templates/`, `static/` | The website |
