from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src" / "modules"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from src.modules.exploration import _LLR, PRIOR, RANK_PRIOR, Check, Cite, ExplainCheck, Explained, Link, NodeReview, Observation, Record, Refute, explore
from src.modules.issue_model import IssueModel, Scenario

TOP = "Function:pkg/d.py:diophantine"
MERGE = "Function:pkg/d.py:merge_solution"
LEAF = "Function:pkg/d.py:helper"
NOISE = "Function:pkg/other.py:unrelated_thing"
CODE = {
    TOP: ("def diophantine(eq, syms=None, permute=False):\n    if syms != var:\n        return {t for t in diophantine(eq)}\n    sols = merge_solution(var, t, s)\n    return sols", 10),
    MERGE: ("def merge_solution(var, var_t, solution):\n    sol = []\n    return tuple(sol)", 50),
    LEAF: ("def helper(x):\n    return x", 70),
    NOISE: ("def unrelated_thing():\n    pass", 90),
}
EDGES = {("calls", TOP): [(MERGE, 0.95), (NOISE, 0.4)], ("calls", MERGE): [(LEAF, 0.95)]}


def fake_query(cypher: str, params: dict | None = None) -> list[dict]:
    if "n.content AS code" in cypher:
        return [{"id": i, "name": i.split(":")[-1], "sig": CODE[i][0].split("\n")[0][4:-1], "code": CODE[i][0], "start": CODE[i][1]} for i in params["ids"] if i in CODE]
    if "x.type = 'EXTENDS'" in cypher and params["id"] in ("Class:pkg/d.py:Solver", "File:pkg/d.py"):  # the members lane of a class or file
        return [{"id": TOP, "label": "Function", "name": "diophantine", "path": "pkg/d.py", "w": 1.0}]
    if cypher.startswith("MATCH (n)-[r:CodeRelation]->(m) WHERE n.id = $id AND r.type = 'CALLS'"):  # the callee lane
        return [{"id": m, "label": "Function", "name": m.split(":")[-1], "path": m.split(":")[1], "w": w} for m, w in EDGES.get(("calls", params["id"]), [])]
    return []


def C(pid, status, line, quote, *more) -> Check:
    """A check citing (line, quote) plus any further (line, quote) pairs; status confirmed/violated maps to for/against."""
    cites = [Cite(line=line, quote=quote), *(Cite(line=n, quote=q) for n, q in more)]
    return Check(pid=pid, status={"confirmed": "for", "violated": "against"}.get(status, status), cites=cites, reason="because")


def hyps(*items) -> dict:
    return {"hypotheses": list(items)}


def hyp(hid, target, core_node, refute="never"):
    return {
        "id": hid, "claim": f"{hid} defect in `{target.split(':')[-1]}`", "refute_if": refute,
        "anchors": [{"node": target, "role": "target", "via": "self"}],
        "predictions": [{"id": f"{hid}.P1", "kind": "core", "node": core_node, "via": "self", "text": "recursion drops permute"}],
    }


class Explain:
    """Explain-check stub: answers from {observation line: [hypothesis ids]}."""

    def __init__(self, by_line=None):
        self.by_line, self.prompts = by_line or {}, []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        found = re.findall(r"^(O\d+) \S+ L(\d+) ", prompt, re.M)
        claims = dict(re.findall(r"^(H\d+) \[\w+\]: (.*)$", prompt, re.M))
        return ExplainCheck(items=[
            Explained(obs=o, explained_by=[Link(h=h, words=claims[h][:12]) for h in self.by_line.get(int(line), [])])
            for o, line in found
        ])


def run(table, *hs, explain=None, **kw):
    llm = Script(table)
    return explore(ISSUE, hyps(*hs), fake_query, llm, explain or Explain(), **kw), llm


class Script:
    """Answers per (node, hypothesis) from a table; records every prompt."""

    def __init__(self, table):
        self.table, self.prompts = table, []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        node = re.search(r'<node id="([^"]+)"', prompt).group(1)
        hs = re.findall(r"^(H\d+): ", prompt.split("<hypotheses>")[1], re.M)
        recs, obs = [], []
        for h in hs:
            role, checks, refute, nxt, o, *extra = self.table.get((node, h), ("transit", [], None, [], None))
            also, cite = (extra + [[], None])[:2]
            if not cite and role in ("deviation", "co_change") and checks:
                cite = checks[0].cites[0]  # a model citing the location points at the line its check cited
            recs.append(Record(h=h, checks=checks, refute=refute or Refute(met=False, line=0, quote=""), role=role,
                               cite=cite or Cite(line=0, quote=""), next=nxt, also_change=also))
            obs += [o] if o else []
        return NodeReview(records=recs, observations=obs, new_terms=[])


ISSUE = IssueModel(
    title="diophantine loses solutions", issue_type="bug", report_class="code_identifiers", summary="s",
    scenario=Scenario(precondition="", action="", path=""), reproduction_steps=[], observed="{(3, 2)}", expected="8 solutions",
    error_messages=[], stack_trace="", code_snippets=[], environment=[], reporter_hypotheses=[], key_concepts=[],
    explicit_code_refs=[], assumptions=[], unknowns=[],
)
T, M = "pkg/d.py::diophantine", "pkg/d.py::merge_solution"


class ExplorationTest(unittest.TestCase):
    def test_shared_node_is_read_once_for_all_hypotheses(self) -> None:
        _, llm = run({}, hyp("H1", TOP, TOP), hyp("H2", TOP, TOP), max_calls=1)
        self.assertEqual(len(llm.prompts), 1)
        self.assertIn("H1: ", llm.prompts[0])
        self.assertIn("H2: ", llm.prompts[0])
        self.assertIn("   12         return {t for t in diophantine(eq)}", llm.prompts[0])  # numbered tier-2 body

    def test_fake_quote_is_voided_and_violated_core_refutes(self) -> None:
        out, _ = run({
            (T, "H1"): ("deviation", [C("H1.P1", "confirmed", 12, "made up text")], None, [], None),
            (T, "H2"): ("unrelated", [C("H2.P1", "violated", 11, "if syms != var")], None, [], None),
        }, hyp("H1", TOP, TOP), hyp("H2", TOP, TOP), max_calls=1)
        h1, h2 = out["hypotheses"]
        self.assertEqual(h1["predictions"], {"H1.P1": "unchecked"})
        self.assertEqual(h1["reads"][0]["role"], "supports")  # deviation without a valid citation is downgraded
        self.assertEqual(out["citation_failures"], 2)  # the check's quote and the role's quote (same invented line)
        self.assertEqual(h2["status"], "inconclusive")  # one line against: not pruned (seen: a prediction worded as the fix)
        self.assertEqual(h2["evidence"][0]["quote"], "if syms != var")

    def test_evidence_against_is_weighed_not_a_veto(self) -> None:
        table = {(T, "H2"): ("supports", [C("H2.P1", "violated", 11, "if syms != var")], None, ["N1"], None),
                 (M, "H2"): ("supports", [C("H2.P1", "violated", 51, "sol = []")], None, [], None)}
        out, llm = run(table, hyp("H2", TOP, TOP), max_calls=2, prior=PRIOR)
        h2 = out["hypotheses"][0]
        self.assertEqual((h2["status"], h2["belief"]), ("inconclusive", round(PRIOR + 2 * _LLR["core_against"], 3)))
        self.assertIn("H2.P1 [core]", llm.prompts[1])  # violated once: still open, so checked again at the next node
        vetoed, _ = run(table, hyp("H2", TOP, TOP), max_calls=2, prune="veto")  # v9 rule as an ablation
        self.assertEqual((vetoed["hypotheses"][0]["status"], vetoed["calls"]), ("refuted", 1))

    def test_one_read_adds_only_its_strongest_outcome(self) -> None:
        # The same read voids the core prediction and meets refute_if: one outcome (refute), not two.
        out, _ = run({(T, "H1"): ("unrelated", [C("H1.P1", "violated", 14, "return sols")], Refute(met=True, line=14, quote="return sols"), [], None)},
                     hyp("H1", TOP, TOP), max_calls=1, prior=PRIOR)
        h1 = out["hypotheses"][0]
        self.assertEqual((h1["status"], h1["belief"], h1["outcomes"][0]["outcome"]), ("inconclusive", round(PRIOR + _LLR["refute_met"], 3), "refute_met"))

    def test_supported_needs_cited_core_deviation_and_cited_call_chain(self) -> None:
        cite = C("H1.P1", "confirmed", 51, "sol = []")
        out, _ = run({(T, "H1"): ("supports", [], None, ["N1"], None), (M, "H1"): ("deviation", [cite], None, [], None)}, hyp("H1", TOP, MERGE))
        h1 = out["hypotheses"][0]
        self.assertEqual(h1["status"], "supported")
        self.assertEqual(h1["chain"]["links"], [{"from": TOP, "to": MERGE, "edge": "calls", "line": 13, "cited": True}])
        self.assertEqual([(c["node"], c["role"], c["hypotheses"]) for c in out["candidates"]], [(MERGE, "deviation", ["H1"])])

    def test_refute_condition_met_at_three_places_prunes(self) -> None:
        # PRIOR + 3 * LLR(refute_met) is below the prune posterior; two are not.
        out, _ = run({(T, "H1"): ("supports", [], Refute(met=True, line=14, quote="return sols"), ["N1"], None),
                      (M, "H1"): ("supports", [], Refute(met=True, line=52, quote="return tuple(sol)"), ["N1"], None),
                      ("pkg/d.py::helper", "H1"): ("supports", [], Refute(met=True, line=71, quote="return x"), [], None)}, hyp("H1", TOP, TOP), prior=PRIOR)
        h1 = out["hypotheses"][0]
        self.assertEqual((h1["status"], [r["node"] for r in h1["reads"]]), ("refuted", [TOP, MERGE, LEAF]))
        self.assertEqual(out["calls"], 3)  # pruned after the third read; nothing standing, so no explain-check

    def test_anchors_variant_reads_no_neighbour_and_no_expand_stops_when_supported(self) -> None:
        out, _ = run({(T, "H1"): ("transit", [], None, ["N1"], None)}, hyp("H1", TOP, TOP), search=False, expand_reads=0)
        self.assertEqual([r["node"] for r in out["hypotheses"][0]["reads"]], [TOP])
        out, _ = run({(T, "H1"): ("deviation", [C("H1.P1", "confirmed", 11, "if syms != var")], None, [], None)}, hyp("H1", TOP, TOP), expand_reads=0)
        self.assertEqual((out["hypotheses"][0]["status"], len(out["hypotheses"][0]["reads"])), ("supported", 1))

    def test_supported_hypothesis_expands_to_code_that_changes_with_it(self) -> None:
        dev = C("H1.P1", "confirmed", 11, "if syms != var")
        out, llm = run({(T, "H1"): ("deviation", [dev], None, [], None, ["N1", "N2"]),
                        (M, "H1"): ("co_change", [], None, [], None, ["N1"], Cite(line=51, quote="sol = []")),
                        (LEAF, "H1"): ("co_change", [], None, [], None, [], Cite(line=70, quote="not in the code"))}, hyp("H1", TOP, TOP))
        h1 = out["hypotheses"][0]
        self.assertEqual(h1["status"], "supported")
        self.assertIn("does this node also have to change?", llm.prompts[1])
        self.assertEqual([r["node"] for r in h1["reads"]], [TOP, MERGE, LEAF, NOISE])  # 1 + EXPAND_READS, each one the model picked
        self.assertEqual(h1["co_change"], [MERGE])  # LEAF's quote is not in its code: no location
        self.assertEqual([(c["node"], c["role"]) for c in out["candidates"]], [(TOP, "deviation"), (MERGE, "co_change")])

    def test_evidence_against_during_expansion_stops_it(self) -> None:
        out, _ = run({(T, "H1"): ("deviation", [C("H1.P1", "confirmed", 11, "if syms != var")], None, [], None, ["N1"]),
                      (M, "H1"): ("transit", [], Refute(met=True, line=51, quote="sol = []"), [], None)}, hyp("H1", TOP, TOP), prior=PRIOR)
        h1 = out["hypotheses"][0]
        self.assertEqual([r["node"] for r in h1["reads"]], [TOP, MERGE])  # refute met: no longer supported, expansion stops
        self.assertEqual(h1["status"], "partial")
        self.assertEqual([c["node"] for c in out["candidates"]], [TOP])

    def test_belief_starts_at_the_prior_of_the_a3_rank(self) -> None:
        out, _ = run({}, hyp("H1", TOP, TOP), hyp("H2", MERGE, MERGE), hyp("H3", LEAF, LEAF), hyp("H4", NOISE, NOISE), max_calls=0)
        self.assertEqual([h["prior"] for h in out["hypotheses"]], [*RANK_PRIOR, RANK_PRIOR[-1]])  # third and later share one
        out, _ = run({}, hyp("H1", TOP, TOP), max_calls=0, prior=PRIOR)  # A5's revisions: no A3 rank
        self.assertEqual(out["hypotheses"][0]["prior"], PRIOR)

    def test_search_grows_only_from_neighbours_the_model_picks(self) -> None:
        # TOP's cards show MERGE and NOISE; nothing is picked, so nothing else is read (v12 queued both by lexical score).
        out, llm = run({(T, "H1"): ("transit", [], None, [], None)}, hyp("H1", TOP, TOP))
        self.assertEqual(([r["node"] for r in out["hypotheses"][0]["reads"]], out["calls"]), ([TOP], 1))
        self.assertIn("merge_solution", llm.prompts[0].split("<neighbours>")[1])  # it was shown, just not picked
        out, _ = run({(T, "H1"): ("transit", [], None, ["N1"], None)}, hyp("H1", TOP, TOP))
        self.assertEqual([r["node"] for r in out["hypotheses"][0]["reads"]][:2], [TOP, MERGE])

    def test_a_hypothesis_that_cannot_overtake_the_leader_stops_searching(self) -> None:
        # H1 (rank 1) cites a deviation at TOP. H3 (rank 3) reads MERGE, finds nothing, and would still trail H1
        # after even a cited deviation: it stops instead of reading LEAF. With equal priors it would continue.
        dev = C("H1.P1", "confirmed", 11, "if syms != var")
        table = {(T, "H1"): ("deviation", [dev], None, [], None), (M, "H3"): ("transit", [], None, ["N1"], None)}
        h2 = hyp("H2", NOISE, NOISE)
        out, _ = run(table, hyp("H1", TOP, TOP), h2, hyp("H3", MERGE, MERGE), expand_reads=0)
        h3 = out["hypotheses"][2]
        self.assertEqual(([r["node"] for r in h3["reads"]], h3["stopped"]), ([MERGE], "dominated"))
        out, _ = run(table, hyp("H1", TOP, TOP), h2, hyp("H3", MERGE, MERGE), expand_reads=0, prior=PRIOR)
        self.assertEqual([r["node"] for r in out["hypotheses"][2]["reads"]], [MERGE, LEAF])

    def test_a_location_claim_stands_on_its_own_cited_line(self) -> None:
        # v13: an invented role line passed when any check was cited, even one against h; a real line alone did not.
        against = C("H1.P1", "violated", 11, "if syms != var")
        out, _ = run({(T, "H1"): ("deviation", [against], None, [], None, [], Cite(line=999, quote="invented defect"))}, hyp("H1", TOP, TOP), max_calls=1)
        self.assertEqual((out["hypotheses"][0]["reads"][0]["role"], out["candidates"]), ("supports", []))
        out, _ = run({(T, "H1"): ("deviation", [], None, [], None, [], Cite(line=11, quote="if syms != var"))}, hyp("H1", TOP, TOP), max_calls=1)
        self.assertEqual([c["node"] for c in out["candidates"]], [TOP])  # no check needed: the cited line is the evidence

    def test_one_node_is_one_piece_of_evidence_per_hypothesis(self) -> None:
        # H2 checks its prediction at TOP as a bystander while H1 reads it, then reads TOP itself: v13 added
        # both outcomes to H2's belief. Now the node counts once, with the stronger outcome.
        h2 = hyp("H2", MERGE, MERGE)
        h2["anchors"].append({"node": TOP, "role": "path", "via": "self"})
        dev = C("H2.P1", "confirmed", 11, "if syms != var")
        table = {(T, "H1"): ("transit", [], None, [], None), (T, "H2"): ("deviation", [dev], None, [], None)}
        out, _ = run(table, hyp("H1", TOP, TOP), h2, prior=PRIOR)
        h = out["hypotheses"][1]
        self.assertEqual([o["node"] for o in h["outcomes"]].count(TOP), 1)
        self.assertLessEqual(h["belief"], round(PRIOR + _LLR["deviation"], 3))

    def test_next_picked_on_the_read_that_makes_h_supported_is_kept(self) -> None:
        # v13 cleared the frontier on becoming supported and kept only also_change picks: `next` was lost.
        dev = C("H1.P1", "confirmed", 11, "if syms != var")
        out, _ = run({(T, "H1"): ("deviation", [dev], None, ["N1"], None, [])}, hyp("H1", TOP, TOP), prior=PRIOR)
        self.assertEqual([r["node"] for r in out["hypotheses"][0]["reads"]][:2], [TOP, MERGE])

    def test_neighbours_keep_script_dirs_and_drop_tests(self) -> None:
        from src.modules.exploration import _Graph
        rows = [{"id": "Function:examples/plot.py:plot", "label": "Function", "name": "plot", "path": "examples/plot.py", "w": 0.9},
                {"id": "Function:tests/test_a.py:plot", "label": "Function", "name": "plot", "path": "tests/test_a.py", "w": 0.9}]
        g = _Graph(lambda cypher, params=None: rows if "r.type = 'CALLS'" in cypher and "(n)-[r" in cypher else [])
        self.assertEqual([n["id"] for n in g.neighbours(TOP)], ["Function:examples/plot.py:plot"])

    def test_every_function_target_is_read_even_past_the_read_cap_and_a_dominance_stop(self) -> None:
        # A3 v7 names every edit site; v14 read the second target only if the frontier reached it in time.
        h2 = hyp("H2", MERGE, MERGE)
        h2["anchors"].append({"node": LEAF, "role": "target", "via": "self"})
        dev = C("H1.P1", "confirmed", 11, "if syms != var")
        out, _ = run({(T, "H1"): ("deviation", [dev], None, [], None)}, hyp("H1", TOP, TOP), h2, expand_reads=0, max_reads=1)
        self.assertEqual([r["node"] for r in out["hypotheses"][1]["reads"]], [MERGE, LEAF])

    def test_prune_then_backtrack_to_weaker_sibling(self) -> None:
        out, _ = run({(T, "H1"): ("transit", [], None, ["N1", "N2"], None), (M, "H1"): ("unrelated", [], None, ["N1"], None)}, hyp("H1", TOP, TOP))
        reads = [r["node"] for r in out["hypotheses"][0]["reads"]]
        self.assertEqual(reads, [TOP, MERGE, NOISE])  # strong edge first; after the prune, back to the w=0.4 sibling
        self.assertNotIn(LEAF, reads)  # merge_solution unrelated, score fell, helper shares no term
        self.assertEqual(out["hypotheses"][0]["pruned"][0]["node"], MERGE)
        self.assertEqual(out["hypotheses"][0]["status"], "inconclusive")

    def test_explain_check_decides_anomalies_by_mechanism_not_node(self) -> None:
        # Real run: H1 was 'supported' at the gold node for the wrong mechanism, hiding the gold observation.
        # Since v13 the check runs only when there is no candidate (its anomalies feed only A5).
        cite = C("H1.P1", "confirmed", 11, "if syms != var")
        obs = [Observation(text="recursion drops permute", line=12, quote="diophantine(eq)", touches="error"),
               Observation(text="branch on syms order", line=11, quote="syms != var", touches="expected")]

        class Both(Script):
            def invoke(self, prompt):
                out = super().invoke(prompt)
                return NodeReview(records=out.records, observations=obs, new_terms=[])

        explain = Explain({11: ["H1"], 12: []})
        run = lambda llm, ex: explore(ISSUE, hyps(hyp("H1", TOP, TOP)), fake_query, llm, ex, max_calls=1)

        class Liar(Explain):  # links whose words are not in the claim are ignored
            def invoke(self, prompt):
                out = super().invoke(prompt)
                for item in out.items:
                    item.explained_by = [Link(h="H1", words="words that are not in the claim")]
                return out
        out = run(Both({(T, "H1"): ("supports", [cite], None, [], None)}), explain)
        self.assertEqual(out["candidates"], [])
        self.assertIn("H1 [inconclusive]", explain.prompts[0])
        self.assertEqual([(a["line"], a["touches"]) for a in out["anomalies"]], [(12, "observed")])  # error clamped: issue has none
        self.assertEqual(out["calls"], 2)  # one read + one explain-check
        out2 = run(Both({(T, "H1"): ("supports", [cite], None, [], None)}), Liar())
        self.assertEqual(len(out2["anomalies"]), 2)
        # With a candidate, anomalies feed nothing (A5 runs only without one): no explain-check call.
        explain3 = Explain()
        out3 = run(Both({(T, "H1"): ("deviation", [cite], None, [], None)}), explain3)
        self.assertEqual((out3["calls"], out3["anomalies"], explain3.prompts), (1, [], []))

    def test_candidates_rank_by_belief(self) -> None:
        # H2 has a cited core confirmation at TOP before its deviation at MERGE; H1 only the deviation at TOP.
        h1, h2 = hyp("H1", TOP, TOP), hyp("H2", TOP, TOP)
        h2["predictions"].append({"id": "H2.P2", "kind": "core", "node": MERGE, "via": "self", "text": "second"})
        out, _ = run({(T, "H1"): ("deviation", [C("H1.P1", "confirmed", 11, "if syms != var")], None, [], None),
                      (T, "H2"): ("supports", [C("H2.P1", "confirmed", 12, "diophantine(eq)")], None, ["N1"], None),
                      (M, "H2"): ("deviation", [C("H2.P2", "confirmed", 51, "sol = []")], None, [], None)}, h1, h2, prior=PRIOR)
        self.assertEqual([h["status"] for h in out["hypotheses"]], ["contested", "contested"])
        self.assertEqual([c["node"] for c in out["candidates"]], [MERGE, TOP])

    def test_bystander_checks_prediction_at_a_node_read_for_another_hypothesis(self) -> None:
        # H2's prediction names MERGE, but the proving line is in TOP, which H1 reads first.
        h1, h2 = hyp("H1", TOP, TOP), hyp("H2", MERGE, MERGE)
        cite = C("H2.P1", "confirmed", 12, "diophantine(eq)")
        llm = Script({(T, "H1"): ("transit", [], None, [], None), (T, "H2"): ("deviation", [cite], None, [], None)})
        out = explore(ISSUE, hyps(h1, h2), fake_query, llm, Explain(), max_calls=1)
        self.assertIn("H2: H2 defect in `merge_solution` (not searching here", llm.prompts[0])
        h2_out = out["hypotheses"][1]
        self.assertEqual(h2_out["predictions"], {"H2.P1": "confirmed"})
        self.assertEqual(h2_out["checked_at"], [TOP])
        self.assertEqual(h2_out["status"], "partial")  # no search path to TOP, so no closed chain
        self.assertEqual([c["node"] for c in out["candidates"]], [TOP])

    def test_multi_line_check_needs_every_cite_real(self) -> None:
        good = C("H1.P1", "confirmed", 11, "if syms != var", (12, "diophantine(eq)"))
        out, _ = run({(T, "H1"): ("deviation", [good], None, [], None)}, hyp("H1", TOP, TOP))
        self.assertEqual(out["hypotheses"][0]["predictions"], {"H1.P1": "confirmed"})
        self.assertEqual([c["line"] for c in out["hypotheses"][0]["evidence"][0]["cites"]], [11, 12])
        bad = C("H1.P1", "confirmed", 11, "if syms != var", (12, "not in the code"))
        out, _ = run({(T, "H1"): ("deviation", [bad], None, [], None)}, hyp("H1", TOP, TOP))
        self.assertEqual(out["hypotheses"][0]["predictions"], {"H1.P1": "unchecked"})

    def test_class_anchor_with_lane_starts_at_its_methods(self) -> None:
        # A class body is not read as a window; 'members' starts the search at its (inherited) methods.
        h = hyp("H1", TOP, TOP)
        h["anchors"] = [{"node": "Class:pkg/d.py:Solver", "role": "target", "via": "members"}]
        h["predictions"][0]["node"], h["predictions"][0]["via"] = "Class:pkg/d.py:Solver", "members"
        _, llm = run({}, h, max_calls=1)
        self.assertIn('<node id="pkg/d.py::diophantine">', llm.prompts[0])

    def test_file_or_class_target_on_itself_starts_at_its_members(self) -> None:
        # A3 may anchor a whole file (a feature request: 'the helper belongs in this module'); v11 read the file node.
        h = hyp("H1", "File:pkg/d.py", TOP)
        h["anchors"][0]["via"] = "self"
        _, llm = run({}, h, max_calls=1)
        self.assertIn('<node id="pkg/d.py::diophantine">', llm.prompts[0])

    def test_cited_deviation_is_a_candidate_and_one_judgement_per_prediction_per_node(self) -> None:
        refuted = C("H1.P1", "violated", 11, "if syms != var")
        out, _ = run({(T, "H1"): ("deviation", [refuted, C("H1.P1", "confirmed", 12, "diophantine(eq)")], None, [], None)}, hyp("H1", TOP, TOP), max_calls=1)
        self.assertEqual(out["hypotheses"][0]["predictions"], {"H1.P1": "violated"})  # the second check at the same node is ignored
        self.assertEqual([c["node"] for c in out["candidates"]], [TOP])  # a deviation is weighed, not vetoed by one line

    def test_two_supported_at_different_nodes_are_contested(self) -> None:
        c1 = C("H1.P1", "confirmed", 11, "if syms != var")
        c2 = C("H2.P1", "confirmed", 51, "sol = []")
        out, _ = run({(T, "H1"): ("deviation", [c1], None, [], None), (M, "H2"): ("deviation", [c2], None, [], None)},
                     hyp("H1", TOP, TOP), hyp("H2", MERGE, MERGE))
        self.assertEqual([h["status"] for h in out["hypotheses"]], ["contested", "contested"])
        self.assertEqual([c["supported"] for c in out["candidates"]], [1, 1])


    def test_observations_capped_per_node_and_prompt_demands_whole_prediction(self) -> None:
        many = [Observation(text=f"fact {i}", line=11, quote="syms != var", touches="observed") for i in range(5)]

        class Chatty(Script):
            def invoke(self, prompt):
                out = super().invoke(prompt)
                return NodeReview(records=out.records, observations=many, new_terms=[])

        llm = Chatty({})
        out = explore(ISSUE, hyps(hyp("H1", TOP, TOP)), fake_query, llm, Explain(), max_calls=1)
        self.assertEqual(len(out["observations"]), 1)  # capped at 2, then same (node, line) deduped
        self.assertIn("bears `for` or `against` the claim", llm.prompts[0])
        self.assertIn("at most 2 observations", llm.prompts[0])


    def test_citation_only_from_shown_lines_and_short_fragments_must_be_whole_lines(self) -> None:
        from src.modules.exploration import _Graph, _cited
        stats = {"citation_failures": 0}
        lines = {10: "def f(x):", 11: "    if x:", 12: "        return x", 13: "    else:"}
        self.assertTrue(_cited(13, "else:", lines, stats))  # short, but a whole line
        self.assertFalse(_cited(12, "x):", lines, stats))  # short fragment of a line
        self.assertTrue(_cited(12, "return x", lines, stats))
        # A long body shows a window; a quote from a hidden line is rejected even though the line exists.
        long_body = "def big():\n" + "\n".join(f"    step_{i}()" for i in range(200)) + "\n    return merge_solution(x)"
        graph = _Graph(lambda cypher, params=None: [{"id": "F", "name": "big", "sig": "big()", "code": long_body, "start": 1}] if "n.content AS code" in cypher else [])
        graph._neigh["F"] = []
        code, shown = graph.view("F", {"merge_solution"})
        self.assertNotIn(50, shown)  # step_48 is far from the term hit, not shown
        self.assertFalse(_cited(50, "step_48()", shown, stats))
        self.assertTrue(_cited(202, "return merge_solution(x)", shown, stats))

    def test_one_supported_hypothesis_with_two_deviation_nodes_is_not_contested(self) -> None:
        from src.modules.exploration import finalize
        alone = {"id": "H1", "rule_status": "supported", "status": "supported", "core_confirmed": 1, "deviations": [TOP, MERGE]}
        finalize([alone])
        self.assertEqual(alone["status"], "supported")
        other = {"id": "H2", "rule_status": "supported", "status": "supported", "core_confirmed": 1, "deviations": [LEAF]}
        finalize([alone, other])
        self.assertEqual((alone["status"], other["status"]), ("contested", "contested"))

    def test_a_hypothesis_waiting_for_its_own_pick_does_not_join_another_node(self) -> None:
        # H1 picks TOP (higher F); H2 picks MERGE. With one read left, H1 must not also be read at MERGE.
        h1, h2 = hyp("H1", TOP, TOP), hyp("H2", MERGE, MERGE)
        h1["anchors"].append({"node": MERGE, "role": "path", "via": "self"})
        out, _ = run({}, h1, h2, max_reads=1)
        self.assertEqual([len(h["reads"]) for h in out["hypotheses"]], [1, 1])


if __name__ == "__main__":
    unittest.main()
