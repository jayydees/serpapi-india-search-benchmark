# serpapi-india-search-benchmark

A reproducible benchmark of search APIs for India-focused queries. It compares SerpApi, Serper.dev, Exa and Apify's Google actors (SearchApi.io is an optional extra) on three intents:

1. **News and general web**: fresh, time-sensitive queries such as cricket fixtures, RBI explainers and phone launches.
2. **Local places** in Indian cities: "vegan cafe in Indiranagar", "24 hour pharmacy near Koramangala".
3. **Shopping**: Indian consumer products where the INR price and the merchant matter, such as "whey protein 1kg" or "mixer grinder 750 watt".

The repo is the method and the harness. Results from two runs are below. Run it with your own keys and read the numbers it produces.

## Why India and these three intents?

AI agents need more than a list of links. An agent serving Indian users may need a fresh news article, a local business with the right address and rating, or a product price in rupees from a relevant merchant. Search APIs that look similar on generic web queries may behave differently on these structured, location-sensitive tasks.

This benchmark compares SerpApi, Serper, Exa and Apify across 50 India-focused queries spanning news, local places and shopping. It measures success rate, latency, structured-field completeness, India relevance and cost, with an optional blind LLM judge.

The goal is not to crown a universal winner. It is to understand where each provider performs well, where its limitations appear, and what developers gain for the price they pay. The results can help developers choose a provider for their use case and help identify where SerpApi's reliability and structured data justify its premium.

Tavily and Brave are excluded from the published comparison because the terms reviewed for this project restrict publishing benchmark or performance comparisons. Their adapters are therefore not included. Recheck each provider's current terms before expanding the benchmark.

## Quick start

```
python -m venv .venv
.venv\Scripts\activate          # macOS and Linux: source .venv/bin/activate
pip install -e ".[dev]"
pytest -q --cov=src             # all tests are offline

indiasearchbench run --providers serpapi,serper,exa --limit 5           # dry run, no API calls
indiasearchbench run --providers serpapi,serper,exa --limit 5 --live    # spends credits
indiasearchbench report runs/<timestamp>                                 # rebuild results.md
```

A dry run prints the plan: queries selected, calls and estimated credits per provider, and which environment variables are set. `--live` is required before anything is sent.

### Options

| Option | Meaning |
|---|---|
| `--providers` | Comma list from `serpapi,serper,exa,apify,searchapi`. Default `serpapi,serper,exa,apify`. |
| `--intents` | Comma list from `news,local,shopping`. Default all three. |
| `--limit N` | First N queries of each intent, in file order. |
| `--live` | Call the APIs. Without it the command is a dry run. |
| `--judge` | Score each result list with the blind Gemini judge. Off by default. |
| `--max-serpapi-searches` | Budget guard for SerpApi, default 160. |
| `--resume runs/<dir>` | Continue a run; pairs already in `results.json` are skipped. |

## Environment variables

Keys are read from the environment, or from a local `.env` file in the folder you run the command from (copy `.env.example` to `.env`; it is gitignored). Real environment variables win over `.env`. Keys are never logged and are redacted from error text and saved files. A provider whose variable is missing is skipped with a message.

| Variable | Used for |
|---|---|
| `SERPAPI_API_KEY` | SerpApi searches and the free Account API |
| `SERPER_API_KEY` | Serper.dev |
| `EXA_API_KEY` | Exa |
| `APIFY_TOKEN` | Apify actors |
| `SEARCHAPI_API_KEY` | SearchApi.io (optional) |
| `GEMINI_API_KEY` | Judge, only with `--judge` |
| `JUDGE_MODEL` | Gemini model id for the judge. No default is built in. |

## Running inside free tiers

Free allowances read on 2026-10-21 (see `docs/PRICING.md`): SerpApi 250 searches a month with 50 per hour, Serper 2,500 queries, Exa $10 a month, Apify $5 a month. SerpApi's news intent makes two searches per query and Serper's makes two calls, so counts are not one per query.

- `--limit 5` runs 15 queries per provider. SerpApi uses 20 searches, which fits inside one hour of free throughput.
- `--limit 10` uses 40 SerpApi searches and still fits inside one hour.
- The full 50 queries need 67 SerpApi searches. That is more than 50 per hour, so run it in two sittings with `--resume`.

The runner reads `account.json` before and after, and refuses to start if the planned searches exceed the guard or the searches left.

## Output

Each live run writes to `runs/<timestamp>/`, which is gitignored:

- `raw/` holds raw provider responses. They stay on your machine and are never committed, because provider terms restrict redistribution.
- `results.json` holds derived records: latency, status, normalised result fields and judge scores.
- `results.md` holds tables per intent, a cost table, a "where each provider wins and loses" section built only from the numbers, and a methods block with date and versions.

The shape of the report, with placeholder numbers that are not measurements:

```
## local
| Provider | Queries | Success | p50 latency | ... | USD per 1,000 queries |
|---|---|---|---|---|---|
| provider-a | XX | XX% | XXXX ms | ... | $X.XX |
| provider-b | XX | XX% | XXXX ms | ... | $X.XX |
```

A metric that cannot be computed, for example completeness for a provider that has no structured block, shows `n/a`. A provider that does not offer an intent is `n/a` for it, never zero.

## Results (two runs)

Two live runs from one location in India, both with SerpApi's cache bypassed and a blind Gemini judge (`gemini-3.5-flash-lite`, via the `gemini-flash-lite-latest` alias).

- **Run 1:** 50 queries, started 2026-10-22 09:05 UTC (14:35 IST, early morning in Austin).
- **Run 2:** the first 10 queries of each intent, started 2026-10-22 13:44 UTC (about 9 am in Austin).

The tables compare both runs on the same 10 queries per intent. Sample sizes are small, so treat gaps smaller than about 0.5 judge points or 25% in speed as noise. Prices come from `docs/PRICING.md`, read from each provider's pricing page on 2026-10-21 and re-checked in a browser on 2026-10-22. Raw responses are not published because provider terms restrict redistribution.

Exa offers news only. Apify's actors cover news and local. Median is in milliseconds. "Empty" counts queries where the provider answered with no items.

### Local places

| Provider | Median R1 / R2 | Fields complete R2 | Judge R1 / R2 | Empty R1 / R2 | USD per 1,000 |
|---|---|---|---|---|---|
| SerpApi | 1,582 / 1,197 | 98% | 2.4 / 2.4 | 0 / 0 | $25.00 |
| Serper | 1,661 / 1,661 | 87% | 2.2 / 2.3 | 0 / 0 | $1.00 |
| Apify | 12,005 / 11,949 | 100% | 2.2 / 2.3 | 0 / 0 | $15.00 |

All three returned places inside the query city every time.

### News and general web

| Provider | Median R2 | Fields complete R2 | Judge R1 / R2 | Empty R1 / R2 | USD per 1,000 |
|---|---|---|---|---|---|
| Exa | 2,998 | 90% | 3.0 / 3.0 | 0 / 0 | $7.00 |
| SerpApi | 1,391 | 100% | 2.67 / 1.80 | 0 / 0 | $25.00 |
| Serper | 2,361 | 50% | 2.2 / 2.5 | 2 / 5 | $1.00 |
| Apify | 22,348 | n/a | 2.2 / 2.1 | 0 / 0 | $1.80 |

Run 1 times for SerpApi and Serper news added a second baseline call, so only Run 2 is comparable.

### Shopping

| Provider | Median R1 / R2 | Fields complete R2 | Judge R1 / R2 | Empty R1 / R2 | USD per 1,000 |
|---|---|---|---|---|---|
| Serper | 1,771 / 1,612 | 100% | 2.8 / 2.8 | 0 / 0 | $2.00 |
| SerpApi | 1,946 / 2,123 | 100% | 2.6 / 2.4 | 0 / 0 | $25.00 |

### What the two runs show

- **Speed repeated for local and shopping.** Medians moved by less than half a second between runs. SerpApi had the fastest local median in both. Serper was faster on shopping in both.
- **SerpApi never returned an empty result,** and every news and shopping item had all the fields checked. Serper returned an empty news answer for 2 of 10 queries in Run 1 and 5 of 10 in Run 2. Sending the same request again alone gave 0 items for one query three times and 10, 0, 10 for another, so the empties come and go for the same query, and a call order effect is ruled out. Serper billed 1 credit for those empty answers.
- **Exa led news on the judge** (3.0 in both runs). SerpApi's news judge score moved from 2.67 to 1.80 between runs, which shows how noisy a single LLM judge is.
- **Price:** Serper costs 12 to 25 times less per search than SerpApi in every intent where both ran. Apify's actors were much slower than the direct APIs, with news at 22 to 28 seconds at the median and a p95 near 90 to 100 seconds.

Not measured: reliability over weeks, the breadth of engines, legal protections, support and documentation.

## How this benchmark was checked

The first live runs found six mistakes in my own code and metrics. I fixed each one before trusting any number. Each fix has a test, and METHODOLOGY.md has the details.

1. **A bad SerpApi request.** The news call sent a parameter (`so`) that SerpApi rejects when `q` is present. Every news query failed until I removed it.
2. **A misleading shopping score.** India relevance counted `.in` links. SerpApi's links point to `google.co.in` because of the request setting, so it scored 100% by accident. Shopping now counts items priced in rupees.
3. **Cached results counted as live.** A repeated SerpApi query returned the first search's data in 60 to 100 ms. The harness now detects cached responses by the age of `processed_at`, and a `--serpapi-no-cache` option times every search live.
4. **An unfair local score.** Serper's place addresses leave out the city, so an address check gave it 42% and the others 100%. Local relevance now uses distance from the city centre.
5. **Lists of different lengths.** Providers return 10, 20, 40 or 100 items. Completeness and relevance now use each provider's first 10.
6. **A hidden second call.** For news, SerpApi and Serper also get a web search that only feeds the overlap metric. That call is now left out of latency and cost.

One finding is still open: Serper's news endpoint returned no items for about a third of the queries in two runs, on mostly different queries. A repeat run at a different time of day will show whether this is a pattern.

## Limitations

- Latency is measured from wherever you run the script, including your network.
- Small samples produce noisy differences. Treat sub-10-point gaps with caution.
- Domain overlap with SerpApi is an agreement measure. It does not say who is right.
- The LLM judge is noisy and biased. It is one signal and is off by default. Agreement with human labels on a small subset is a TODO for the author.
- Some provider parameters are unverified; see the verify-live list in `METHODOLOGY.md`.
- Prices change. `docs/PRICING.md` records the date each price was read.

See `METHODOLOGY.md` for exact metric definitions.

## Ethics and independence

This is an independent project and is not affiliated with any provider named here. It calls each provider's public API with your own key. Raw responses are not redistributed. Queries are generic and publicly harmless.

## Adding a provider

1. Add `src/indiasearchbench/providers/<name>.py` with a `Provider` subclass. Set `name`, `env_var`, `intents` and `structured`, then implement `build_requests` and `parse`.
2. Register it in `src/indiasearchbench/providers/__init__.py`.
3. Add a row to the table in `docs/PRICING.md` whose key matches `pricing_key`.
4. Add a hand-written `synthetic_<name>_*.json` fixture and tests for the exact request and the normalised output.

## License

MIT, see `LICENSE`.
