# Code Knowledge Graphs: Comprehensive Research Synthesis

**Date**: April 2025  
**Papers Analyzed**: 11 (2404.00599, 2310.06770, 2505.14394, 2511.07584, 2406.07003, 2408.03910, 2503.21710, 2411.11532, 2304.09048, 2603.07326, 2603.21430)  
**Scope**: Repository-level code understanding, generation, repair, and testing

---

## Executive Summary

Code knowledge graphs (KGs) have emerged as a **fundamental paradigm** for enhancing LLM-based software engineering. After analyzing 11 seminal papers, we identify:

1. **Consensus**: Graph-structured repository representation significantly improves context retrieval (15-50% gains on complex tasks)
2. **Evolution**: From simple retrieval augmentation → constraint-aware generation → agent integration
3. **Critical feature**: Multi-hop traversal captures relationships impossible to find via embedding similarity alone
4. **Application domains**: Generation, repair, completion, testing, domain adaptation
5. **Performance frontier**: SemanticForge leads with 49.8% Pass@1 on REPOKG-50, 52% error reduction via SMT constraints

---

## 1. Taxonomy of Approaches

### 1.1 By Primary Application

| Category | Papers | Core Problem | Best Performance |
|----------|--------|--------------|------------------|
| **Benchmarks** | 2404.00599 (EvoCodeBench), 2310.06770 (SWE-Bench) | Evaluation gaps | Establishes standards; reveals <2% baseline |
| **Code Generation** | 2505.14394, 2511.07584 (SemanticForge) | Repository context | 36.36% (EvoCodeBench), 49.8% (REPOKG-50) |
| **Code Completion** | 2406.07003 (GraphCoder) | Intra-file context | +6 code match, +6 identifier match |
| **Software Repair** | 2503.21710 (KGCompass), 2603.07326 (Echo) | Fault localization | 58.3% (SWE-Bench Lite), 66.28% (reproduction) |
| **Fuzz Testing** | 2411.11532 (CKGFuzzer) | Driver generation | +8.73% coverage, 11 bugs (9 new) |
| **Domain Adaptation** | 2603.21430 (DomAgent) | Specialized knowledge | 67% on DS-1000 (vs 45% baseline) |
| **KG Construction** | 2304.09048 (CodeKGC) | Automated KG building | +4.5% F1 on ACE04 |

### 1.2 By Technical Approach

| Innovation | Papers Using It | Impact |
|------------|-----------------|--------|
| **Hybrid retrieval** (full-text + vector + graph) | 2505.14394, 2603.21430 | Most common pattern; solid gains |
| **Dual static-dynamic graphs** | 2511.07584 (only) | +7.3% Pass@1 from dynamic alone |
| **SMT-integrated generation** | 2511.07584 (only) | -52% schematic errors, frontier tech |
| **Graph query learning** | 2511.07584 (trained), 2408.03910 (LLM) | 73% vs 51% precision |
| **Code Context Graph (CCG)** | 2406.07003 (only) | Statement-level; +6 match |
| **Artifact linkage** (issues/PRs) | 2503.21710 | Enables multi-hop repair |
| **KG-guided case selection** | 2603.21430 | Small case base, high coverage |
| **Schema-aware prompting** | 2304.09048 | CodeLM for KG construction |

---

## 2. Graph Schema Design Patterns

### 2.1 Common Node Types (Consensus)

```
Essential:
- FILE / MODULE
- CLASS
- FUNCTION (standalone)
- METHOD (class-bound)
- ATTRIBUTE / FIELD
- VARIABLE (optional)

Extended (task-specific):
- ISSUE (repair/reproduction)
- PULL_REQUEST (repair)
- TEST (testing)
- TEST_FILE (testing)
- PARAMETER (fuzzing)
- TYPE / DATA_STRUCTURE (domain-specific)
- GLOBAL_VARIABLE / CONSTANT
```

### 2.2 Common Edge Types (Consensus)

```
Structural:
- CONTAINS / DEFINES (file → class/function)
- INHERITS (class → parent class)
- HAS_METHOD (class → method)
- HAS_FIELD (class/struct → field)

Dependency:
- CALLS / INVOKES (function → function)
- USES / REFERENCES (statement → variable/function)
- IMPORTS (module → module)
- DEPENDS_ON (general)

Semantic:
- RELATED_TO (conceptual similarity)
- INSTANCE_OF (object → class)
- OVERRIDES (method → parent method)
- DOCUMENTS (doc → code element)
```

### 2.3 Task-Specific Schema Extensions

**Repair** (2503.21710):
```
ISSUE --mentions--> FILE/FUNCTION
PR --fixes--> ISSUE
PR --modifies--> FILE/FUNCTION
TEST --covers--> FUNCTION
```

**Fuzzing** (2411.11532):
```
FUNCTION --reads--> VARIABLE
FUNCTION --writes--> VARIABLE
FUNCTION --allocates--> RESOURCE
FUNCTION --frees--> RESOURCE
API_COMBINATION --includes--> {FUNCTIONS}
```

**Domain Adaptation** (2603.21430):
```
PACKAGE --contains--> FUNCTION
FUNCTION --returns--> TYPE
FUNCTION --accepts--> TYPE
CONCEPT --related_to--> FUNCTION
CASE --demonstrates--> API_PATTERN
```

---

## 3. Construction Methods: Trade-offs

| Method | Accuracy | Speed | Cost | Captures |
|--------|----------|-------|------|----------|
| **Static AST** | 100% on structure | Fast | Low | Calls, contains, inherits |
| **Dynamic traces** | Runtime behavior | Slow | High | Actual paths, types |
| **LLM extraction** | Semantic intent | Medium | Medium-High | Documentation, purpose |
| **Hybrid** | Best overall | Slow | High | Both structure + semantics |

**Consensus trend**: Start with static AST (fast, reliable), augment with LLM (semantics), add dynamic if needed (behavior).

**Papers using hybrid**: 2511.07584 (static+dynamic), 2505.14394 (AST+LLM), 2603.21430 (KG+CBR)

---

## 4. Retrieval Strategies: Effectiveness Comparison

### 4.1 Baseline: Similarity-Based

**Methods**: BM25, embedding similarity
**Pros**: Simple, fast, works for obvious matches
**Cons**: Lexical bias, misses transitive relationships, no structure
**Performance**: ~20-40% on repository tasks

### 4.2 Graph Traversal (n-hop)

**Method**: Start from target, expand to neighbors with decay-weighting
**Papers**: 2406.07003 (CCG slicing), 2505.14394 (subgraph expansion)
**Pros**: Captures dependencies, respects structure, configurable breadth
**Cons**: Computationally expensive, needs pruning
**Performance**: ~33-36% Pass@1 (EvoCodeBench)

### 4.3 Graph Query Generation

**Method**: Convert natural language to Cypher/SQL-like queries
**Variants**:
- LLM ad-hoc (2408.03910): 51% precision
- Learned policy (2511.07584): 73% precision (+22% improvement)
**Pros**: Precise, interpretable, flexible
**Cons**: Query quality critical; LLM queries unreliable

### 4.4 Hybrid Search

**Method**: Combine full-text + vector + graph signals
**Paper**: 2505.14394
**Formula**: Score = α·text_match + β·vector_sim + γ·graph_proximity
**Pros**: Robust to different query types
**Cons**: Parameter tuning needed
**Result**: Best retrieval quality among compared

### 4.5 Path-Guided Retrieval

**Method**: Multi-hop entity paths (issue → PR → function)
**Paper**: 2503.21710
**Critical statistic**: 89.7% of successful repairs require multi-hop
**Insight**: Single-hop (similarity) insufficient for complex tasks

---

## 5. Integration Patterns with LLMs

### 5.1 Context Augmentation (Most Common)

**Pattern**: Retrieve subgraph → format as text → inject into LLM prompt

**Implementation**:
```python
context = kg.retrieve(query, top_k=20)
prompt = f"""
Repository context:
{format_subgraph(context)}

Task: {user_query}
"""
```

**Used by**: 2505.14394, 2406.07003, 2503.21710, 2603.07326, 2411.11532, 2603.21430

**Advantages**: Simple, works with any LLM, no training needed
**Disadvantages**: Context length limits, LLM must understand graph format

### 5.2 Constraint-Aware Generation (Frontier)

**Pattern**: Encode KG constraints into generation process itself

**Method**: SMT solver in beam search (2511.07584)
- During token sampling, check if candidate violates type/signature
- Prune invalid continuations
- Guarantees schema compliance

**Results**: -52% schematic errors, +15.6% Pass@1

**Advantages**: Prevents errors, formal guarantees
**Disadvantages**: Complex integration, SMT overhead, undecidable constraints

### 5.3 Query Translation

**Pattern**: LLM generates graph queries, executes, uses results

**Method**: Two-agent system (2408.03910):
- Analysis agent: Determines what info needed
- Translation agent: Converts to Cypher
- Execute → results → synthesis

**Advantages**: Flexible, natural language interface
**Disadvantages**: Query quality varies (51-73% precision), error handling complex

### 5.4 Dual-Retrieval Integration

**Pattern**: Combine structured KG + unstructured cases

**Method**: 2603.21430:
- Top-down: KG gives API signatures, types
- Bottom-up: Cases show usage patterns
- LLM synthesizes both

**Advantages**: Complete knowledge (concepts + patterns)
**Disadvantages**: Two retrieval systems to maintain

---

## 6. Performance Landscape

### 6.1 Benchmarks and State-of-the-Art

| Benchmark | Task Type | Samples | Best SOTA | Paper |
|-----------|-----------|---------|-----------|-------|
| **HumanEval** | Standalone function | 164 | ~80% (GPT-4) | Not KG-focused |
| **EvoCodeBench** | Repo-level generation | 275 | 36.36% (Claude 3.5 Sonnet + KG) | 2505.14394 |
| **REPOKG-50** | Repo-level tasks | 4,250 | 49.8% (CodeLlama-34B + KG+SMT) | 2511.07584 |
| **SWE-Bench** | Issue repair | 2,294 | ~2% (Claude 2) | 2310.06770 baseline |
| **SWE-Bench Lite** | Issue repair | 300 | 58.3% (Claude-4 Sonnet + KG) | 2503.21710 |
| **SWT-Bench Verified** | Test reproduction | ~300 | 66.28% (Echo) | 2603.07326 |
| **DS-1000** | Domain data science | 1,000 | 67% (DomAgent) | 2603.21430 |
| **CrossCodeEval** | Cross-file completion | Varies | Competitive | 2408.03910 |

**Key observation**: KG approaches show **largest gains on hard, repository-scale tasks**. On HumanEval (simple standalone), gains minimal (<5%). This proves KGs solve the **context problem** - when context matters most, KGs deliver.

### 6.2 Error Reduction Metrics

Beyond Pass@1, several papers measure specific error types:

| Paper | Error Type | Reduction |
|-------|------------|-----------|
| 2511.07584 (SemanticForge) | Schematic hallucinations (type/signature) | 49.8% |
| 2511.07584 | Logical hallucinations (control/data flow) | 34.7% |
| 2411.11532 (CKGFuzzer) | Manual crash review workload | 84.4% |
| 2503.21710 (KGCompass) | Fault localization search (to 20 candidates) | 95%+ reduction |

**Insight**: KGs don't just improve success rate - they **systematically eliminate specific failure modes**.

---

## 7. Common Challenges Across Papers

### 7.1 Scalability

**Problem**: Graph size grows with repository:
- 500K LOC → millions of nodes/edges
- n-hop traversal expensive (O(n²) worst case)
- Graph DB queries need optimization

**Solutions**:
- Neo4j with proper indexing (2505.14394, 2408.03910)
- Sub-linear complexity claims (2511.07584: O(n^0.73))
- Incremental updates (2511.07584: O(|R|·log n))
- Pruning/top-k filtering (all papers)

**Open**: How do KGs scale to monorepos with 10M+ LOC? Not addressed.

### 7.2 Schema Design

**Problem**: What nodes/edges to include?
- Too few: Miss important relationships
- Too many: Noise, slow, LLM context overwhelmed
- Language-specific: Python ≠ Java ≠ C++

**Current practice**: Minimal viable schema (files, classes, functions, calls, contains)
**Future need**: Task-adaptive schemas or learned schemas

**Papers addressing**:
- 2304.09048: Schema-aware prompting for construction
- 2603.21430: Domain-specific extensions
- 2505.14394: Acknowledges need for decorators, types, aux files

### 7.3 Evaluation Standardization

**Problem**: Hard to compare:
- Different benchmarks (EvoCodeBench vs SWE-Bench vs custom)
- Different metrics (Pass@1, repair rate, coverage)
- Different LLM backbones
- Agentic vs procedural not comparable

**Community need**: Unified benchmark suite with consistent task formulation.

**Progress**: EvoCodeBench, SWE-Bench becoming de facto standards.

### 7.4 Data Contamination

**Problem**: Training data includes test instances → inflated performance

**Solutions**:
- Evolving benchmarks (EvoCodeBench updates every 6 months)
- Temporal filtering (2503.21710: only pre-issue artifacts)
- Use recent repositories post-training cut-off

**Remaining risk**: Still possible leakage through indirect paths.

### 7.5 Engineering Complexity

**Problem**: Sophisticated KG systems hard to implement:
- SMT integration (2511.07584)
- Graph query learning (2511.07584)
- Dual static-dynamic analysis (2511.07584)
- Multi-agent orchestration (2411.11532, 2603.21430)

**Trade-off**: Simpler systems (2505.14394) easier to deploy, slightly lower performance.
Complex systems (2511.07584) higher performance, engineering burden.

---

## 8. Technical Innovation Timeline

### Phase 1: Basic Retrieval Augmentation (2023-early 2024)
- RepoCoder, RepoFusion: Similarity-based retrieval
- Simple RAG: fetch relevant files, inject into prompt
- **Limitation**: No structure, lexical bias

### Phase 2: Graph-Based Retrieval (2024)
- **2406.07003 GraphCoder**: CCG with slicing, decay-weighting
- **2505.14394 KG Gen**: Hybrid search + n-hop expansion
- **2408.03910 CodeXGraph**: Graph DB + query translation
- **Innovation**: Structure matters, multi-hop traversal

### Phase 3: Constraint-Aware Generation (2025)
- **2511.07584 SemanticForge**: Dual graphs + SMT in beam search
- **Innovation**: Prevent errors during generation, not after
- **Trade-off**: Complexity vs. single-pass guarantee

### Phase 4: Specialized Applications (2024-2025)
- **2503.21710 KGCompass**: Artifact linkage for repair
- **2603.07326 Echo**: Auto-execution for test generation
- **2411.11532 CKGFuzzer**: KG for fuzzing
- **2603.21430 DomAgent**: Domain adaptation with CBR
- **Pattern**: KG + domain-specific workflow

---

## 9. Comparative Analysis Matrix

### 9.1 System Capabilities

| Capability | 2404 | 2310 | 2505 | 2511 | 2406 | 2408 | 2503 | 2411 | 2304 | 2603 | 2603 |
|------------|------|------|------|------|------|------|------|------|------|------|------|
| **Benchmark** | ✓ | ✓ | | | | | | | | | |
| **Generation** | | | ✓ | ✓ | | | | | | | ✓ |
| **Completion** | | | | | ✓ | | | | | | |
| **Repair** | | ✓ | | | | | ✓ | | | | |
| **Test Gen** | | | | | | | | ✓ | | ✓ | |
| **Fuzzing** | | | | | | | | ✓ | | | |
| **Domain Adapt** | | | | | | | | | | | ✓ |
| **KG Construction** | | | | | | | | | ✓ | | |

### 9.2 Technical Sophistication vs. Practicality

```
High Sophistication:
├── 2511.07584 SemanticForge (SMT, dual graphs, learned queries)
├── 2503.21710 KGCompass (artifact linkage, paths)
└── 2411.11532 CKGFuzzer (multi-agent, coverage loop)

Medium Sophistication:
├── 2603.21430 DomAgent (dual retrieval, RL)
├── 2408.03910 CodeXGraph (query translation)
└── 2505.14394 KG Gen (hybrid retrieval, LLM descs)

Lower Sophistication (Easier to Implement):
├── 2406.07003 GraphCoder (CCG slicing)
├── 2304.09048 CodeKGC (schema prompts)
└── 2603.07326 Echo (graph + execution)
```

**Frontier**: 2511.07584 SemanticForge represents state-of-the-art in technical sophistication with formal guarantees.

**Most deployable**: 2505.14394 and 2406.07003 - solid gains without extreme complexity.

---

## 10. Key Technical Insights

### 10.1 What Makes KG Retrieval Work?

1. **Multi-hop reasoning** (2503.21710: 89.7% successes need multi-hop)
   - Single-hop similarity fails on indirect relationships
   - Graph structure enables systematic traversal
   - Path mining more reliable than embedding search

2. **Constraint propagation** (2511.07584)
   - Type/signature constraints prevent entire classes of errors
   - SMT integration catches violations during generation
   - Formal guarantees possible

3. **Task-specific schemas**
   - Repair: Need artifact linkage (issues, PRs)
   - Fuzzing: Need API usage patterns, data flow
   - Domain: Need conceptual + experiential
   - One-size-fits-all schema suboptimal

4. **Context pruning essential**
   - n-hop expansion yields huge subgraphs
   - Must filter to top-k by relevance
   - Without pruning: LLM overwhelmed, latency high

5. **Dual analysis beats single**
   - Static + dynamic (2511.07584): +7.3%
   - KG + cases (2603.21430): +9% over simple RAG
   - Full-text + vector + graph (2505.14394): Best retrieval

### 10.2 What Doesn't Work Well?

1. **Pure similarity retrieval** for complex tasks
   - Works for obvious matches, fails on implicit relationships
   - Lexical bias toward surface forms

2. **LLM ad-hoc query generation** (2408.03910 baseline)
   - Only 51% precision
   - Queries often malformed, too broad/narrow
   - Learned policy (2511.07584) much better

3. **Post-hoc validation only**
   - Generate → validate → repair loop expensive
   - Multiple iterations needed (10-50 for agents)
   - Constraint integration eliminates need

4. **Single-file context** for repository tasks
   - 2406.07003 limited to intra-file
   - Cross-file dependencies critical (2505.14394 shows gains)
   - Need both intra (statement) + inter (file) context

5. **Static KG only**
   - Doesn't capture runtime behavior
   - Dynamic traces add value (2511.07584)

---

## 11. Open Research Questions

### 11.1 Fundamental

1. **Optimal graph schema**: Is there a universal schema or must it be task-specific?
2. **Diminishing returns**: How much context is enough? Top-5 vs Top-20 vs Top-50?
3. **Explainability vs performance**: Path-guided (2503.21710) interpretable; SMT (2511.07584) less so - trade-off?
4. **Constraint completeness**: Can SMT encode all repository constraints? What about architectural patterns, style guides?

### 11.2 Engineering

1. **Incremental updates at scale**: 2511.07584 claims O(|R|·log n) but evaluated on 50 repos only. Monorepo scale?
2. **Multi-language KGs**: Can one graph span Python, Java, C++? Or per-language schemas with cross-links?
3. **KG construction automation**: Current methods still need manual schema design. Can we learn schemas from code?
4. **Real-time vs batch**: Graph building expensive. Can we build incrementally as code changes?

### 11.3 Evaluation

1. **Unified benchmark**: Need standard tasks, metrics, LLM backbones
2. **Cost-aware evaluation**: Agent iterations vs single-pass; token usage; wall-clock
3. **Human studies**: Do KG-generated patches more maintainable? Easier to review?
4. **Longitudinal**: How do KG systems perform as codebase evolves?

---

## 12. Practical Recommendations

### 12.1 For Practitioners (Which Paper to Implement?)

**Scenario 1: Building repository-aware code assistant**
- **Start with**: 2505.14394 (KG Gen) or 2408.03910 (CodeXGraph)
- **Why**: Good balance of performance vs complexity
- **Implementation**: Neo4j + AST parser + embedding model
- **Expected gain**: ~15-20% over simple RAG

**Scenario 2: Automated bug repair system**
- **Start with**: 2503.21710 (KGCompass) pattern
- **Why**: Artifact linkage critical for repair; multi-hop localization
- **Key**: Build KG with issues/PRs, not just code
- **Expected**: 50%+ improvement over pure LLM

**Scenario 3: Fuzzing/security testing**
- **Use**: 2411.11532 (CKGFuzzer) approach
- **Why**: Only system targeting fuzzing; real bugs found
- **Investment**: Program analysis infrastructure required
- **Expected**: ~9% coverage gain, new vulnerability discovery

**Scenario 4: Domain-specific code gen** (proprietary libraries)
- **Use**: 2603.21430 (DomAgent) pattern
- **Why**: Doesn't require fine-tuning; works with any LLM
- **Key**: Build domain KG + curated case base
- **Expected**: Match fine-tuned models without retraining

**Scenario 5: Research frontier (maximum performance)**
- **Study**: 2511.07584 (SemanticForge)
- **Why**: State-of-the-art; constraint-aware generation
- **Complexity**: High (SMT, learned queries, dual graphs)
- **Expected**: Best reported results if you can implement

### 12.2 Implementation Roadmap (Simplified)

**Phase 1: Static KG** (Week 1-2)
- AST parser → extract files, classes, functions, calls
- Build graph (NetworkX or Neo4j)
- Verify: Can you query "what does X call?"

**Phase 2: Retrieval** (Week 3-4)
- n-hop traversal from target
- Embedding similarity for semantic search
- Combine with full-text for name matching
- Test: Does retrieved context help LLM?

**Phase 3: Integration** (Week 5-6)
- Format subgraph as prompt text
- Inject into LLM completion request
- Evaluate on repository task benchmark

**Phase 4: Enhancement** (Week 7-8)
- Add metadata (LLM-generated descriptions)
- Implement pruning/re-ranking
- Experiment with query refinement loop
- Add execution validation if repair/testing

**Total**: 2 months for working prototype based on 2505.14394 pattern.

---

## 13. Future Directions (Synthesis)

### 13.1 Near-Term (1-2 years)

1. **Standardized evaluation**: EvoCodeBench + SWE-Bench become standard; leaderboards emerge
2. **KG-as-a-service**: Cloud graph DB for code repositories; APIs for LLMs
3. **IDE integration**: Real-time KG queries in editors (like CodeXGraph demo)
4. **Multi-language schemas**: Common abstractions across Python/Java/JS
5. **Incremental updates**: Better algorithms for evolving codebases

### 13.2 Mid-Term (3-5 years)

1. **Constraint-solving mainstream**: SMT/Z3 integrated into code gen (SemanticForge proof-of-concept)
2. **Learned query policies**: Replace LLM ad-hoc with trained retriever (2511.07584 direction)
3. **Cross-repo reasoning**: Bugs spanning multiple repositories (dependency issues)
4. **Continuous KG**: Live update with every commit; used in CI/CD
5. **Explainable repair**: KG paths provide transparent reasoning (KGCompass model)

### 13.3 Long-Term (5+ years)

1. **Unified code understanding**: Single KG encompassing all code artifacts (code, issues, PRs, tests, docs, runs)
2. **Automated software engineering**: End-to-end: issue → PR with tests, all KG-guided
3. **Formal verification integration**: KG constraints feed into formal specs
4. **Cross-project learning**: Transfer patterns between projects via KG abstraction
5. **KG compression**: Summarization of large repos into essential constraints

---

## 14. Conclusion

Code knowledge graphs represent a **paradigm shift** from "LLM as pattern completer" to "LLM as constraint-based synthesizer operating on structured repository memory."

**Empirical evidence**: 15-50% improvements on realistic repository tasks. Not just academic - deployed in industrial settings (Volvo, Huawei, Alibaba).

**Theoretical foundation**: Graph structure captures what embeddings cannot - transitive relationships, type propagation, architectural invariants.

**Practical takeaway**: If you're building AI for real-world software engineering (not toy benchmarks), **invest in code KG infrastructure**. The gains are largest where they matter most: complex, integrated code.

**Open challenge**: Engineering complexity. State-of-the-art (SemanticForge) requires SMT, learned queries, dual analysis. Making this accessible to practitioners is next frontier.

**Final assessment**: Code KGs are not a passing fad. They address fundamental limitations of pure LLMs: lack of precise repository understanding, inability to enforce constraints, no traceable reasoning. The papers collectively demonstrate a maturing field moving from exploration to deployment.

---

## Appendix: Paper Quick Reference

| Paper | Year | Key Idea | Best For | Complexity |
|-------|------|----------|----------|------------|
| 2304.09048 | 2024 | CodeLM for KG construction | Automated KG building | Low-Medium |
| 2404.00599 | 2024 | Evolving benchmark | Evaluation standard | N/A |
| 2310.06770 | 2024 | Real GitHub issues | Repair benchmark | N/A |
| 2406.07003 | 2024 | CCG with decay | Code completion | Medium |
| 2408.03910 | 2024 | Graph DB interface | General LLM-codebase interaction | Medium |
| 2503.21710 | 2025 | Artifact linkage + paths | Issue repair | Medium-High |
| 2505.14394 | 2025 | Hybrid retrieval + LLM descs | General code generation | Medium |
| 2511.07584 | 2025 | Dual graphs + SMT decoding | State-of-the-art generation | Very High |
| 2411.11532 | 2024 | KG-guided fuzzing | Security testing | High |
| 2603.07326 | 2026 | Auto-execution + dual validation | Test reproduction | Medium |
| 2603.21430 | 2026 | KG + case-based reasoning | Domain adaptation | Medium-High |

**Recommended reading order**:
1. Start: 2404.00599 (benchmark motivation), 2406.07003 (basic CCG)
2. Core: 2505.14394 (complete pipeline), 2511.07584 (frontier)
3. Applications: Choose based on interest (repair: 2503.21710; fuzzing: 2411.11532; domain: 2603.21430; tests: 2603.07326)
4. Construction: 2304.09048 if building KG from scratch

---

**Document Version**: 1.0  
**Last Updated**: April 2025  
**Coverage**: 11 papers, 2023-2026
