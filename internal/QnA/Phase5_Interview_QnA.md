# Phase 5 — Interview Questions and Answers

This question bank covers **Phase 5: Knowledge pipeline**. Answers are written
to be spoken in an interview and distinguish implemented behavior from future
work.

Related reading:

- [Phase 5 plain-language explanation](../explain_codebase/phase5_explained.md)
- [Phase 5 system design evolution](../design_evolution/Phase5_Project_System_Design_Evolution.md)
- [Phase 5 infrastructure evolution](../Infra_design_evolution/Phase5_Infra_design_evolution.md)
- [Phase 5 task status](../../TASK.md)
- [Phase plan and exit criteria](../../PLAN_PHASE.md)

## 30-second overview

### 1. Can you summarize Phase 5?

**A:** “Phase 5 makes CloudDesk support articles searchable. It loads Markdown
articles, splits them into cited sections, prepares them for vector and
keyword search, combines both types of results, and exposes the knowledge
operations through protected API routes. It runs offline with fake embeddings
and an in-memory vector store.”

### 2. What problem does the phase solve?

**A:** “Support staff should not have to read every handbook article to find a
relevant answer. Phase 5 searches for useful passages and returns the article
and section they came from.”

### 3. What is the main design goal?

**A:** “Keep content preparation, vector storage, retrieval, service
coordination, and HTTP authorization in separate components. That makes the
pipeline testable offline and lets the storage implementation change without
rewriting the API.”

### 4. Which subtasks make up Phase 5?

**A:** “P5-1 adds knowledge articles and chunking. P5-2 adds embeddings and a
vector-store interface. P5-3 combines semantic and keyword retrieval. P5-4
wires the pipeline into startup, adds the knowledge API, and provides an ingest
command.”

### 5. Does Phase 5 generate and send a customer answer?

**A:** “No. It finds and returns cited evidence. It does not generate a final
customer response, send an email, issue a refund, or change an account.”

### 6. Is Phase 5 the same as a complete RAG answer-generation system?

**A:** “It implements the retrieval and evidence part of a retrieval-augmented
system. It does not yet connect those results to a language model that writes
the customer response.”

### 7. Does Phase 5 search resolved tickets as well as articles?

**A:** “The Phase 5 knowledge index searches the Markdown support articles.
Searching similar previously resolved cases is not included in this phase.”

### 8. Is the support console's knowledge page part of this phase?

**A:** “No. Phase 5 provides backend routes and frontend contract types. It does
not implement a running knowledge-search screen.”

### 9. Why is the phase called a pipeline?

**A:** “Each subtask prepares something the next one needs: articles become
chunks, chunks can be embedded and stored, the retriever combines search
methods, and the API exposes the finished pipeline.”

### 10. What is the difference between ‘task complete’ and ‘phase complete’?

**A:** “The four Phase 5 tasks are marked complete in the task checklist. The
phase remains in progress in the exit-criteria plan because the retrieval
hit-rate target has not been measured.”

## Knowledge articles and chunking

### 11. What is the source of knowledge?

**A:** “The source is a set of Markdown files in the knowledge-base directory.
Each file contains article text and a small metadata header.”

### 12. What metadata does an article need?

**A:** “It needs a title, category, tags, and summary. The loader also checks
that the category is one of the application's supported categories.”

### 13. Why use Markdown files instead of putting the articles directly in code?

**A:** “Markdown keeps support guidance readable and editable as content. The
loader converts it into structured article records at runtime.”

### 14. What does ‘chunking’ mean?

**A:** “Chunking means dividing a long article into smaller passages so search
can return the relevant section rather than an entire unrelated page.”

### 15. How are the chunks created?

**A:** “The code splits the article at Markdown headings, then divides long
sections into windows of up to 900 characters with a 150-character overlap.”

### 16. Why split at headings first?

**A:** “Headings give passages useful context. A section about API limits is
more meaningful as its own search unit than as part of one large article.”

### 17. Why do the windows overlap?

**A:** “Overlap reduces the chance that an important sentence near a window
boundary gets separated from the context needed to understand it.”

### 18. Why is the article title and heading added to each chunk?

**A:** “The title and heading provide context even when a short passage is
retrieved on its own. They also help ranking and source identification.”

### 19. What provenance does each chunk keep?

**A:** “It keeps the article ID, title, heading, category, tags, summary, slug,
and a source such as `kb://api-rate-limits#retry-behavior`.”

### 20. How are chunk IDs made stable?

**A:** “The chunk ID is derived from the article slug, heading, window number,
and text using a hash. The vector document ID is then a deterministic UUID.
This gives the same content a repeatable identifier across ingests.”

### 21. What happens if an article is malformed?

**A:** “The loader raises a clear error for missing required metadata or an
invalid category. It does not quietly index malformed content.”

### 22. What happens if no articles are found?

**A:** “The index refuses to initialize and reports that no knowledge articles
were found in the configured directory.”

### 23. How many example articles and chunks are currently present?

**A:** “The local sample contains 15 articles. The verified ingest run created
45 searchable chunks.”

## Embeddings and vector storage

### 24. What is an embedding?

**A:** “An embedding is a list of numbers representing text. Search compares a
question's vector with article vectors to find passages that are related.”

### 25. What embedding provider does the offline setup use?

**A:** “It uses deterministic fake embeddings: a hashed bag-of-words
representation with 384 dimensions by default. It runs locally and needs no
external model API.”

### 26. Are fake embeddings equivalent to a production language model?

**A:** “No. They provide a repeatable offline representation for development
and tests; they are not a claim of production-quality language understanding.”

### 27. Why provide fake embeddings?

**A:** “They let the project ingest and search articles offline, make tests
repeatable, and avoid requiring a model API key for the demo.”

### 28. What is the vector-store interface responsible for?

**A:** “It defines the common operations for adding, searching, deleting,
clearing, counting, and checking the health of vector documents.”

### 29. Which vector-store implementations exist?

**A:** “There is an in-memory implementation for offline use and a Qdrant
adapter for a configured vector database.”

### 30. How is the storage choice selected?

**A:** “Settings choose the provider. The default is `VECTOR_STORE=memory`; the
Qdrant adapter requires a configured Qdrant URL.”

### 31. Does the default in-memory store survive a process restart?

**A:** “No. It is process-local and its contents disappear when the process
exits. It is useful for tests and demos, not durable shared storage.”

### 32. Does the project use Qdrant by default?

**A:** “No. The example configuration defaults to memory and leaves the Qdrant
URL empty. The adapter exists, but a live Qdrant service was not used for
validation.”

### 33. Is the relational database also used to store knowledge vectors?

**A:** “No. Ticket and customer records use the relational database. Knowledge
vectors use the vector-store interface. They are separate storage paths.”

### 34. Why use an interface instead of writing directly to Qdrant?

**A:** “The interface keeps retrieval independent of one storage product. The
same search code can use in-memory storage locally or a configured Qdrant
adapter.”

### 35. How are vector document IDs made compatible with Qdrant?

**A:** “The code converts the deterministic chunk ID into a UUID using UUID5,
so the point identifier is repeatable and has the expected UUID form.”

## Hybrid retrieval

### 36. What does ‘hybrid retrieval’ mean?

**A:** “It combines semantic search, which compares text representations, with
keyword search, which looks for matching terms. Each method can find passages
the other might miss.”

### 37. Which keyword-search method is used?

**A:** “BM25 ranks article chunks based on the query terms and how they occur in
the corpus.”

### 38. What retrieval modes can a caller request?

**A:** “The API supports `hybrid`, `semantic`, and `keyword` modes. Hybrid is
the default.”

### 39. How are the two result lists combined?

**A:** “The retriever uses reciprocal rank fusion with `k=60`. It adds a
contribution of `1 / (60 + rank)` for each result's position in a ranked list,
so it combines ranks without assuming the two search methods' raw scores use
the same scale.”

### 40. What happens after rank fusion?

**A:** “The retriever applies category and title-overlap heuristics, keeps at
most one result per article, and returns the requested number of evidence
items.”

### 41. Can a caller restrict search to a category?

**A:** “Yes. The request can include a supported category. The retriever filters
the article chunks and passes a category filter to semantic search.”

### 42. How many results can an API caller request?

**A:** “The request schema allows `top_k` from 1 to 20, with a default of 5.
The retriever considers up to 20 candidates from each search method.”

### 43. Why return at most one result per article?

**A:** “It prevents the final list from being dominated by several passages
from one article and gives the agent a broader set of sources to review.”

### 44. What information is returned for each evidence item?

**A:** “It includes an ID, title, source citation, snippet, score, article URL,
and article ID.”

### 45. Is the score a confidence percentage?

**A:** “No. It is a ranking score, not a calibrated probability that the result
is correct. The agent should read the cited passage.”

### 46. Is an AI reranker active?

**A:** “There is an optional reranker hook in the retriever, but the current
knowledge service does not configure a language-model reranker. The implemented
path uses local ranking.”

### 47. Does the retriever cache search results?

**A:** “Yes. It has a bounded in-process cache with a 300-second time-to-live
and up to 512 entries. The key includes the normalized query, mode, category,
and result count.”

### 48. Does Phase 5 use Redis for its retrieval cache?

**A:** “No. The retrieval cache is local to the retriever process. Redis is not
wired into this knowledge-search cache.”

### 49. What prevents old vector-store results from being returned?

**A:** “The retriever checks that semantic result IDs belong to the currently
loaded article documents. That prevents stale points from an older index from
appearing as current evidence.”

### 50. Is the keyword index built once at startup?

**A:** “The current retriever builds BM25 from its in-memory documents when it
runs an uncached keyword search. For a much larger corpus, prebuilding and
maintaining that index would be a reasonable optimization.”

## Knowledge API and application wiring

### 51. What knowledge API operations were added?

**A:** “The API can list articles, return one article, search for evidence, and
rebuild the index.”

### 52. What are the route paths?

**A:** “They are `GET /api/v1/knowledge`,
`GET /api/v1/knowledge/{article_id}`,
`POST /api/v1/knowledge/search`, and
`POST /api/v1/knowledge/reindex`.”

### 53. Who can search or read articles?

**A:** “An authenticated viewer or higher role can list, read, and search
articles.”

### 54. Who can reindex through the API?

**A:** “Only an authenticated admin can use the API reindex route.”

### 55. What validates a search request?

**A:** “Pydantic requires a non-empty query up to 2,000 characters, validates
the optional category and retrieval mode, and limits `top_k` to 1 through 20.”

### 56. What is the responsibility of the knowledge API router?

**A:** “It enforces role dependencies, validates the request and response
shape, calls the service, and maps errors to HTTP responses. It does not
perform vector ranking itself.”

### 57. What does `KnowledgeService` do?

**A:** “It composes the configured embedding provider, vector store, article
index, and retriever, and provides operations for listing, reading, searching,
initializing, and reindexing.”

### 58. Does the knowledge API query ticket tables?

**A:** “No. Article listing and detail use the loaded article catalog; search
uses the retriever and vector store. Ticket and customer routes continue to
use their existing SQL services.”

### 59. When is the knowledge service initialized?

**A:** “During FastAPI application startup. The lifespan creates it from
settings, loads articles, initializes the vector store as needed, and installs
the retriever before serving requests.”

### 60. Does startup always rebuild an existing vector index?

**A:** “No. It indexes when the configured store is empty. If it already
contains vectors, startup loads the current article catalog but leaves the
stored vectors alone. Operators use explicit reindexing to rebuild them.”

### 61. What happens if the knowledge service is unavailable?

**A:** “If the application has no initialized knowledge service, the router
returns HTTP 503. The reindex route also maps indexing errors to HTTP 503.
Search requires an initialized retriever; if that state is missing, the current
search route raises an error rather than returning an empty success response.”

### 62. What happens if an article ID does not exist?

**A:** “The detail route returns HTTP 404.”

### 63. What does the local ingest command do?

**A:** “It creates a knowledge service from the environment settings, reads the
article files, clears the configured index, rebuilds it, and prints the
article and chunk counts as JSON.”

### 64. Is the local ingest command protected by the API admin role?

**A:** “No. It is a local operator command, not an HTTP endpoint. The API
reindex route is protected by the admin role.”

### 65. Why might `make ingest` not populate the running server's in-memory store?

**A:** “The CLI runs in a separate process. With the default in-memory store,
its vectors disappear when it exits, and the API process has its own store.
Use a persistent configured vector store to share indexed data across
processes.”

### 66. Does Phase 5 add Docker networking?

**A:** “No. The repository has no Dockerfile or Compose configuration at this
phase. The backend runs as a local FastAPI process; Docker delivery is a later
project phase.”

## Testing, status, and limitations

### 67. How was Phase 5 tested?

**A:** “The offline test suite covers chunking, vector stores, retrieval,
ingestion, API authorization, and error handling. The full suite passed 87
tests in the recorded local verification.”

### 68. Was the ingest command run against the sample articles?

**A:** “Yes. It reported 15 articles and 45 chunks.”

### 69. Was a live Qdrant server tested?

**A:** “No. Qdrant adapter behavior was tested with a stub, but no live Qdrant
service was used.”

### 70. Has the retrieval hit-rate requirement been met?

**A:** “It has not been measured. The exit criterion is hit-rate-at-three of at
least 0.75, but the required evaluation dataset and test are not present.”

### 71. Were cloud services or credentials used?

**A:** “No. The local verification used the offline configuration; no cloud
deployment or live vector database was used.”

### 72. What happens if indexing fails after the old index is cleared?

**A:** “The index does not keep reporting itself as ready. It clears the
in-memory retriever state before adding the new documents, and the API reports
the reindex failure as HTTP 503. A subsequent search encounters the missing
retriever; mapping that search failure to an explicit HTTP 503 is a reasonable
follow-up improvement.”

### 73. Is article content automatically trusted as a customer answer?

**A:** “No. The API returns cited evidence for review. A result is not
automatically sent to a customer or treated as a guaranteed answer.”

### 74. What are the most important limitations to be transparent about?

**A:** “Fake embeddings are for offline development, Qdrant was not live-tested,
no language-model reranker is configured, there is no knowledge-search screen
yet, and retrieval hit-rate has not been measured.”

## Design and follow-up questions

### 75. Why not use only semantic search?

**A:** “Semantic search can find related wording, but exact terms such as an
error code may be important. Keyword search can catch those exact matches.
Combining both gives the support agent more useful candidates.”

### 76. Why not use only keyword search?

**A:** “Keyword search can miss relevant passages when the question uses
different wording from the article. Semantic search can help find related
passages even when the words differ.”

### 77. Why fuse ranks instead of raw scores?

**A:** “The vector and BM25 scores are on different scales. Rank fusion uses
each result's position in its own list, so it avoids treating unlike scores as
directly comparable.”

### 78. What would you improve before production?

**A:** “I would evaluate with a representative query set, measure the required
retrieval metrics, use a production embedding model, test against a live
Qdrant service, and consider prebuilding the BM25 index for larger corpora.”

### 79. How would you make retrieval results more reliable?

**A:** “I would build an evaluation set with expected relevant articles,
measure hit-rate and citation quality, inspect failures, and tune chunking and
ranking based on those measured results rather than assuming a higher score
means a correct answer.”

### 80. What is the key architectural lesson from Phase 5?

**A:** “Keep each responsibility behind a clear boundary: articles are content,
the chunker prepares passages, the vector store handles semantic retrieval,
the retriever combines search methods, the service coordinates them, and the
API controls access and response formats.”

## Additional technical follow-ups

### 81. What does BM25 stand for, and why is it useful here?

**A:** “BM25 is a probabilistic ranking method for text search. It is useful
for matching important exact terms such as product names, error codes, or
settings labels.”

### 82. Can the application use OpenAI or another embedding provider today?

**A:** “Not in the current implementation. The settings have provider fields,
but the embedding factory currently supports only the fake provider. A
production provider would need an implementation of the embedding protocol, a
factory update, and tests.”

### 83. What happens when an article changes on disk?

**A:** “The running index is not automatically watching the files. An operator
must run the ingest command or an admin must call the reindex API to rebuild
the index.”

### 84. Is API reindexing synchronous or queued?

**A:** “It is synchronous in the current API. The route awaits the reindex
operation and returns the article and chunk counts when it completes. A
background job would be a later scalability improvement.”

### 85. Does reindexing reset the retrieval cache?

**A:** “Yes. After a successful rebuild, the index creates a new retriever,
which has a fresh in-process cache.”

### 86. What is the difference between the returned score and final ordering?

**A:** “The category and title heuristics affect ordering, but the evidence
score returned by the current code is the fused rank score. It is not a
confidence value and does not include those heuristic bonuses.”

### 87. Are the results guaranteed to be identical in memory and Qdrant mode?

**A:** “They follow the same vector-store interface, but the adapters and
configured embedding behavior can affect scores and ordering. The interface
provides a consistent contract, not a guarantee of byte-for-byte identical
ranking.”

### 88. Does the current retrieval path call a language model?

**A:** “No. The configured path uses fake embeddings, BM25, reciprocal rank
fusion, and local heuristics. The optional reranker interface is not connected
to a language model.”

### 89. What would be involved in making the pipeline production-ready?

**A:** “I would add and validate a production embedding provider, use durable
vector storage, run live integration tests, measure retrieval against a
representative evaluation set, and add operational monitoring for reindexing
and search quality.”

### 90. How does Phase 5 fit into the later workflow?

**A:** “It provides cited knowledge evidence as an input for later specialist
agents. Those later phases can use the evidence while keeping ticket decisions,
customer replies, and consequential actions in their own controlled workflow.”

## Source-code map

| Topic | Implementation |
|---|---|
| Article parsing and chunking | [rag/chunking.py](../../rag/chunking.py) |
| Fake embeddings | [rag/embeddings.py](../../rag/embeddings.py) |
| Vector-store protocol and adapters | [rag/vector_store.py](../../rag/vector_store.py) |
| Hybrid retrieval and ranking | [rag/retriever.py](../../rag/retriever.py) |
| Ingestion and index lifecycle | [rag/ingest.py](../../rag/ingest.py) |
| Knowledge request and response schemas | [knowledge.py](../../backend/app/schemas/knowledge.py) |
| Knowledge routes and role restrictions | [api/knowledge.py](../../backend/app/api/knowledge.py) |
| Service composition | [knowledge_service.py](../../backend/app/services/knowledge_service.py) |
| Startup and router mounting | [main.py](../../backend/app/main.py) |
| Local ingest command | [cli/ingest_knowledge.py](../../backend/app/cli/ingest_knowledge.py) |
