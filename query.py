#!/usr/bin/env python3
"""SPARQL CLI Dispatcher — Module 9 Week A Stretch.

Dispatches fixed-vocabulary natural-language intents to SPARQL queries
against the publications ontology hosted on Apache Fuseki.

Usage:
    python query.py "list authors at NeurIPS"
    python query.py "papers per topic"
    python query.py "top 5 cited"
    python query.py "2023 paper graph"
    python query.py "any author over 10 papers"
    python query.py "all papers with doi"
    python query.py "coauthor pairs"
    python query.py "hinton authors"
"""

import argparse
import sys
import textwrap

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

FUSEKI_ENDPOINT = "http://localhost:3030/publications/sparql"

PREFIX = """\
PREFIX :     <http://aispire.example.org/publications/>
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>
"""

# ---------------------------------------------------------------------------
# SPARQL query builders  (reused from Integration 9A)
# ---------------------------------------------------------------------------


def sparql_list_authors_at_neurips() -> str:
    """SELECT — authors who have published at NeurIPS."""
    return PREFIX + """
SELECT DISTINCT ?author
WHERE {
    ?paper :authoredBy ?author ;
           :publishedIn :NeurIPS .
}
ORDER BY ?author"""


def sparql_papers_per_topic() -> str:
    """SELECT — paper count grouped by topic."""
    return PREFIX + """
SELECT ?topic (COUNT(?paper) AS ?n)
WHERE {
    ?paper :topic ?topic .
}
GROUP BY ?topic
ORDER BY DESC(?n)"""


def sparql_top_5_cited() -> str:
    """SELECT — top 5 most-cited papers."""
    return PREFIX + """
SELECT ?paper ?cc
WHERE {
    ?paper :citationCount ?cc .
}
ORDER BY DESC(?cc)
LIMIT 5"""


def sparql_construct_2023_graph() -> str:
    """CONSTRUCT — author graph for 2023 papers."""
    return PREFIX + """
CONSTRUCT { ?paper :authoredBy ?author . }
WHERE {
    ?paper a :Paper ;
           :year 2023 ;
           :authoredBy ?author .
}"""


def sparql_ask_author_over_10() -> str:
    """ASK — whether any author has more than 10 papers."""
    return PREFIX + """
ASK {
    SELECT ?author (COUNT(?p) AS ?cnt)
    WHERE {
        ?p :authoredBy ?author .
    }
    GROUP BY ?author
    HAVING (COUNT(?p) > 10)
}"""


def sparql_all_papers_with_doi() -> str:
    """SELECT — every paper and its DOI (OPTIONAL)."""
    return PREFIX + """
SELECT ?paper ?doi
WHERE {
    ?paper a :Paper .
    OPTIONAL { ?paper :doi ?doi . }
}
ORDER BY ?paper"""


def sparql_coauthor_pairs() -> str:
    """SELECT — canonical coauthor pairs (a < b)."""
    return PREFIX + """
SELECT DISTINCT ?a ?b
WHERE {
    ?paper :authoredBy ?a ;
           :authoredBy ?b .
    FILTER (str(?a) < str(?b))
}
ORDER BY ?a ?b"""


def sparql_hinton_authors() -> str:
    """SELECT — authors whose prefLabel or altLabel is 'Hinton'."""
    return PREFIX + """
SELECT DISTINCT ?author
WHERE {
    ?author ?label "Hinton" .
    FILTER (?label = skos:prefLabel || ?label = skos:altLabel)
}"""


# ---------------------------------------------------------------------------
# Intent registry
# ---------------------------------------------------------------------------

INTENTS: dict[str, dict] = {
    "list authors at neurips": {
        "description": "SELECT authors who published at NeurIPS",
        "query_fn": sparql_list_authors_at_neurips,
        "query_type": "select",
    },
    "papers per topic": {
        "description": "SELECT paper count per topic",
        "query_fn": sparql_papers_per_topic,
        "query_type": "select",
    },
    "top 5 cited": {
        "description": "SELECT top 5 most-cited papers",
        "query_fn": sparql_top_5_cited,
        "query_type": "select",
    },
    "2023 paper graph": {
        "description": "CONSTRUCT author graph for 2023 papers",
        "query_fn": sparql_construct_2023_graph,
        "query_type": "construct",
    },
    "any author over 10 papers": {
        "description": "ASK whether any author has >10 papers",
        "query_fn": sparql_ask_author_over_10,
        "query_type": "ask",
    },
    "all papers with doi": {
        "description": "SELECT every paper with its DOI (OPTIONAL)",
        "query_fn": sparql_all_papers_with_doi,
        "query_type": "select",
    },
    "coauthor pairs": {
        "description": "SELECT canonical coauthor pairs",
        "query_fn": sparql_coauthor_pairs,
        "query_type": "select",
    },
    "hinton authors": {
        "description": "SELECT authors matching 'Hinton' label",
        "query_fn": sparql_hinton_authors,
        "query_type": "select",
    },
}


# ---------------------------------------------------------------------------
# Dispatch & execute
# ---------------------------------------------------------------------------


def resolve_intent(raw: str) -> str | None:
    """Normalise the raw string and look it up in INTENTS."""
    normalised = raw.strip().lower()
    return normalised if normalised in INTENTS else None


def get_sparql(intent_key: str) -> str:
    """Return the SPARQL string for a known intent key."""
    return INTENTS[intent_key]["query_fn"]()


def execute_query(sparql: str, query_type: str, endpoint: str) -> None:
    """Send the query to Fuseki and pretty-print results."""
    headers: dict[str, str]
    if query_type in ("select",):
        headers = {"Accept": "application/sparql-results+json"}
    elif query_type == "construct":
        headers = {"Accept": "text/turtle"}
    else:  # ask
        headers = {"Accept": "application/sparql-results+json"}

    try:
        resp = requests.get(
            endpoint,
            params={"query": sparql},
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        print(
            f"ERROR: Cannot reach Fuseki at {endpoint}\n"
            "Make sure `docker compose up -d` is running.",
            file=sys.stderr,
        )
        sys.exit(2)
    except requests.exceptions.HTTPError as exc:
        print(f"ERROR: Fuseki returned {exc.response.status_code}", file=sys.stderr)
        sys.exit(2)

    if query_type == "construct":
        print(resp.text)
        return

    data = resp.json()

    if query_type == "ask":
        print(data["boolean"])
        return

    # SELECT — tabular output
    vars_ = data["results"]["bindings"]
    if not vars_:
        print("(no results)")
        return

    col_names = data["head"]["vars"]
    rows = [
        [b[c]["value"].split("/")[-1] if c in b else "" for c in col_names]
        for b in data["results"]["bindings"]
    ]

    # compute column widths
    widths = [len(c) for c in col_names]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    for row in rows:
        print(fmt.format(*row))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    supported = "\n".join(f'  "{k}"  — {v["description"]}' for k, v in INTENTS.items())
    parser = argparse.ArgumentParser(
        prog="query.py",
        description="SPARQL CLI Dispatcher for the publications ontology.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            f"""\
supported intents:
{supported}

example:
  python query.py "list authors at neurips"
  python query.py "top 5 cited"
  python query.py "any author over 10 papers"
"""
        ),
    )
    parser.add_argument("intent", help="Natural-language intent (see list above).")
    parser.add_argument(
        "--endpoint",
        default=FUSEKI_ENDPOINT,
        help=f"Fuseki SPARQL endpoint (default: {FUSEKI_ENDPOINT})",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    intent_key = resolve_intent(args.intent)
    if intent_key is None:
        print(
            f"ERROR: Unknown intent: '{args.intent}'\n",
            file=sys.stderr,
        )
        parser.print_help(sys.stderr)
        return 1

    sparql = get_sparql(intent_key)
    query_type = INTENTS[intent_key]["query_type"]
    execute_query(sparql, query_type, args.endpoint)
    return 0


if __name__ == "__main__":
    sys.exit(main())
