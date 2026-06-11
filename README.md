# SPARQL CLI Dispatcher

A command-line tool that maps fixed-vocabulary natural-language intents to SPARQL queries against the **publications ontology** (`data/publications.ttl`) hosted on Apache Fuseki.

This is the **Module 9 Week A — Stretch (Honors Track)** submission.

---

## Quick start

### 1 — Prerequisites

- Docker + Docker Compose
- Python 3.11+

### 2 — Clone and set up

```bash
git clone https://github.com/<your-username>/sparql-cli-dispatcher.git
cd sparql-cli-dispatcher
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3 — Add the data file

Copy `publications.ttl` from your Integration 9A repo into `data/`:

```bash
cp /path/to/integration-9a/data/publications.ttl data/
```

### 4 — Start Fuseki and load data

```bash
docker compose up -d
python load_dataset.py
```

`load_dataset.py` waits up to 60 seconds for Fuseki to be ready, then POSTs `data/publications.ttl` into the `publications` dataset with HTTP Basic Auth (defaults: `admin`/`admin`, matching the `docker-compose.yml`). You only need to run it once — data persists in the Docker volume.

To override credentials:
```bash
FUSEKI_USER=admin FUSEKI_PASSWORD=yourpassword python load_dataset.py
```

### 5 — Run queries

```bash
python query.py "list authors at neurips"
python query.py "papers per topic"
python query.py "top 5 cited"
python query.py "2023 paper graph"
python query.py "any author over 10 papers"
python query.py "all papers with doi"
python query.py "coauthor pairs"
python query.py "hinton authors"
```

Custom endpoint:

```bash
python query.py "top 5 cited" --endpoint http://localhost:3030/publications/sparql
```

---

## Intent → SPARQL mapping

| Intent (exact, case-insensitive) | Query type | SPARQL pattern | Description |
|---|---|---|---|
| `list authors at neurips` | `SELECT` | `DISTINCT ?author` · `:publishedIn :NeurIPS` | All authors who published at NeurIPS |
| `papers per topic` | `SELECT` | `COUNT(?paper)` · `GROUP BY ?topic` | Paper count per topic, descending |
| `top 5 cited` | `SELECT` | `:citationCount` · `ORDER BY DESC` · `LIMIT 5` | Five most-cited papers |
| `2023 paper graph` | `CONSTRUCT` | `CONSTRUCT { ?paper :authoredBy ?author }` · `:year 2023` | Turtle graph of 2023 paper–author triples |
| `any author over 10 papers` | `ASK` | `ASK { … HAVING (COUNT(?p) > 10) }` | Boolean: does any author have >10 papers? |
| `all papers with doi` | `SELECT` | `OPTIONAL { ?paper :doi ?doi }` | Every paper + DOI where present |
| `coauthor pairs` | `SELECT` | `DISTINCT ?a ?b` · `FILTER (str(?a) < str(?b))` | Canonical unordered coauthor pairs |
| `hinton authors` | `SELECT` | `skos:prefLabel` OR `skos:altLabel = "Hinton"` | Authors labelled "Hinton" |

---

## Running the tests

```bash
pytest tests/ -v
```

All tests run **without a live Fuseki instance** — they verify intent resolution logic and SPARQL structural correctness only.

---

## Design notes

### Intent normalisation
`resolve_intent()` lowercases and strips whitespace before lookup, so `"List Authors At NeurIPS"` and `"list authors at neurips"` both resolve correctly.

### Query type dispatch
The `INTENTS` registry stores `query_type` (`"select"`, `"construct"`, `"ask"`) alongside the query builder function. `execute_query()` uses this to set the correct `Accept` header and parse the response accordingly:

- `select` → `application/sparql-results+json` → tabular output
- `construct` → `text/turtle` → raw Turtle printed to stdout
- `ask` → `application/sparql-results+json` → prints `True` / `False`

### Error handling
- Unknown intent → non-zero exit + full `--help` banner listing all supported intents.
- Fuseki unreachable → clear message prompting `docker compose up -d`.
- HTTP error from Fuseki → status code printed and exit code 2.

### Relationship to Integration 9A
The eight SPARQL query builder functions are reused verbatim from Integration 9A (`q1`–`q8`), renamed for clarity. The dispatcher layer (`INTENTS` registry, `resolve_intent`, `execute_query`, `main`) is new work introduced in this Stretch assignment.
