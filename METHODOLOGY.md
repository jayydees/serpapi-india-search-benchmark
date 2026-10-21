# Methodology

This file states how every number is computed, what is measured, and what the numbers cannot show.

## Queries

`queries/queries.yaml` holds 50 queries: 17 news and general web, 17 local (six cities: Bangalore, Mumbai, Delhi NCR, Chennai, Hyderabad, Pune) and 16 shopping. Each has an id, an intent, a one-sentence rubric describing what a good answer contains, and a city for local queries. `--limit N` takes the first N of each intent in file order, so runs of different sizes are nested.

## What is called

| Intent | SerpApi | Serper | Exa | Apify | SearchApi |
|---|---|---|---|---|---|
| news | `google` plus `google_news` | `/search` plus `/news` | `/search`, category news | google-search-scraper | `google` |
| local | `google_maps` | `/places` | not offered | crawler-google-places | `google_maps` |
| shopping | `google_shopping` | `/shopping` | not offered | not offered | `google_shopping` |

All requests ask for India: `gl=in`, `hl=en` for Google-backed APIs, `userLocation=IN` for Exa, `countryCode=in` for Apify. Local queries pass the city as a location string, or as coordinates for APIs that take `ll`. A provider that does not offer an intent returns `intent_not_offered` and is scored n/a for that intent.

Exa is its own index and not a Google result page, so it is never described as Google results.

## Metrics

- **Success rate**: successful responses divided by queries the provider offers. `intent_not_offered` is excluded from the denominator.
- **Latency p50 and p95**: client-side wall time of successful, non-cached responses. Percentiles use the nearest-rank method: the value at rank `ceil(p/100 * n)` in the sorted list. When an intent needs two calls, latency is the sum. SerpApi responses that report a cache hit are excluded from latency. Apify latency includes actor start-up and is not comparable with a direct API.
- **Structured completeness**: local is the share of places with name, address and rating; shopping is the share of items with title, price and merchant; news is the share of items with date and source. The score is averaged over queries. It is n/a when the provider has no structured block for the intent, and 0 when it has one but returned nothing.
- **Domain overlap**: Jaccard index between the registrable domains of a provider's top 10 web results and SerpApi's top 10 for the same news query. Registrable domain is the last two host labels, or three for suffixes like `co.in`, without a public-suffix list. This is an agreement measure against one reference, not accuracy. If SerpApi differs from the truth, agreeing with it is not a virtue.
- **India relevance**: for local, the share of places whose address contains an alias of the query city; for shopping, the share of items priced in rupees (a price containing the rupee sign, "INR" or "Rs"); for news, the share of top-10 results whose host ends in `.in`, excluding Google hosts such as `google.co.in`, which appear only because of the request's `google_domain` setting. The `.in` rule is a crude proxy, since many relevant Indian pages sit on `.com`. An earlier version counted `.in` hosts for shopping too and credited SerpApi for its own `google.co.in` links, so it was replaced.
- **Cost per 1,000 queries**: the provider-reported cost when the response carries one (Exa), otherwise the price in `docs/PRICING.md` times the mean billable units per query. SerpApi cache hits are not billed and count as zero units. Free-tier runs cost nothing in practice, and the table shows list prices.
- **LLM judge (optional, `--judge`)**: a Gemini model, named by `JUDGE_MODEL`, scores each result list 0 to 3 against the query's rubric and gives a one-sentence reason. It is blind: no provider name appears in the prompt, and items are shuffled with a fixed seed so the order is reproducible. Temperature is 0. Limits: LLM judges are biased and noisy, shuffling removes rank information, and one judge model can favour a style of result. Use it as one signal. Agreement with a small human-labelled subset has not been measured, and that is a TODO for the author.

## What is measured and where

Everything is timed on the machine that runs the script, so network distance to each provider is part of the number. Run from the same place, at similar times, and repeat. Providers differ in how they cache. SerpApi serves identical queries from cache for an hour, and `no_cache` is left at `false` by default, so repeated runs can return cached copies that cost nothing and are excluded from latency.

## What cannot be concluded

- Which provider has the best results in general. The queries are 50 and the rubrics are short.
- Anything about providers that are not included.
- Accuracy from overlap, or quality from the judge alone.
- Stable rankings from one run. Search results and latency change over time.
- Anything from the synthetic test fixtures. They check that adapters parse the documented shapes and are not provider output.

## verify-live

Several provider details were not confirmed against a live response when this was written. Each lives in one clearly marked place in code. Do a small `--live --limit 2` run and compare the raw files in `runs/<dir>/raw/` before trusting these.

- **Serper**: endpoint names, body fields (including the `location` format), response keys (`organic`, `news`, `places`, `shopping`, `phoneNumber`) and credits per query come from third-party guides. See `SERPER_MAP` in `providers/serper.py`.
- **SerpApi**: the docs name no cache flag. A response is treated as cached when its `search_metadata.processed_at` is more than 30 seconds old, because a repeated query returns the first search's id and timestamps. The first 10-query run showed this: cached responses came back in 60-100 ms and were first counted as live, which made SerpApi's local latency look unrealistically low. The maps response is documented without a website field.
- **Apify**: the Authorization Bearer header is used for auth (a token query parameter is the other documented style), and the places actor's output keys come from its listing page.
- **SearchApi**: the India `location` format is an inference, so the adapter does not send `location`.
- **Exa**: how `costDollars` counts highlights.
- **Pricing**: each row in `docs/PRICING.md` carries VERIFIED or UNVERIFIED and a fetch date of 2026-10-21. Re-open each URL before publishing.

## Legal note

Several providers here return results collected from Google Search. Whether and how automated collection of search results is permitted is disputed, and in December 2025 Google filed a lawsuit against SerpApi (reported at https://www.gigazine.net/gsc_news/en/20251222-google-sues-serpapi). This repository takes no position. It calls provider APIs with your own keys and does not scrape Google. Read each provider's current terms before running or publishing results.

## Terms that shaped the design

Tavily and Brave are excluded because their terms restrict disclosing performance information or benchmarking, according to the research behind this repo. Raw responses stay in a gitignored directory because provider terms limit redistribution. Confirm both against the current terms.
