# Tests

All tests run offline. No test makes a network call and no API key is needed.

The files in `fixtures/` named `synthetic_*.json` are hand-written. They mimic the response
shapes described in each provider's documentation, and they are **not real provider output**.
Real responses are not redistributed because provider terms restrict it. Because the fixtures
are written from documentation, passing tests prove the adapters handle the documented shape, not
that the live API still returns it. Confirm that with a small `--live` run.

Run with:

```
pytest -q --cov=src
```
