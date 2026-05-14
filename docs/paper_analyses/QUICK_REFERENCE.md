# Code Knowledge Graphs: Quick Reference Guide

## At-a-Glance Summary

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CODE KNOWLEDGE GRAPH LANDSCAPE                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    GRAPH CONSTRUCTION PATTERNS                      │   │
│  ├─────────────┬─────────────┬────────────────┬────────────────────────┤   │
│  │ Static AST  │ Dynamic     │ LLM-Enhanced   │ Hybrid                  │   │
│  │ (All papers)│ (2511 only) │ (2505, 2304)   │ (2511, 2603.21430)      │   │
│  │ Fast,       │ Runtime     │ Semantic       │ Best accuracy           │   │
│  │ reliable    │ behavior    │ intent         │ Complex                 │   │
│  └─────────────┴─────────────┴────────────────┴────────────────────────┘   │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    RETRIEVAL STRATEGIES (Best to Worst)             │   │
│  ├──────────────┬─────────────┬──────────────┬─────────────────────────┤   │
│  │ SMT-guided   │ Path-guided │ Hybrid search│ Graph query (LLM)       │   │
│  │ generation   │ (multi-hop) │ (text+vec+gr)│ (51% precision)         │   │
│  │ (2511)       │ (2503)      │ (2505)       │ (2408)                  │   │
│  │ -52% errors  │ 89.7% need  │ Baseline     │ Needs improvement       │   │
│  │ +15.6% Pass@1│ multi-hop   │              │                         │   │
│  └──────────────┴─────────────┴──────────────┴─────────────────────────┘   │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    PERFORMANCE BY APPLICATION                       │   │
│  ├─────────────────────┬─────────────┬──────────────────────────────────┤   │
│  │ Generation          │ 33-50% Pass│ 2505 (36%), 2511 (50%)           │   │
│  │ Repair              │ 58%        │ 2503 (KGCompass)                 │   │
│  │ Test Reproduction   │ 66%        │ 2603.07326 (Echo)                │   │
│  │ Completion          │ +6 match   │ 2406 (GraphCoder)                │   │
│  │ Fuzzing             │ +9% cov    │ 2411 (CKGFuzzer)                 │   │
│  │ Domain Adaptation   │ 67%        │ 2603.21430 (DomAgent)            │   │
│  └─────────────────────┴─────────────┴──────────────────────────────────┘   │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    KEY INSIGHTS (Evidence-Based)                   │   │
│  ├──────────────────────────────────────────────────────────────────────┤   │
│  │ 1. Multi-hop is critical: 89.7% of repair successes need it        │   │
│  │ 2. Constraint integration beats post-hoc validation: -52% errors   │   │
│  │ 3. KG + retrieval: 15-50% gains on complex tasks                   │   │
│  │ 4. Context matters: Big gains on repo tasks, small on HumanEval    │   │
│  │ 5. Dual analysis: Static+dynamic = +7.3% (2511.07584)              │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Paper Decision Matrix

```
Which paper should I read/implement for my needs?

┌─────────────────────┬─────────────────────┬─────────────────────────────┐
│ Need:              │ Read First:         │ Implementation Complexity:  │
├─────────────────────┼─────────────────────┼─────────────────────────────┤
│ General overview   │ SYNTHESIS_MASTER    │ N/A                         │
│ Benchmark problems │ 2404.00599, 2310    │ N/A                         │
│                     │                     │                             │
│ Code generation    │ 2505.14394          │ ◐◐◐ (Medium)                │
│                     │ then 2511.07584     │ ◐◐◐◐◐ (High - SMT)          │
│                     │                     │                             │
│ Code completion    │ 2406.07003          │ ◐◐ (Medium-Low)             │
│                     │                     │                             │
│ Bug repair         │ 2503.21710          │ ◐◐◐ (Medium-High)           │
│                     │                     │                             │
│ Test generation    │ 2603.07326          │ ◐◐◐ (Medium)                │
│                     │                     │                             │
│ Fuzzing            │ 2411.11532          │ ◐◐◐◐ (High - multi-agent)   │
│                     │                     │                             │
│ Domain adaptation  │ 2603.21430          │ ◐◐◐ (Medium-High)           │
│                     │                     │                             │
│ KG construction    │ 2304.09048          │ ◐◐ (Low-Medium)             │
│                     │                     │                             │
│ Graph interface    │ 2408.03910          │ ◐◐◐ (Medium)                │
└─────────────────────┴─────────────────────┴─────────────────────────────┘

Complexity: ◐ Low ◐◐ Medium ◐◐◐ Medium-High ◐◐◐◐ High ◐◐◐◐◐ Very High
```

---

## Schema Quick Reference

### Minimal Viable Schema (for any code KG)

```cypher
// Nodes
(:File {path, language})
(:Class {name, signature, file})
(:Function {name, signature, file})
(:Method {name, signature, class, file})
(:Attribute {name, type, owner})  // owner = class or function

// Edges
(:File)-[:CONTAINS]->(:Class|:Function)
(:Class)-[:CONTAINS]->(:Method)
(:Class)-[:INHERITS]->(:Class)
(:Function)-[:CALLS]->(:Function)
(:Statement)-[:USES]->(:Variable|:Function)
(:Function)-[:HAS_PARAM]->(:Parameter)
```

### Repair-Specific Extensions

```cypher
(:Issue {id, title, description, created_at})
(:PR {id, title, description, created_at})
(:Issue)-[:MENTIONS]->(:File|:Function)
(:PR)-[:FIXES]->(:Issue)
(:PR)-[:MODIFIES]->(:File|:Function)
(:Test)-[:VERIFIES]->(:Function)
```

### Fuzzing-Specific Extensions

```cypher
(:APIGroup {name, library})
(:APICombination {id, confidence})
(:APICombination)-[:INCLUDES]->(:Function)
(:Function)-[:READS]->(:Variable)
(:Function)-[:WRITES]->(:Variable)
(:Function)-[:ALLOCATES]->(:Resource)
(:Function)-[:INITIALIZES]->(:Object)
```

### Domain-Specific Extensions

```cypher
(:Package {name, domain})
(:DomainConcept {name, description})
(:Concept)-[:RELATED_TO]->(:Function)
(:Example)-[:DEMONSTRATES]->(:Pattern)
(:Pattern)-[:INVOLVES]->(:Function)
```

---

## Implementation Checklist

### Phase 1: Foundation (Week 1-2)
- [ ] Choose graph database (Neo4j recommended for prototyping)
- [ ] Define schema for your task
- [ ] Implement AST parser for target language
- [ ] Extract basic entities (files, classes, functions)
- [ ] Build initial graph for test repository

### Phase 2: Enhancement (Week 3-4)
- [ ] Add dependency edges (CALLS, USES, IMPORTS)
- [ ] Generate embeddings (use MiniLM or similar)
- [ ] Implement n-hop traversal with decay-weighting
- [ ] Add full-text search indexes
- [ ] Test retrieval quality manually

### Phase 3: LLM Integration (Week 5-6)
- [ ] Format subgraph as LLM-friendly text
- [ ] Design prompt template
- [ ] Implement retrieval-augmented generation
- [ ] Evaluate on small benchmark
- [ ] Iterate on prompt design

### Phase 4: Task-Specific Features (Week 7-8)
- [ ] Add task-specific nodes/edges (see above)
- [ ] Implement constraint checking if needed
- [ ] Add execution/validation loop if repair/testing
- [ ] Performance optimization (caching, indexing)
- [ ] Cost analysis

### Phase 5: Evaluation (Week 9-10)
- [ ] Choose appropriate benchmark
- [ ] Run baseline comparisons
- [ ] Ablation studies (with/without KG, with/without n-hop)
- [ ] Error analysis
- [ ] Document results

---

## Common Pitfalls & Solutions

| Pitfall | Symptom | Solution |
|---------|---------|----------|
| **Schema too sparse** | KG misses important relationships | Add more edge types, analyze failed cases |
| **Schema too dense** | LLM overwhelmed, slow queries | Prune low-value edges, limit n-hop |
| **Retrieval too broad** | Context length exceeded | Lower top-k, increase similarity threshold |
| **Retrieval too narrow** | Missing needed context | Decrease threshold, increase hops, hybrid search |
| **LLM ignores KG** | Generated code doesn't use provided context | Improve prompt, add "use these APIs" instructions |
| **Stale KG** | Code changed, KG outdated | Incremental updates, rebuild on commit |
| **Noisy KG** | Many false CALLS/USES edges | Improve static analysis, type-based filtering |
| **High latency** | Retrieval takes >5s | Better indexing, caching, pre-computation |

---

## Performance Expectations

Based on paper results, expect these **relative improvements** over baseline (no KG):

| Task Complexity | Expected Gain | Caveats |
|-----------------|---------------|---------|
| **Simple** (standalone function) | 5-10% | Context matters less |
| **Moderate** (cross-file, 2-3 dependencies) | 15-25% | Need good retrieval |
| **Complex** (repo-scale, many deps) | 30-50% | Multi-hop essential |
| **Repair** (fault localization) | 40-60% | Artifact linkage critical |
| **Domain-specific** | 20-40% | KG must capture domain |

**Cost**: ~2-5 seconds additional latency per query (graph traversal + LLM). Acceptable for most applications.

**Infrastructure**: Neo4j instance ($0-$500/month depending on scale), embedding model (free or $), LLM API ($0.001-0.05/query).

---

## Benchmark Selection Guide

```
Which benchmark should I use to evaluate my KG system?

┌─────────────────────────────────────────────────────────────────────────┐
│ Benchmark          │ Task Type       │ Size  │ Difficulty │ Use When:       │
├────────────────────┼─────────────────┼───────┼────────────┼─────────────────┤
│ HumanEval          │ Standalone      │ 164   │ Easy       │ Baseline LLM    │
│ MBPP               │ Standalone      │ 974   │ Easy-Medium│ Simple gen      │
├────────────────────┼─────────────────┼───────┼────────────┼─────────────────┤
│ EvoCodeBench       │ Repo generation │ 275   │ Hard       │ Realistic repo  │
│ RepoEval           │ Cross-file comp │ Varies│ Hard       │ Completion      │
├────────────────────┼─────────────────┼───────┼────────────┼─────────────────┤
│ SWE-Bench Lite     │ Issue repair    │ 300   │ Very Hard  │ Repair          │
│ SWT-Bench          │ Test gen        │ ~500  │ Hard       │ Reproduction    │
├────────────────────┼─────────────────┼───────┼────────────┼─────────────────┤
│ DS-1000            │ Domain (data sci│ 1000  │ Medium     │ Domain adapt    │
│ └─ subcategories   │ specific)       │       │            │                 │
├────────────────────┼─────────────────┼───────┼────────────┼─────────────────┤
│ Custom             │ Your task        │ Any   │ Your task  │ Specific domain │
└────────────────────┴─────────────────┴───────┴────────────┴─────────────────┘

Recommendation: Start with EvoCodeBench (generation) or SWE-Bench Lite (repair).
```

---

## Glossary

**KG**: Knowledge Graph - nodes (entities) connected by edges (relationships)

**n-hop**: Traversing n edges from starting node. 1-hop = direct neighbors, 2-hop = neighbors-of-neighbors

**Pass@k**: Probability that at least one of k generated samples passes all tests

**RAG**: Retrieval-Augmented Generation - fetch external context, inject into LLM prompt

**SMT**: Satisfiability Modulo Theories - mathematical solver for constraints

**CCG**: Code Context Graph (GraphCoder) - CFG + DDG + CDG superimposed

**AST**: Abstract Syntax Tree - tree representation of code structure

**CFG**: Control Flow Graph - possible execution paths

**DDG**: Data Dependence Graph - variable definition-use relationships

**CDG**: Control Dependence Graph - which conditions affect which statements

**Embedding**: Vector representation of text/code for similarity search

**Decay-weighting**: Distant context gets lower weight (e.g., exp(-λ×distance))

**Dual-version validation**: Test must fail on buggy code, pass on patched code

**Fail-to-pass**: Same test changes from fail to pass after fix

**Entity path**: Multi-hop chain linking entities (issue → PR → function)

**Schema**: Definition of node types and edge types in KG

**Provenance**: Tracking where information came from (important for KG)

---

## Citation Quick Reference

```bibtex
@inproceedings{2404.00599,
  title={EvoCodeBench: An Evolving Code Generation Benchmark},
  author={Li, Jia and Li, Ge and Zhang, Xuanming and Dong, Yihong and Jin, Zhi},
  year={2024},
  booktitle={ICLR}
}

@inproceedings{2511.07584,
  title={SemanticForge: Dual Static-Dynamic Knowledge Graphs},
  author={Zhang, Wuyang and Zhang, Chenkai and Luo, Zhen and Ma, Jianming and others},
  year={2025},
  booktitle={JEAAI}
}

@inproceedings{2503.21710,
  title={KGCompass: Repository-Aware Knowledge Graphs for Repair},
  author={Yang, Boyang and Ren, Jiadong and Jin, Shunfu and Liu, Yang and others},
  year={2025},
  booktitle={ACM Conference}
}

@inproceedings{2406.07003,
  title={GraphCoder: Code Context Graph for Completion},
  author={Liu, Wei and Yu, Ailun and Zan, Daoguang and Shen, Bo and Wang, Qianxiang and others},
  year={2024}
}

@article{2603.21430,
  title={DomAgent: KG + Case-Based Reasoning for Domain Code},
  author={Wang, Shuai and Parthasarathy, Dhasarathy and Feldt, Robert and Yu, Yinan},
  year={2026},
  journal={AAMAS}
}
```

---

**Last Updated**: April 2025  
**Papers Covered**: 11  
**Pages**: This quick reference + 11 detailed analyses + 1 synthesis

For detailed analysis, see individual markdown files in `paper_analyses/` directory.
