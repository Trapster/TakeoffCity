# TakeoffCity

Group travel coordination app. FastAPI backend + Flask webapp + PostgreSQL.

---

## Running the app

```bash
cp .env.example .env   # fill in values
docker compose up --build
```

---

## Tests

Tests live in `tests/`. Backend tests use a real PostgreSQL instance; webapp tests mock all HTTP calls. See `tests/INSTRUCTIONS.md` for how to add new tests.

### Pre-deployment — run the full suite

```bash
docker compose -f docker-compose.test.yml up --build all-tests
docker compose -f docker-compose.test.yml down -v
```

Both test containers run in parallel. `all-tests` is a gate service that only starts (and exits 0) once both suites pass — if either fails, the command exits non-zero.

### After a fix — run only previously failing tests

```bash
docker compose -f docker-compose.test.yml run --rm backend-test pytest --lf
docker compose -f docker-compose.test.yml run --rm webapp-test pytest --lf
```

`--lf` (last-failed) skips every test that passed last time. The cache is stored in a named Docker volume so it persists between runs.

### Target a specific test file or case

```bash
docker compose -f docker-compose.test.yml run --rm backend-test \
  pytest tests/test_events.py -v

docker compose -f docker-compose.test.yml run --rm backend-test \
  pytest tests/test_events.py::test_get_event_not_found -v
```

### Debugging with pdb

Add `import pdb; pdb.set_trace()` anywhere in a test or in source code, then run with an interactive TTY and `-s` to disable output capture:

```bash
docker compose -f docker-compose.test.yml run --rm -it backend-test \
  pytest tests/test_events.py::test_get_event_not_found -s

docker compose -f docker-compose.test.yml run --rm -it webapp-test \
  pytest tests/test_proxy.py::test_proxy_injects_username_header -s
```

### Teardown

```bash
docker compose -f docker-compose.test.yml down -v
```

The `-v` flag removes the named volumes (including the pytest cache). Omit it if you want `--lf` to remember failures across a full teardown.
