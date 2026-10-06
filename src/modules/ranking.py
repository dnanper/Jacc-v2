"""Design v3: probabilistic scoring of edit-set candidates (research/codekg-survey/DESIGN_PROBABILISTIC_EDITSET.vn.md).
Deterministic, no LLM, reads saved A2/A3 artifacts.

- `candidates`: one row per function node A3 or A2 produced, with the features of §4.5 of the design;
  rows come in the Ranked-prior order (targets of H1, H2, ... in A3 order, then A2 function seeds, then the
  remaining anchors), so the prior arm is the row order itself;
- `fit_logistic` / `predict`: the calibrator, L2-regularised logistic regression fitted by Newton steps;
- `fit_conditional_logit`: a within-instance ranker (softmax over one instance's candidates; amendment A2);
- `expected_f1_prefix`: how many top rows to answer so that expected F1 is largest;
- `crc_threshold`: conformal risk control threshold for a recall target;
- metrics: ranking (`average_precision`, `acc_at`, `reciprocal_rank`, `ndcg`), GraphLocator set metrics
  (`set_metrics`), calibration (`brier`, `ece`);
- `load_calibrator` / `decide`: the frozen V6 calibrator (data/calibrator_v6.json) and the answer it gives.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from src.modules.repo_profile import _loc

FUNCTION_KINDS = ("Function:", "Method:", "Constructor:")
CALIBRATOR = Path(__file__).parent / "data" / "calibrator_v6.json"
FEATURES = ("target_rank_inv", "in_h1", "hyp_share", "vote", "anchor_only", "seed_relevant", "seed_maybe",
            "seed_rank_inv", "same_file_h1", "same_class_h1")
FEATURES_V2 = FEATURES + ("named_in_issue", "class_named", "file_named", "in_trace", "seed_score", "seed_hits")  # amendment A2
GRAPH_SOURCES = {"g_root": "root", "g_alt": "alternate hypothesis", "g_container": "region container",
                 "g_family": "implementation family", "g_call1": "call hop 1", "g_call2": "call hop 2"}
FEATURES_V3 = FEATURES_V2 + tuple(GRAPH_SOURCES)  # amendment A3
FEATURES_V4 = FEATURES_V3 + ("v_shown", "v_edited", "v_maybe", "v_rank_inv")  # amendment A4: listwise verifier
FEATURES_V5 = tuple(f for f in FEATURES_V2 if f not in ("vote", "hyp_share")) + FEATURES_V4[-4:] + ("v_est", "v_est_edited")  # A5
FEATURES_V6 = FEATURES_V5 + ("c_shown", "c_also", "c_maybe")  # A5b: co-edit completion


def _parts(node: str) -> tuple[str, str]:
    """(file path, owning class or '') of a node id 'Kind:path:Qualified.name' (a File node has no name)."""
    kind, _, rest = node.partition(":")
    path, _, qual = rest.partition(":")
    if kind == "Class":
        return path, qual
    return path, qual.rsplit(".", 1)[0] if "." in qual else ""


def restrict_samples(a3: dict[str, Any], keep: int) -> dict[str, Any]:
    """A3 as if only its first `keep` samples had been drawn (amendment A5): hypotheses no kept sample proposed are
    dropped, the rest keep their order. Needs `sample_ids`; merge records are dropped with them."""
    hyps = [{**h, "sample_ids": ids} for h in a3["hypotheses"] if (ids := [k for k in h["sample_ids"] if k < keep])]
    return {**a3, "samples": keep, "hypotheses": hyps, "dropped": []}


def _mentions(name: str, text: str) -> bool:
    return len(name) >= 4 and not name.startswith("__") and re.search(rf"\b{re.escape(name)}\b", text) is not None


def candidates(a3: dict[str, Any], a2: dict[str, Any], issue: str = "", trace: str = "", graph: list[dict] | None = None,
               verifier: dict[str, Any] | None = None, completion: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Function candidates of one A3 run with their features, in Ranked-prior order.

    vote = share of the A3 samples that proposed v as a target. Artifacts written before `sample_ids` existed
    only record merges, so there vote counts proposing hypotheses (1 + merges) over samples, capped at 1:
    it over-counts when one sample targets v in two hypotheses. `issue` is the raw issue text and `trace` the
    stack trace and error messages A1 extracted; they feed the A2-amendment features only. `graph` is the A3R graph
    discovery (amendment A3): its function nodes not already listed are appended at the end, so the prior order of
    the A2/A3 candidates is unchanged, and every row gets one flag per discovery source. `verifier` is the Phase 2
    artifact (amendment A4): whether v was shown, its label and its place in the verifier's top five. `completion`
    (A5b) adds the co-edit decisions about the verifier's first function; its new nodes are appended last."""
    hyps = a3["hypotheses"]
    n_samples = max(1, int(a3.get("samples") or 1))
    merges = Counter(d["reason"].removeprefix("merged into ") for d in a3.get("dropped", []) if d["reason"].startswith("merged into "))
    seeds = [s for s in a2["seeds"] if s["id"].startswith(FUNCTION_KINDS)]
    seed_pos = {s["id"]: i for i, s in enumerate(seeds)}
    top_score = max((s.get("score") or 0.0 for s in seeds), default=0.0) or 1.0
    top_hits = max((len(s.get("hit_by") or []) for s in seeds), default=0) or 1
    by_seed = {s["id"]: s for s in seeds}
    verdict = {s["id"]: s["verdict"] for s in seeds}
    h1_ref = next((a["node"] for a in hyps[0]["anchors"] if a["role"] == "target"), None) if hyps else None
    ref_file, ref_class = _parts(h1_ref) if h1_ref else ("", "")

    order: list[str] = []
    rank: dict[str, int] = {}
    n_hyps: Counter = Counter()
    voters: dict[str, set] = {}
    votes: Counter = Counter()
    anchored: set[str] = set()
    for r, h in enumerate(hyps, 1):
        proposers = h.get("sample_ids")
        for v in dict.fromkeys(a["node"] for a in h["anchors"] if a["role"] == "target" and a["node"].startswith(FUNCTION_KINDS)):
            order.append(v)
            rank.setdefault(v, r)
            n_hyps[v] += 1
            if proposers is None:
                votes[v] += 1 + merges[h["id"]]
            else:
                voters.setdefault(v, set()).update(proposers)
        anchored.update(a["node"] for a in h["anchors"] if a["node"].startswith(FUNCTION_KINDS))
    order += [s["id"] for s in seeds] + sorted(anchored)
    found = {g["node"]: set(g["sources"]) for g in graph or [] if g["node"].startswith(FUNCTION_KINDS)}
    order += list(found)
    order += [n for n in (completion or {}).get("shown", []) if n.startswith(FUNCTION_KINDS)]
    c_shown, c_labels = set((completion or {}).get("shown", [])), (completion or {}).get("labels", {})
    shown = set((verifier or {}).get("shown", []))
    labels = (verifier or {}).get("labels", {})
    v_rank = {n: i for i, n in enumerate((verifier or {}).get("ranking", []))}
    v_est = min((verifier or {}).get("edited_count", 0), 5) / 5

    rows = []
    for v in dict.fromkeys(order):
        path, cls = _parts(v)
        name = v.rsplit(":", 1)[-1].rsplit(".", 1)[-1]
        stem = path.rsplit("/", 1)[-1].removesuffix(".py")
        seed = by_seed.get(v, {})
        vote = len(voters[v]) / n_samples if v in voters else min(1.0, votes[v] / n_samples)
        rows.append({"node": v, "loc": _loc(v), "features": {
            "target_rank_inv": 1 / rank[v] if v in rank else 0.0,
            "in_h1": float(rank.get(v) == 1),
            "hyp_share": n_hyps[v] / len(hyps) if hyps else 0.0,
            "vote": vote,
            "anchor_only": float(v in anchored and v not in rank),
            "seed_relevant": float(verdict.get(v) == "relevant"),
            "seed_maybe": float(verdict.get(v) == "maybe"),
            "seed_rank_inv": 1 / (seed_pos[v] + 1) if v in seed_pos else 0.0,
            "same_file_h1": float(bool(ref_file) and path == ref_file),
            "same_class_h1": float(bool(ref_class) and cls == ref_class),
            "named_in_issue": float(_mentions(name, issue)),
            "class_named": float(bool(cls) and _mentions(cls.rsplit(".", 1)[-1], issue)),
            "file_named": float(path in issue or _mentions(stem, issue)),
            "in_trace": float(_mentions(name, trace)),
            "seed_score": (seed.get("score") or 0.0) / top_score,
            "seed_hits": len(seed.get("hit_by") or []) / top_hits,
            **{f: float(src in found.get(v, ())) for f, src in GRAPH_SOURCES.items()},
            "v_shown": float(v in shown),
            "v_edited": float(labels.get(v) == "edited"),
            "v_maybe": float(labels.get(v) == "maybe"),
            "v_rank_inv": 1 / (v_rank[v] + 1) if v in v_rank else 0.0,
            "v_est": v_est,
            "v_est_edited": v_est * float(labels.get(v) == "edited"),
            "c_shown": float(v in c_shown),
            "c_also": float(c_labels.get(v) == "also"),
            "c_maybe": float(c_labels.get(v) == "maybe"),
        }})
    return rows


def matrix(rows: list[dict[str, Any]], features: tuple[str, ...] = FEATURES) -> np.ndarray:
    return np.array([[r["features"][f] for f in features] for r in rows], dtype=float).reshape(len(rows), len(features))


def fit_logistic(x: np.ndarray, y: np.ndarray, l2: float = 1.0, iters: int = 100) -> np.ndarray:
    """Weights (intercept first) of logistic regression with an L2 penalty on the slopes, by Newton steps."""
    x = np.c_[np.ones(len(x)), x]
    w = np.zeros(x.shape[1])
    penalty = l2 * np.eye(len(w))
    penalty[0, 0] = 0.0
    for _ in range(iters):
        p = 1 / (1 + np.exp(-x @ w))
        step = np.linalg.solve((x.T * (p * (1 - p))) @ x + penalty, x.T @ (p - y) + penalty @ w)
        w -= step
        if np.abs(step).max() < 1e-9:
            break
    return w


def fit_conditional_logit(groups: list[tuple[np.ndarray, np.ndarray]], l2: float = 1.0, iters: int = 100) -> np.ndarray:
    """Weights (no intercept) of a softmax over each instance's candidates, maximising the log-probability of its
    gold candidates (sum over gold), with an L2 penalty; Newton steps. Instances without gold among the
    candidates carry no ranking signal and are skipped."""
    groups = [(x, y) for x, y in groups if y.any()]
    w = np.zeros(groups[0][0].shape[1]) if groups else np.zeros(0)

    def loss(v: np.ndarray) -> float:
        out = 0.5 * l2 * v @ v
        for x, y in groups:
            s = x @ v
            out -= y @ s - y.sum() * (s.max() + math.log(np.exp(s - s.max()).sum()))
        return out

    for _ in range(iters):
        grad, hess = l2 * w, l2 * np.eye(len(w))
        for x, y in groups:
            s = x @ w
            p = np.exp(s - s.max())
            p /= p.sum()
            mu = p @ x
            grad -= y @ x - y.sum() * mu
            hess += y.sum() * ((x.T * p) @ x - np.outer(mu, mu))
        step, now, t = np.linalg.solve(hess, grad), loss(w), 1.0
        while loss(w - t * step) > now and t > 1e-6:  # near-separable data: a full Newton step overshoots
            t /= 2
        w = w - t * step
        if np.abs(t * step).max() < 1e-9:
            break
    return w


def predict(w: np.ndarray, x: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-(np.c_[np.ones(len(x)), x] @ w)))


def _poisson_binomial(ps) -> np.ndarray:
    pmf = np.array([1.0])
    for q in ps:
        pmf = np.convolve(pmf, [1 - q, q])
    return pmf


def expected_f1(p: list[float]) -> list[float]:
    """E[F1] of answering the top k, k = 1..n, for probabilities sorted high to low, assuming independent
    labels and no gold outside the list (unseen gold lowers every k's F1 alike)."""
    n, out = len(p), []
    for k in range(1, n + 1):
        hit, rest = _poisson_binomial(p[:k]), _poisson_binomial(p[k:])
        a, b = np.arange(k + 1)[:, None], np.arange(n - k + 1)[None, :]
        f1 = np.divide(2 * a, k + a + b, out=np.zeros((k + 1, n - k + 1)), where=a > 0)
        out.append(float(hit @ f1 @ rest))
    return out


def expected_f1_prefix(p: list[float]) -> int:
    """Answer size k >= 1 with the largest expected F1 (0 for an empty list)."""
    e = expected_f1(p)
    return int(np.argmax(e)) + 1 if e else 0


def crc_threshold(cal: list[tuple[list[float], list[bool], int]], alpha: float) -> float:
    """Conformal risk control (Angelopoulos et al., ICLR 2024) for loss = 1 - recall of {v: score >= lam}.

    `cal` holds, per calibration instance, its candidate scores, their gold flags and its number of gold
    (gold outside the candidates included, so it counts as a miss). Returns the largest lam with
    n/(n+1) * mean loss + 1/(n+1) <= alpha; -inf when not even all candidates reach it (no guarantee)."""
    n = len(cal)
    for lam in sorted({s for scores, _, _ in cal for s in scores}, reverse=True):
        loss = sum(1 - sum(g for s, g in zip(scores, gold) if s >= lam) / n_gold for scores, gold, n_gold in cal) / n
        if n / (n + 1) * loss + 1 / (n + 1) <= alpha:
            return lam
    return -math.inf


def average_precision(ranked: list[str], gold: set[str], k: int = 10) -> float:
    hits = [i for i, x in enumerate(ranked[:k]) if x in gold]
    return sum((j + 1) / (i + 1) for j, i in enumerate(hits)) / len(gold)


def acc_at(ranked: list[str], gold: set[str], k: int) -> float:
    return float(gold <= set(ranked[:k]))


def reciprocal_rank(ranked: list[str], gold: set[str], k: int = 10) -> float:
    return next((1 / (i + 1) for i, x in enumerate(ranked[:k]) if x in gold), 0.0)


def ndcg(ranked: list[str], gold: set[str], k: int = 10) -> float:
    dcg = sum(1 / math.log2(i + 2) for i, x in enumerate(ranked[:k]) if x in gold)
    return dcg / sum(1 / math.log2(i + 2) for i in range(min(len(gold), k)))


def set_metrics(pred: list[str], gold: set[str]) -> tuple[float, float, float, float]:
    """GraphLocator's SL, REC, PRE, F1 for one instance (empty prediction scores 0)."""
    p = set(pred)
    hit = len(p & gold)
    return (float(hit == len(gold)), hit / len(gold), hit / len(p) if p else 0.0,
            0.0 if not hit else 2 / (len(p) / hit + len(gold) / hit))


def brier(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2))


def ece(p: np.ndarray, y: np.ndarray, bins: int = 10) -> float:
    idx = np.minimum((p * bins).astype(int), bins - 1)
    return float(sum(abs(p[idx == b].mean() - y[idx == b].mean()) * (idx == b).mean() for b in range(bins) if (idx == b).any()))


def load_calibrator(path: Path = CALIBRATOR) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def decide(rows: list[dict[str, Any]], calibrator: dict[str, Any]) -> tuple[list[tuple[str, float]], int]:
    """(node, probability) high to low under the frozen calibrator, and how many of them to answer (expected-F1 prefix)."""
    p = predict(np.array(calibrator["weights"]), matrix(rows, tuple(calibrator["features"])))
    ranked = [(rows[i]["node"], float(p[i])) for i in np.argsort(-p, kind="stable")]
    return ranked, expected_f1_prefix([q for _, q in ranked])
