"""pytest suite — verifies intent dispatch without a live Fuseki instance.

Tests cover:
  - Each intent resolves to a key in INTENTS.
  - Each intent's SPARQL contains structural markers for its query type.
  - An unknown intent exits non-zero and prints the usage banner.
"""

import subprocess
import sys

import pytest

# ---------------------------------------------------------------------------
# Import the dispatcher under test
# ---------------------------------------------------------------------------
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from query import (  # noqa: E402
    INTENTS,
    build_parser,
    get_sparql,
    resolve_intent,
    sparql_all_papers_with_doi,
    sparql_ask_author_over_10,
    sparql_coauthor_pairs,
    sparql_construct_2023_graph,
    sparql_hinton_authors,
    sparql_list_authors_at_neurips,
    sparql_papers_per_topic,
    sparql_top_5_cited,
)

# ---------------------------------------------------------------------------
# Intent resolution
# ---------------------------------------------------------------------------


class TestResolveIntent:
    def test_exact_match(self):
        assert resolve_intent("list authors at neurips") == "list authors at neurips"

    def test_case_insensitive(self):
        assert resolve_intent("List Authors At NeurIPS") == "list authors at neurips"

    def test_strips_whitespace(self):
        assert resolve_intent("  top 5 cited  ") == "top 5 cited"

    def test_unknown_returns_none(self):
        assert resolve_intent("who are the authors") is None

    def test_all_intents_resolve(self):
        for key in INTENTS:
            assert resolve_intent(key) == key, f"Intent '{key}' did not self-resolve"


# ---------------------------------------------------------------------------
# SPARQL structure — SELECT intents
# ---------------------------------------------------------------------------


class TestSelectQueries:
    """Each SELECT query must contain the expected structural keywords."""

    def _assert_select(self, sparql: str, *expected_fragments: str):
        upper = sparql.upper()
        assert "SELECT" in upper, "Missing SELECT keyword"
        for frag in expected_fragments:
            assert frag.upper() in upper, f"Expected fragment not found: {frag!r}"

    def test_list_authors_at_neurips(self):
        q = sparql_list_authors_at_neurips()
        self._assert_select(q, "DISTINCT", "NeurIPS", "publishedIn")

    def test_papers_per_topic(self):
        q = sparql_papers_per_topic()
        self._assert_select(q, "COUNT", "GROUP BY", "topic")

    def test_top_5_cited(self):
        q = sparql_top_5_cited()
        self._assert_select(q, "citationCount", "ORDER BY DESC", "LIMIT 5")

    def test_all_papers_with_doi(self):
        q = sparql_all_papers_with_doi()
        self._assert_select(q, "OPTIONAL", "doi")

    def test_coauthor_pairs(self):
        q = sparql_coauthor_pairs()
        self._assert_select(q, "DISTINCT", "FILTER", "authoredBy")

    def test_hinton_authors(self):
        q = sparql_hinton_authors()
        self._assert_select(q, "DISTINCT", "Hinton", "prefLabel")


# ---------------------------------------------------------------------------
# SPARQL structure — CONSTRUCT intent
# ---------------------------------------------------------------------------


class TestConstructQuery:
    def test_construct_2023_graph(self):
        q = sparql_construct_2023_graph()
        upper = q.upper()
        assert "CONSTRUCT" in upper
        assert "2023" in q
        assert "authoredBy" in q


# ---------------------------------------------------------------------------
# SPARQL structure — ASK intent
# ---------------------------------------------------------------------------


class TestAskQuery:
    def test_ask_author_over_10(self):
        q = sparql_ask_author_over_10()
        upper = q.upper()
        assert "ASK" in upper
        assert "HAVING" in upper
        assert "COUNT" in upper
        assert "10" in q


# ---------------------------------------------------------------------------
# get_sparql helper
# ---------------------------------------------------------------------------


class TestGetSparql:
    def test_returns_string_for_every_intent(self):
        for key in INTENTS:
            result = get_sparql(key)
            assert isinstance(result, str)
            assert len(result) > 20

    def test_query_type_metadata(self):
        """Each intent must have a recognised query_type."""
        valid_types = {"select", "construct", "ask"}
        for key, meta in INTENTS.items():
            assert meta["query_type"] in valid_types, (
                f"Intent '{key}' has invalid query_type: {meta['query_type']}"
            )

    def test_at_least_one_construct(self):
        types = [m["query_type"] for m in INTENTS.values()]
        assert "construct" in types

    def test_at_least_one_ask(self):
        types = [m["query_type"] for m in INTENTS.values()]
        assert "ask" in types

    def test_at_least_one_select(self):
        types = [m["query_type"] for m in INTENTS.values()]
        assert "select" in types


# ---------------------------------------------------------------------------
# Coverage: at least 5 intents
# ---------------------------------------------------------------------------


class TestIntentCoverage:
    def test_minimum_five_intents(self):
        assert len(INTENTS) >= 5, f"Only {len(INTENTS)} intents registered; need >= 5"


# ---------------------------------------------------------------------------
# CLI — unknown intent exits non-zero with usage banner
# ---------------------------------------------------------------------------


class TestCLIUnknownIntent:
    def _run(self, *args):
        return subprocess.run(
            [sys.executable, "query.py", *args],
            capture_output=True,
            text=True,
            cwd=str(__import__("pathlib").Path(__file__).parent.parent),
        )

    def test_unknown_intent_exits_nonzero(self):
        result = self._run("this intent does not exist")
        assert result.returncode != 0

    def test_unknown_intent_prints_error(self):
        result = self._run("this intent does not exist")
        combined = result.stdout + result.stderr
        assert "unknown intent" in combined.lower() or "error" in combined.lower()

    def test_unknown_intent_shows_usage(self):
        result = self._run("this intent does not exist")
        combined = result.stdout + result.stderr
        # The help output should list at least one known intent
        assert "neurips" in combined.lower() or "topic" in combined.lower()

    def test_no_args_exits_nonzero(self):
        result = self._run()
        assert result.returncode != 0

    def test_help_flag_exits_zero(self):
        result = self._run("--help")
        assert result.returncode == 0
        assert "intent" in result.stdout.lower()
