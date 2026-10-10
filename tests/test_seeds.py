from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src" / "modules"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from src.modules.issue_model import IssueModel, Scenario
from src.modules.repo_profile import _loc
from src.modules.repo_explorer.explore._search.bm25_search import _escape_fts_query
from src.modules.seeds import Judgement, Review, SeedQueries, code_queries, find_seeds, render_seeds, rrf, search

DIOP = "Function:pkg/solvers/diophantine.py:diophantine"
SIGNS = "Function:pkg/utils/iterables.py:permute_signs"
PERM = "Class:pkg/comb/perm.py:Permutation"
SIGNED = "Function:pkg/utils/iterables.py:signed_permutations"
TEST = "Function:pkg/tests/test_d.py:test_diophantine"

# name / FTS hits per search text; everything else returns nothing.
EXACT = {"diophantine": [DIOP, TEST], "permute_signs": [SIGNS]}
FTS = {"permute_signs": [SIGNED], "permute": [PERM, SIGNS], "sign combination": [SIGNS, PERM], "diophantine": [DIOP]}


def fake_query(cypher: str, params: dict | None = None) -> list[dict]:
    if "n.name IN $names" in cypher:
        return [{"id": i, "path": i.split(":")[1], "fan_in": 1} for n in params["names"] for i in EXACT.get(n, [])]
    if "QUERY_FTS_INDEX('Function'" in cypher or "QUERY_FTS_INDEX('Class'" in cypher:
        text = cypher.split("'")[5]
        label = "Function" if "'Function'" in cypher else "Class"
        hits = next((ids for key, ids in FTS.items() if key in text), [])
        return [{"id": i, "path": i.split(":")[1], "score": 5.0 - n} for n, i in enumerate(hits) if i.startswith(label)]
    if "n.signature AS sig" in cypher:
        return [{"id": i, "sig": f"{i.split(':')[-1]}(...)", "code": ""} for i in params["ids"]]
    return []


class Stub:
    def __init__(self, *outputs):
        self.outputs, self.prompts = list(outputs), []

    def invoke(self, prompt: str):
        self.prompts.append(prompt)
        return self.outputs.pop(0)


def issue(**kw) -> IssueModel:
    base = dict(
        title="diophantine incomplete with permute", issue_type="bug", report_class="code_identifiers",
        summary="permute=True misses solutions", scenario=Scenario(precondition="", action="", path=""),
        reproduction_steps=[], observed="", expected="", error_messages=[], stack_trace="",
        code_snippets=["diophantine(n**4 + m**4 - 97, syms=(n, m), permute=True)"], environment=[],
        reporter_hypotheses=[], key_concepts=["sign combinations"], explicit_code_refs=["diophantine"],
        assumptions=[], unknowns=[],
    )
    return IssueModel(**{**base, **kw})


def j(node: str, verdict: str, concept: str = "") -> Judgement:
    return Judgement(id=node, verdict=verdict, concept=concept, reason="because")


class Reviewer(Stub):
    """Review stub over node ids: each queued Review names nodes; they are sent back under the alias the
    prompt shows for them (C1..). A node not shown in this prompt is dropped from the answer."""

    def invoke(self, prompt: str):
        out = super().invoke(prompt)
        alias = {_loc_of(node): a for a, node in re.findall(r"^- (C\d+) (\S+)", prompt.split("<candidates>")[1], re.M)}
        return Review(judgements=[Judgement(id=alias[_loc_of(x.id)], verdict=x.verdict, concept=x.concept, reason=x.reason)
                                  for x in out.judgements if _loc_of(x.id) in alias], new_queries=out.new_queries)


def _loc_of(node: str) -> str:
    return node if "::" in node else _loc(node)  # graph id -> 'path::name'; a shown location stays as is


class SeedsTest(unittest.TestCase):
    def test_code_queries_take_refs_frames_errors_and_snippet_identifiers(self) -> None:
        got = code_queries(issue(
            stack_trace='File "/x/pkg/solvers/diophantine.py", line 3, in merge_solution\n    raise ValueError',
            error_messages=["ValueError: bad syms"],
        ))
        self.assertEqual(got[:4], ["diophantine", "merge_solution", "ValueError: bad syms", "syms"])
        self.assertNotIn("True", got)  # builtins and keywords carry no signal
        self.assertNotIn("DIOPHANTINE", [q.upper() for q in got[1:]])  # case-insensitive dedupe

    def test_fts_literal_keeps_only_word_tokens(self) -> None:
        # '2**4' from a code snippet segfaulted the FTS extension; quotes would break the literal.
        self.assertEqual(_escape_fts_query("n**4 + m**4 - 2**4, it's"), "n 4 m 4 2 4 it s")

    def test_rrf_rewards_nodes_hit_by_many_queries(self) -> None:
        self.assertEqual(rrf([["a", "b"], ["c", "b"]])[0], "b")

    def test_rrf_keeps_a_query_top_hit_above_a_node_many_queries_rank_low(self) -> None:
        lists = [["gold"], *[[*(f"x{i}{j}" for j in range(7)), "generic"] for i in range(2)]]  # k=60 ranks generic first
        self.assertLess(rrf(lists).index("gold"), rrf(lists).index("generic"))

    def test_qualified_query_ranks_its_owner_first(self) -> None:
        other, mine = "Method:pkg/base.py:BaseCommand.handle", "Method:pkg/templates.py:TemplateCommand.handle"
        q = lambda cypher, params=None: (
            [{"id": other, "path": "pkg/base.py", "fan_in": 9}, {"id": mine, "path": "pkg/templates.py", "fan_in": 1}]
            if "n.name IN $names" in cypher else []
        )
        self.assertEqual(search(q, "TemplateCommand.handle")[0], mine)
        self.assertEqual(search(q, "handle")[0], other)  # unqualified: fan-in order

    def test_loop_learns_queries_keeps_maybe_and_unlabelled_drops_tests(self) -> None:
        propose = Stub(SeedQueries(queries=["sign combination", "Diophantine", "permute"]))  # both dupe code queries
        review = Reviewer(
            Review(judgements=[j(DIOP, "relevant", "permute=True"), j(PERM, "irrelevant")], new_queries=["permute_signs", "Permute"]),
            Review(judgements=[], new_queries=[]),  # re-ask of round 1's unlabelled nodes: still nothing
            Review(judgements=[], new_queries=[]),
            Review(judgements=[], new_queries=[]),  # re-ask of round 2
        )
        out = find_seeds(issue(), None, fake_query, propose, review, rounds=2)
        self.assertIn("permute", out["queries"]["code"])  # snippet keyword argument
        self.assertEqual(out["queries"]["llm"], ["sign combination"])
        self.assertEqual(out["queries"]["round2"], ["permute_signs"])  # already-searched 'permute' dropped
        ids = [s["id"] for s in out["seeds"]]
        self.assertEqual(ids[0], DIOP)  # relevant first
        self.assertIn(SIGNS, ids)  # round-1 'maybe' by omission
        self.assertNotIn(PERM, ids)
        self.assertNotIn(TEST, ids)
        self.assertEqual(next(s["round"] for s in out["seeds"] if s["id"] == SIGNED), 2)  # found only via a learned query
        self.assertEqual(out["rejected"], [PERM])
        self.assertEqual(out["concepts"]["permute=True"], [DIOP])
        # round 2 only shows nodes not judged in round 1
        self.assertNotIn("diophantine.py::diophantine", review.prompts[2].split("<candidates>")[1])
        self.assertEqual(out["calls"], 5)  # propose + (review + re-ask) x 2 rounds

    def test_rounds_go_on_with_the_next_window_when_no_query_is_learned(self) -> None:
        review = Reviewer(*[Review(judgements=[], new_queries=[]) for _ in range(6)])
        out = find_seeds(issue(), None, fake_query, Stub(SeedQueries(queries=[])), review, top_k=1, rounds=3)
        self.assertEqual(len(out["rounds"]), 3)  # v6 stopped after round 1 when the model learned nothing
        self.assertEqual(len({n for r in out["rounds"] for n in r["reviewed"]}), 3)  # each round a new window

    def test_learner_model_writes_the_next_rounds_queries_from_a_short_prompt(self) -> None:
        from src.modules.seeds import LearnedQueries
        review = Reviewer(Review(judgements=[j(DIOP, "relevant", "permute=True"), j(PERM, "irrelevant")], new_queries=["Permute"]),
                          *[Review(judgements=[], new_queries=[]) for _ in range(3)])
        learner = Stub(LearnedQueries(queries=["permute_signs", "Permute"]))
        out = find_seeds(issue(), None, fake_query, Stub(SeedQueries(queries=[])), review, learner, rounds=2)
        self.assertEqual(out["queries"]["round2"], ["permute_signs"])  # learner first; searched or duplicate terms dropped
        self.assertEqual(out["learn_calls"], 1)                        # once, between the two rounds
        prompt = learner.prompts[0]
        self.assertIn("diophantine", prompt)                           # the relevant candidate is shown
        self.assertNotIn("perm.py::Permutation", prompt.split("<candidates>")[1])  # the irrelevant one is not
        self.assertNotIn('"issue_type"', prompt)                       # short issue, not the issue-model JSON

    def test_review_is_matched_by_alias_and_missing_labels_are_asked_once_more(self) -> None:
        # v3 matched the model's copy of each full id: 37% of seeds came back unmatched and stayed unlabelled.
        review = Reviewer(
            Review(judgements=[j(DIOP, "relevant", "permute=True")], new_queries=[]),
            Review(judgements=[j(PERM, "irrelevant"), j(SIGNS, "maybe")], new_queries=[]),
        )
        out = find_seeds(issue(), None, fake_query, Stub(SeedQueries(queries=[])), review, rounds=1)
        self.assertIn("- C1 pkg/solvers/diophantine.py::diophantine", review.prompts[0])  # alias + location, no graph id
        self.assertNotIn("diophantine.py::diophantine", review.prompts[1].split("<candidates>")[1])  # re-ask: only the missing
        self.assertEqual(out["rejected"], [PERM])
        self.assertEqual({s["id"]: s["reason"] for s in out["seeds"]}, {DIOP: "because", SIGNS: "because"})

    def test_seeds_sort_by_retrieval_score_within_a_verdict(self) -> None:
        review = Reviewer(Review(judgements=[], new_queries=[]), Review(judgements=[], new_queries=[]))
        out = find_seeds(issue(), None, fake_query, Stub(SeedQueries(queries=[])), review, rounds=1)
        scores = [s["score"] for s in out["seeds"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_path_and_module_queries_hit_the_file(self) -> None:
        files = ["pkg/solvers/diophantine.py", "other/diophantine.py", "pkg/solvers/__init__.py"]
        q = lambda cypher, params=None: (
            [{"id": f"File:{f}", "path": f} for f in files if f.rsplit("/", 1)[-1] in params["names"]] if "MATCH (n:File)" in cypher else []
        )
        self.assertEqual(search(q, "pkg/solvers/diophantine.py")[0], "File:pkg/solvers/diophantine.py")
        self.assertEqual(search(q, "/usr/lib/site/pkg/solvers/diophantine.py")[0], "File:pkg/solvers/diophantine.py")  # trace path
        self.assertEqual(search(q, "pkg.solvers.diophantine")[0], "File:pkg/solvers/diophantine.py")
        self.assertEqual(search(q, "pkg.solvers")[0], "File:pkg/solvers/__init__.py")  # a package
        self.assertEqual(search(q, "`pkg/solvers/diophantine.py`")[0], "File:pkg/solvers/diophantine.py")  # quoted in markdown
        self.assertEqual(set(search(q, "diophantine.py")), {"File:pkg/solvers/diophantine.py", "File:other/diophantine.py"})  # bare file name
        self.assertEqual(search(q, "diophantine"), [])  # a bare name never matches a file

    def test_a_common_bare_name_keeps_only_its_best_exact_matches(self) -> None:
        many = [{"id": f"Method:m{i}.py:K{i}.__init__", "path": f"m{i}.py", "fan_in": i} for i in range(9)]
        q = lambda cypher, params=None: many if "n.name IN $names" in cypher else []
        self.assertEqual(search(q, "__init__"), ["Method:m8.py:K8.__init__", "Method:m7.py:K7.__init__", "Method:m6.py:K6.__init__"])

    def test_script_dirs_rank_last_but_tests_stay_out(self) -> None:
        rows = [{"id": "Function:examples/plot.py:plot", "path": "examples/plot.py", "fan_in": 9},
                {"id": "Function:tests/test_a.py:plot", "path": "tests/test_a.py", "fan_in": 9},
                {"id": "Function:pkg/a.py:plot", "path": "pkg/a.py", "fan_in": 1}]
        q = lambda cypher, params=None: rows if "n.name IN $names" in cypher else []
        # 7 Loc-Bench instances have all their gold under examples/ or benchmarks/; v3 dropped them.
        self.assertEqual(search(q, "plot"), ["Function:pkg/a.py:plot", "Function:examples/plot.py:plot"])

    def test_each_query_head_is_judged_before_the_rest_of_the_rrf_order(self) -> None:
        # xarray-4493: the issue's own 'as_variable' was searched and ranked first by its query, but ~30 other
        # lists sharing generic nodes pushed it past the 30-node window under plain RRF.
        from src.modules.seeds import _window_order, rrf_scores
        shared = [f"g{i}" for i in range(5)]
        lists = {f"q{i}": [*shared] for i in range(6)} | {"as_variable": ["gold", *shared]}
        order = _window_order(lists, rrf_scores(lists.values()))
        self.assertLess(order.index("gold"), 2)  # heads first: 'g0' (head of six lists) and 'gold'
        self.assertGreater(sorted(rrf_scores(lists.values()), key=lambda n: -rrf_scores(lists.values())[n]).index("gold"), 1)

    def test_window_contains_unique_nodes_not_repeated_query_heads(self) -> None:
        from src.modules.seeds import _window_order, rrf_scores
        lists = {"one": ["a", "b"], "two": ["a", "c"]}
        order = _window_order(lists, rrf_scores(lists.values()))
        self.assertEqual(order, ["a", "b", "c"])

    def test_fresh_round_uses_first_unjudged_hit_before_old_backlog(self) -> None:
        from src.modules.seeds import _window_order, rrf_scores
        lists = {"old": ["old", "tail"], "new": ["seen", "fresh"]}
        scores = rrf_scores(lists.values())
        order = _window_order(lists, scores, fresh={"new": lists["new"]}, judged={"seen"})
        self.assertEqual(order[0], "fresh")
        self.assertNotIn("seen", order)
        self.assertEqual(len(order), len(set(order)))

    def test_final_scores_and_hits_include_queries_after_a_node_was_reviewed(self) -> None:
        from unittest.mock import patch
        from src.modules.seeds import rrf_scores
        lists = {"alpha": [DIOP], "beta": [SIGNS], "later": [SIGNS, DIOP]}
        reviewer = Reviewer(
            Review(judgements=[j(DIOP, "relevant")], new_queries=["later"]),
            Review(judgements=[j(SIGNS, "relevant")], new_queries=[]),
        )
        with patch("src.modules.seeds.search", side_effect=lambda q, text: lists.get(text, [])):
            out = find_seeds(issue(explicit_code_refs=["alpha"], code_snippets=[]), None,
                             fake_query, Stub(SeedQueries(queries=["beta"])), reviewer, top_k=1, rounds=2)
        expected = rrf_scores(lists.values())
        by_id = {s["id"]: s for s in out["seeds"]}
        self.assertEqual(by_id[DIOP]["score"], round(expected[DIOP], 5))
        self.assertEqual(by_id[DIOP]["hit_by"], ["alpha", "later"])
        self.assertEqual(out["calls"], 3)
        self.assertEqual(out["rounds"][1]["reviewed"], [SIGNS])

    def test_a_query_the_driver_rejects_does_not_crash_retrieval(self) -> None:
        # scipy-21801: the code reference '[2]' made the exact-name query raise and aborted A2.
        def q(cypher, params=None):
            if "n.name IN $names" in cypher:
                raise RuntimeError("Binder exception: Expression n.name has data type STRING but expected INT8[].")
            return fake_query(cypher, params)
        self.assertEqual(search(q, "[2]"), [])
        self.assertEqual(search(q, "permute"), [PERM, SIGNS])  # BM25 hits still come back

    def test_profile_links_and_render(self) -> None:
        profile = {
            "repo": "o/r", "commit": "c", "packages": [], "families": [], "dispatch": [], "blind_spots": [], "caveat": "",
            "errors": [{"exception": "Class:pkg/solvers/diophantine.py:DiopError", "raised_in": [DIOP], "raise_sites": 1, "message": "", "caught_in": []}],
        }
        propose = Stub(SeedQueries(queries=[]))
        review = Reviewer(Review(judgements=[j(DIOP, "relevant", "permute=True")], new_queries=[]), Review(judgements=[], new_queries=[]))
        out = find_seeds(issue(), profile, fake_query, propose, review, rounds=1)
        self.assertIn("<repo_profile", propose.prompts[0])
        self.assertEqual(out["profile_links"], [f"exception pkg/solvers/diophantine.py::DiopError raised in pkg/solvers/diophantine.py::diophantine"])
        text = render_seeds(out)
        self.assertIn("- permute=True:\n  - pkg/solvers/diophantine.py::diophantine [relevant]", text)


if __name__ == "__main__":
    unittest.main()
