# Draft write-up (provisional): what 50 Indian search queries showed about four search APIs

Status: draft for the author. Numbers come from the first full run (2026-10-22, 09:05 UTC) and are provisional until the repeat run is analysed. Do not publish before the pricing pages are re-checked by eye and the news latencies are re-timed.

---

## Title options

1. I ran 50 Indian search queries through four search APIs. Here is what I found.
2. SerpApi, Serper, Exa and Apify on India queries: speed, completeness and price
3. What a search API costs you when you build for India

## Post (about 330 words)

If you build an AI agent for Indian users, the search API behind it decides whether it can answer "vegan cafe in Indiranagar" with a real place, an address and a rating.

I wanted numbers, so I built a small open benchmark and ran 50 queries: 17 news, 17 local places across six cities, and 16 shopping queries for Indian products. Four providers: SerpApi, Serper, Exa and Apify's Google actors. A Gemini model judged each result list blind, and I measured speed, how complete the fields were, and cost.

What came out of the first run:

- **Local places.** SerpApi had the fastest median (1.5 s) and the best judge score (2.65 of 3). All three providers that serve local put every result inside the right city.
- **News.** Exa was fastest and scored highest (2.94). Apify's actors took about 32 seconds at the median and 101 seconds at the 95th percentile.
- **Shopping.** Serper and SerpApi both returned full price and merchant data. Serper was faster and the judge preferred it (2.75 against 2.31).
- **Price.** Serper cost $1 to $2 per 1,000 searches. SerpApi cost $25. That is 12 to 25 times more.
- **Consistency.** SerpApi never returned an empty result and had every checked field on every news and shopping item. Serper's news endpoint came back empty on 6 of 17 queries, and on 4 of 10 in an earlier run, on mostly different queries.

My read: if price per search is the only thing that matters, Serper wins in this run. If an agent breaks when a search comes back empty or half filled, the consistency numbers are worth weighing against the price.

What I did not measure: reliability over weeks, how many engines each provider covers, legal protections, support. One location, one judge model and 50 queries are a small sample, and I will repeat the run at a different time of day.

Code, queries and method are open: [repo link].

[OPTIONAL disclosure line, your call: "Full disclosure: I am applying for a developer relations role at SerpApi. I built this to understand the product and its rivals, and the repo is independent."]

## Notes for the author

- Replace "[repo link]" after you decide whether to publish under jayydees.
- The news latency cells for SerpApi and Serper are left out of the post on purpose: the first run added a second baseline call to their time. Re-time and add them after the repeat run.
- If the repeat run shows Serper's empty news results disappear, soften or drop that bullet.
- Keep raw provider JSON out of anything you publish. Their terms restrict redistribution.
- Voice check before posting: no dashes as punctuation, no hedging stacks, one clear claim per bullet.
