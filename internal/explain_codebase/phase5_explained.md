# Phase 5 — CloudDesk Knowledge Pipeline

## A plain-language presentation

> **Use this as a speaking script.** It explains Phase 5 for an audience that
> may not have a software background.

Phases 1 through 4 prepared the application, its example business records, its
access rules, and its ticket and customer APIs. Phase 5 gives support staff a
reliable way to find the right information in CloudDesk's support articles.

Think of the knowledge base as the team's digital handbook. Instead of asking
an employee to read every page whenever a new question arrives, Phase 5 prepares
the handbook for quick searching and returns the most relevant passages with
their sources.

The short version is:

```text
Support articles
  → are split into labeled excerpts
  → are prepared for both meaning-based and word-based search
  → are ranked and combined
  → are returned as cited evidence to a support agent
```

Phase 5 finds and presents information. It does not independently send an answer
to a customer or take an action on a customer account.

## The problem Phase 5 solves

Imagine that a support agent receives this message:

> “Our nightly sync keeps getting an API 429 error.”

The team may have an article explaining rate limits and retry behavior. The
system needs to find that article even when the customer's wording is not
identical to the article's title.

Phase 5 uses two complementary ways to search:

- **Word search:** looks for important words that appear in the articles.
- **Meaning search:** looks for passages whose overall wording is related to
  the question, even if the exact words differ.

Combining both is more dependable than relying on only one.

## The main pieces

### 1. The support articles — P5-1

The articles are Markdown files: ordinary text files with headings. Each one
starts with a small information label containing its title, category, tags, and
short summary.

For example, the rate-limit article is labeled as an API issue and tagged with
terms such as “429” and “backoff.” These labels help the system organize and
narrow its search.

The article loader checks that the required labels are present and that the
category is one CloudDesk recognizes. If an article is malformed, the system
reports the problem rather than quietly treating it as valid.

### 2. Breaking articles into excerpts — P5-1

A whole article can be too large to search as one item. Phase 5 splits an
article at its headings and, when needed, into shorter overlapping sections.
Each excerpt keeps its title, heading, category, and source reference.

This is like adding a page label and section heading to every small card in a
filing cabinet. The system can find the specific useful passage and still tell
the agent which article and section it came from.

The current example set has 15 articles. In the verified local ingest run, those
articles produced 45 searchable excerpts.

### 3. Meaning search and local vector storage — P5-2

For meaning search, the system turns each excerpt into a list of numbers that
represents its wording. A question is converted in the same way, and the system
compares the two representations.

In the offline demonstration, these numbers are created by a deterministic
“fake embeddings” provider. It does not call an external AI service, so the
project can be tested without an API key or internet connection. It is useful
for development, but it is not a claim that the demo's word representations
understand language like a production model.

The project can keep searchable excerpts in a simple in-memory store for local
use or use Qdrant as the configured vector database. Both options follow the
same storage interface, so the search code does not need to be rewritten when
the storage choice changes.

### 4. Combined retrieval — P5-3

When an agent asks a question, Phase 5 can run meaning search and word search
side by side. It combines their rankings so a passage that does well in both
methods is likely to appear near the top.

The system then:

1. Applies a requested category filter, if one was provided.
2. Gives a modest preference to matching article titles and categories.
3. Keeps at most one excerpt from each article in the final results.
4. Returns up to the requested number of results with source details.

The ranking combination is called **reciprocal rank fusion**. In plain language,
it is a way to combine two ordered lists without assuming their scores use the
same scale.

There is also a hook for an optional reranker to further reorder results. The
current knowledge service does not configure an AI reranker; the offline path
uses the local ranking steps above.

## What happens when knowledge is searched

```text
Agent asks a question
  └─ The API checks the user's role and validates the search options
       └─ Meaning search finds related excerpts
       └─ Word search finds excerpts containing relevant terms
            └─ The rankings are combined and duplicate articles are removed
                 └─ The API returns the best excerpts and their citations
```

The result includes the excerpt, its title, a score, and a source such as
`kb://api-rate-limits#retry-behavior`. The source is similar to a citation in a
report: it tells the support agent which article and section support the result.
The response also includes the article identifier so the UI can link to the
full article.

The score helps order results. It should not be presented as a guarantee that a
passage is correct; an agent still needs to read and assess the cited material.

## The knowledge API — P5-4

The backend provides four knowledge operations:

| Operation | Minimum role | Everyday meaning |
|---|---|---|
| List articles | Viewer | Browse the article directory |
| Read an article | Viewer | Open one complete article |
| Search articles | Viewer | Find cited passages for a question |
| Rebuild the search index | Admin | Refresh the prepared search data |

The list and detail operations expose the article information needed by the
support console. Search accepts a question and optional category, search mode,
and result count. The API checks those values before starting the search.

An agent or viewer can search, but only an admin can request a reindex through
the API. That distinction prevents a normal read request from unexpectedly
replacing the shared search index.

## Ingesting and rebuilding the index

**Ingesting** means reading the article files, splitting them into excerpts,
preparing their search representations, and adding them to the configured
vector store.

The application initializes its knowledge service at startup. For a fresh
in-memory store, it loads the articles and prepares the index. An operator can
also run the explicit offline command:

```text
python -m backend.app.cli.ingest_knowledge
```

The repository also has a `make ingest` target for environments with GNU Make.
The command reports how many articles and excerpts it indexed. An administrator
can rebuild the running application's index through the protected reindex API.
Rebuilding clears the old configured index before adding the current excerpts;
if rebuilding fails after the clear, search reports that the index is
unavailable instead of pretending that it succeeded.

## How the components fit together

```text
Markdown article files
  └─ Article loader and chunker
       └─ Ingestion prepares labeled excerpt records
            ├─ Meaning search: embeddings + vector store
            └─ Word search: BM25 keyword ranking
                 └─ Hybrid retriever combines and deduplicates results
                      └─ Knowledge service
                           └─ Protected FastAPI knowledge routes
                                └─ Cited results for the support console
```

The responsibilities are deliberately separated:

- **Article files** contain the support guidance.
- **The chunker** makes the guidance small enough to search while preserving
  where each excerpt came from.
- **The vector store** holds excerpts for meaning-based search.
- **The retriever** combines meaning and word search.
- **The service** connects article data, storage, and retrieval.
- **The API** checks roles, validates requests, and returns consistent responses.
- **The API contract and TypeScript types** describe the same response shapes
  for backend and frontend development.

## Safety and boundaries

- Article text is reference material, not an instruction to the software.
- Article content is treated as untrusted input.
- Search results include a source so an agent can check the original guidance.
- Viewing and searching require an authenticated viewer-or-higher role.
- Reindexing through the API requires an admin role.
- No real email is sent and no customer account is changed by knowledge search.
- The default offline setup uses fake embeddings and in-memory storage; no live
  Qdrant service is required for the local demo.

## What Phase 5 does not do

Phase 5 does not:

- decide a ticket's final answer on its own;
- send a customer reply;
- issue a refund or change an account;
- guarantee that the highest-ranked result is correct;
- use a live language-model reranker in the current knowledge service;
- prove the retrieval hit-rate target, because an evaluation dataset and suite
  are not present yet.

Later workflow and agent phases can use the cited evidence as one input to their
investigation. The human support agent remains responsible for reviewing what
the system found.

## Validation and honest status

The current local implementation includes the 15 article fixtures, article
chunking, fake embeddings, in-memory and Qdrant vector-store adapters, hybrid
retrieval, ingestion, and the knowledge API.

The full offline test suite passed **87 tests**. The ingest command was also
run locally and reported 15 articles and 45 excerpts. The Qdrant reset behavior
was tested with a stub, not a live Qdrant service. No cloud service was used.
The retrieval hit-rate target remains unverified until evaluation cases and
their test are added.

## Short answers for likely questions

**Why split an article into excerpts?**  
It lets the system return the useful section instead of making an agent search
through a full document.

**Why use two search methods?**  
Word search is good when the question uses the article's exact terms. Meaning
search can help when the wording is different. Combining them gives the agent
more useful candidates.

**Can the system show where an answer came from?**  
Yes. Search results carry a citation to the article and section.

**Does a search result automatically become a customer reply?**  
No. Phase 5 returns evidence to the support workflow; it does not send replies.

**Who can rebuild the shared index?**  
An admin through the API. The local operator command is for development and
offline setup.

**Has the project proven the retrieval accuracy target?**  
Not yet. The code and offline behavior are tested, but the evaluation dataset
needed to measure that target is not present.
