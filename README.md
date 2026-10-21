# serpapi-india-search-benchmark

A reproducible benchmark of search APIs for India-focused queries. It compares SerpApi, Serper.dev, Exa and Apify's Google actors (SearchApi.io is an optional extra) on three intents:

1. **News and general web**: fresh, time-sensitive queries such as cricket fixtures, RBI explainers and phone launches.
2. **Local places** in Indian cities: "vegan cafe in Indiranagar", "24 hour pharmacy near Koramangala".
3. **Shopping**: Indian consumer products where the INR price and the merchant matter, such as "whey protein 1kg" or "mixer grinder 750 watt".

No results are published here yet. The repo is the method and the harness. Run it with your own keys and read the numbers it produces.

## Why India and these three intents

An agent that grounds its answers in search needs more than ten blue links. For an Indian user it needs fresh local news, a place with an address and a rating in the right city, and a price in rupees from a merchant that ships there. A provider can do well on a US-style web query and still return thin or mis-located data for these. The benchmark measures that gap with plain, inspectable metrics: success rate, latency, structured-field completeness, India relevance, cost, and an optional blind LLM judge.

Tavily and Brave are left out of the published tables on purpose. Their terms restrict disclosing performance information or benchmarking, so the repo does not ship adapters for them.

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

## Limitations

- Latency is measured from wherever you run the script, including your network.
- Small samples produce noisy differences. Treat sub-10-point gaps with caution.
- Domain overlap with SerpApi is an agreement measure. It does not say who is right.
- The LLM judge is noisy and biased. It is one signal and is off by default. Agreement with human labels on a small subset is a TODO for the author.
- Some provider parameters are unverified; see the verify-live list in `METHODOLOGY.md`.
- Pricing rows need a by-eye re-check before any cost number is published.

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
