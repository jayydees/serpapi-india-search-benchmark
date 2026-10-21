# Pricing inputs

Every price below was read on 2026-10-21 from the source URL given. Status is VERIFIED when a
first-party page was read, and UNVERIFIED when the fact came from a third party, a search
snippet or an inference. **Re-verify each row by eye before publishing any cost number.**

The runner reads the first table in this file. Rows start with a backticked key that matches a
provider's pricing key. Cost per 1,000 queries is `USD per 1,000 units` multiplied by the mean
units billed per query (calls for most providers, result pages or places for Apify). Exa
returns its own `costDollars` in each response and the runner prefers that when present.

| Key | Provider and plan | USD per 1,000 units | Unit | Status | Source | Fetched |
|---|---|---|---|---|---|---|
| `serpapi` | SerpApi Starter, $25 for 1,000 searches a month (calculated, the page lists no per-1,000 rate) | 25.00 | search | VERIFIED | https://serpapi.com/pricing | 2026-10-21 |
| `serper` | Serper Starter pack, $50 for 50k credits (credits per query UNVERIFIED, 1 assumed) | 1.00 | credit | UNVERIFIED | https://serper.dev | 2026-10-21 |
| `exa` | Exa `auto` search, up to 10 results, contents billed separately | 7.00 | request | VERIFIED | https://exa.ai/pricing | 2026-10-21 |
| `apify` | Apify google-search-scraper, "from" price per results page | 1.80 | result page | VERIFIED | https://apify.com/apify/google-search-scraper | 2026-10-21 |
| `apify_places` | Apify compass/crawler-google-places, "from" price per place | 1.50 | place | VERIFIED | https://apify.com/compass/crawler-google-places | 2026-10-21 |
| `searchapi` | SearchApi Developer, $40 for 10,000 requests a month | 4.00 | request | VERIFIED | https://www.searchapi.io/pricing | 2026-10-21 |

## Notes per provider

- **SerpApi**: a subscription, not credits. Free plan is 250 searches a month with 50 searches per
  hour of throughput. Cached, errored and failed searches are not counted. The news intent uses
  two searches per query (`google` and `google_news`). Whether a card is needed for the free plan
  is not stated on the pages read (UNVERIFIED).
- **Serper**: free tier is 2,500 queries with no card per the homepage. Paid credit packs run
  $0.30 to $1.00 per 1,000 credits. Free-tier expiry is not stated (UNVERIFIED). The news intent
  makes two calls per query.
- **Exa**: free tier is $10 in credits per month, no payment method. Contents (highlights) cost an
  extra $1 per 1,000 pages. How `costDollars` counts highlights was not confirmed (UNVERIFIED),
  which is why the runner uses the reported value when available.
- **Apify**: "from" prices are the best case on higher plans. The free plan is $5 of platform
  usage per month, no card. The local actor is priced per place, and the adapter asks for up to
  10 places per search, so a local query is billed as up to 10 units.
- **SearchApi**: the free trial is 100 requests, which is below a full 50-query run for a
  three-intent comparison.

## Providers excluded from published numbers

Tavily and Brave are not benchmarked. Their terms restrict disclosing performance information or
benchmarking (Tavily terms section 3.2(x), Brave terms section 3(b)(xiii) per the facts file).
Check the current terms yourself before relying on this summary.
