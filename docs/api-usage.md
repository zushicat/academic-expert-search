# API Usage

This document describes how to use the Academic Expert Search API exposed by the FastAPI application in this repository.

The API currently exposes five useful routes:

- `GET /`
- `GET /expert/search`
- `GET /expert/search/stream`
- `GET /expert/recommender`
- `GET /expert/recommender/stream`

The expert endpoints are read-only `GET` endpoints. They accept query parameters and return either JSON or a streamed Server-Sent Events (SSE) response.

## Base URL

The routes in [`src/app.py`](/Users/karin/_programming/academic-expert-search/src/app.py) are mounted without a prefix, so the path in this document is the full HTTP path.

Examples below assume a local server such as:

```text
http://localhost:8000
```

## Authentication

Authentication is enforced globally through a bearer-token dependency in [`src/auth.py`](/Users/karin/_programming/academic-expert-search/src/auth.py).

- `GET /` is exempt from authentication.
- All `/expert/...` routes require `Authorization: Bearer <token>` when `USE_API_KEY=true`.
- When `USE_API_KEY=false`, the expert routes can be called without the header.

Example:

```bash
curl \
  -H "Authorization: Bearer $API_KEY" \
  "http://localhost:8000/expert/search?query=graph+neural+networks"
```

Auth failures come from FastAPI's default `HTTPException` handling, so they return a payload like:

```json
{"detail":"Missing Authorization header"}
```

Possible auth errors:

- `401` for missing `Authorization` header
- `401` for a non-bearer scheme
- `403` for an invalid bearer token

## Common Response Pattern

The non-streaming expert endpoints wrap successful results in this envelope:

```json
{
  "Status": "ok",
  "Response": { "...": "payload" }
}
```

Application-level failures from the route handlers are usually returned as:

```json
{
  "Status": "Error",
  "Response": "error message"
}
```

Two details are important for client code:

- Success uses `"ok"` while failure uses `"Error"` with different casing.
- Some application errors are returned with HTTP `200`, not only with `4xx`.

## Output Modes

All four expert routes support the same two output modifiers:

- `short_response=true` by default
- `toon=false` by default

### `short_response`

When `short_response=true`, the API returns a reduced, client-friendly payload.

When `short_response=false`, the API returns the fuller internal object graph. That fuller payload includes additional fields such as:

- Search: `relevance_score`, `from_query_search`, topic hierarchy metadata, `from_relevant_author_list`, `active_years_counted`, `works_author`
- Recommender: author `scores`, `expert_connections`, and the fuller search-derived structures

For most integrations, `short_response=true` is the easier starting point.

### `toon`

When `toon=true`, `Response` is no longer a JSON object. It becomes a TOON-encoded string produced by [`src/helpers/toon.py`](/Users/karin/_programming/academic-expert-search/src/helpers/toon.py).

That means client code must branch on this flag:

- `toon=false`: parse `Response` as JSON
- `toon=true`: parse `Response` as a string and decode it with a compatible TOON decoder

The same rule applies to streamed completion events: the `result` field is a TOON string when `toon=true`.

## `GET /`

Simple root endpoint mainly useful as a connectivity check.

### Request

```bash
curl "http://localhost:8000/"
```

### Response

```json
{
  "Status": "ok",
  "Response": "GET Root"
}
```

## `GET /expert/search`

Builds a broad expert candidate set from a query by:

1. searching OpenAlex works for the query
2. extracting reference authors from those works
3. finding the topics most shared across those authors
4. retrieving additional authors that match the resulting topic combination
5. aggregating works, authors, institutions, and metadata into one response

This is the discovery endpoint. It is intentionally broader than the recommender.

### Query Parameters

| Parameter | Type | Default | Meaning |
| --- | --- | --- | --- |
| `query` | string | `""` | Search text sent into the work search flow |
| `use_fulltext_search` | boolean | `false` | Uses OpenAlex `search=` instead of `title_and_abstract.search:` |
| `create_queries` | boolean | `false` | Expands the input query with the LLM before work search |
| `short_response` | boolean | `true` | Returns the compact response shape |
| `toon` | boolean | `false` | Returns TOON-encoded payload instead of JSON object in `Response` |

### Important Behavior

- The route does not reject an empty `query` at the router level, but an empty query is not useful in practice.
- The search implementation currently requests up to `20` works and restricts them to publication year `> 2019`, effectively `2020+`.
- When `create_queries=true`, the query expansion helper generates `3` additional queries by default.
- Query-expanded work results are deduplicated by OpenAlex work id before the rest of the pipeline runs.
- Candidate authors found through topic matching are fetched with a limit of `100`.

### Example

```bash
curl \
  -H "Authorization: Bearer $API_KEY" \
  "http://localhost:8000/expert/search?query=wild%20bee%20population%20decline%20bee%20monitoring"
```

### Example With Full-Text Search And Query Expansion

```bash
curl \
  -H "Authorization: Bearer $API_KEY" \
  "http://localhost:8000/expert/search?query=graph%20neural%20networks&use_fulltext_search=true&create_queries=true"
```

### Short Response Shape

With `short_response=true`, the payload shape is:

```json
{
  "Status": "ok",
  "Response": {
    "topics": [],
    "works": [],
    "institutions": [],
    "authors": [],
    "meta": {}
  }
}
```

### Short Response Fields

#### `Response.topics[]`

Each topic contains:

- `id`: OpenAlex topic id or URL
- `display_name`: human-readable topic name when available

#### `Response.works[]`

Each work contains:

- `openalex_id`
- `doi`
- `title`
- `publication_year`
- `primary_topic`
- `author_ids`

#### `Response.institutions[]`

Each institution contains:

- `openalex_id`
- `ror`
- `display_name`
- `country_code`
- `type`

#### `Response.authors[]`

Each author contains:

- `openalex_id`
- `orcid_id`
- `display_name`
- `two_yr_mean_citedness`
- `h_index`
- `i10_index`
- `relevant_topics`: list of topic ids marked relevant for that author
- `relevant_topics_share`: count of selected shared topics matched by this author
- `active_years_min`
- `active_years_max`
- `active_years_sum`
- `institutions`: list of affiliation periods with `openalex_id`, `year_start`, `year_end`
- `instituitions_count`: note the field name is misspelled in the API and should be consumed as-is
- `works_search`: list of work ids attached from the initial search stage
- `works_search_count`

#### `Response.meta`

Search metadata contains:

- `query`: original input query
- `generated_queries`: LLM-generated alternatives, if any
- `reference_author_count`: number of authors extracted from the first work set
- `author_count`: number of authors in the final search response
- `works_count`
- `institutions_count`
- `best_match_topics`: mapping of topic id to shared-author count
- `topics_filter`: OpenAlex topic filter expression used to retrieve candidate authors
- `authors_topic_share_counts`: histogram of author counts by matched-topic-share value

### Interpretation Tips

- `best_match_topics` tells you which topics most strongly define the search area.
- `relevant_topics_share` is the main search-side ranking signal in the short response.
- `topics_filter` is useful for debugging and for understanding how the candidate author pool was constructed.

### Sample Payloads

Sample abbreviated response:

- [`docs/abbr_short_search_response.json`](/Users/karin/_programming/academic-expert-search/docs/abbr_short_search_response.json)

## `GET /expert/search/stream`

Streaming version of the search endpoint. It runs the same search logic but emits progress updates as SSE.

### Query Parameters

The parameters are identical to `GET /expert/search`:

- `query`
- `use_fulltext_search`
- `create_queries`
- `short_response`
- `toon`

### Response Type

Content type:

```text
text/event-stream
```

The implementation only writes `data:` lines, not SSE `event:` lines. Each event is a JSON object serialized into the data frame:

```text
data: {"event":"started","timestamp":...,"stage":"search","step":"start","message":"Starting expert search","result":null}

data: {"event":"step","timestamp":...,"stage":"search","step":"search_works","message":"Searching works matching the query","result":null}

data: {"event":"completed","timestamp":...,"stage":"search","step":"completed","message":"Search stream completed","result":{...}}
```

### Event Object

Each streamed item follows this structure:

```json
{
  "event": "started|step|completed|error",
  "timestamp": 1740000000.0,
  "stage": "search",
  "step": "search_works",
  "message": "Searching works matching the query",
  "result": null
}
```

`result` is only populated on the final `completed` event or on certain error paths.

### Search Stream Steps

The search flow emits the following step names during normal execution:

- `start`
- `search_works`
- `expand_query` when `create_queries=true`
- `extract_reference_authors`
- `fetch_reference_authors`
- `collect_topics`
- `select_shared_topics`
- `find_authors_by_topics`
- `aggregate_authors`
- `assemble_response`
- `completed`

### Example

```bash
curl -N \
  -H "Authorization: Bearer $API_KEY" \
  "http://localhost:8000/expert/search/stream?query=wild%20bee%20population%20decline%20bee%20monitoring"
```

## `GET /expert/recommender`

Runs the search flow first and then applies stronger filtering and scoring to return a more opinionated expert ranking.

At a high level it:

1. runs the search pipeline
2. selects stronger candidate authors from the search output
3. fetches more recent works for those authors
4. builds an expert graph over authors, works, institutions, and topics
5. computes recommendation scores
6. trims the response to the most relevant experts
7. optionally generates LLM summaries

### Query Parameters

| Parameter | Type | Default | Meaning |
| --- | --- | --- | --- |
| `query` | string | `""` | Required in practice; empty query returns an application error |
| `create_expert_summaries` | boolean | `false` | Generates expert summaries from author works |
| `top_perc_found_authors` | float | `0.8` | Topic-share cutoff factor used to keep the strongest candidates from the search step |
| `use_fulltext_search` | boolean | `false` | Passed through to the search stage |
| `create_queries` | boolean | `false` | Passed through to the search stage |
| `short_response` | boolean | `true` | Returns the compact recommender payload |
| `toon` | boolean | `false` | Returns TOON-encoded payload instead of JSON object in `Response` |

### `top_perc_found_authors` Explained

This parameter is not a percentile over authors. It is used as a multiplier over the maximum topic-share count found in the search result.

The code computes:

```text
round(max(authors_topic_share_counts.keys()) * top_perc_found_authors)
```

Example:

- if the best search authors match `5` shared topics
- and `top_perc_found_authors=0.8`
- the recommender keeps authors with at least `4` matched shared topics before the later scoring steps

### Additional Recommender Behavior

- After graph scoring, authors below an `overall_score` cutoff of `0.5` are dropped.
- Recent author works are fetched from the last `3` years.
- If `create_expert_summaries=true`, the recommender runs an LLM summary stage after ranking.

### Example

```bash
curl \
  -H "Authorization: Bearer $API_KEY" \
  "http://localhost:8000/expert/recommender?query=wild%20bee%20population%20decline%20bee%20monitoring"
```

### Example With Summaries

```bash
curl \
  -H "Authorization: Bearer $API_KEY" \
  "http://localhost:8000/expert/recommender?query=wild%20bee%20population%20decline%20bee%20monitoring&create_expert_summaries=true"
```

### Short Response Shape

With `short_response=true`, the payload shape is:

```json
{
  "Status": "ok",
  "Response": {
    "topics": [],
    "works": [],
    "institutions": [],
    "authors": [],
    "meta": {}
  }
}
```

### Short Response Fields

#### `Response.topics[]`

Same meaning as in search.

#### `Response.works[]`

Same meaning as in search, but the recommender usually returns a larger work set because it attaches additional works from the remaining authors.

#### `Response.institutions[]`

Same meaning as in search.

#### `Response.authors[]`

Each author contains:

- `openalex_id`
- `orcid_id`
- `display_name`
- `two_yr_mean_citedness`
- `h_index`
- `i10_index`
- `relevant_topics`
- `relevant_topics_share`
- `active_years_min`
- `active_years_max`
- `active_years_sum`
- `institutions`
- `instituitions_count`: same misspelling as in search
- `works`: list of attached work ids for the recommended author
- `works_count`
- `summary`: `null` unless summary generation was requested and succeeded

The short recommender response intentionally omits the detailed score breakdown. If you need the fuller score objects and expert-connection data, use `short_response=false`.

#### `Response.meta`

Recommender metadata contains:

- `author_count`
- `works_count`
- `institutions_count`
- `author_min_score`
- `author_max_score`
- `search`: embedded search metadata from the initial search stage

### Sample Payloads

Sample abbreviated response:

- [`docs/abbr_short_recommender_response.json`](/Users/karin/_programming/academic-expert-search/docs/abbr_short_recommender_response.json)

## `GET /expert/recommender/stream`

Streaming version of the recommender endpoint. It includes progress updates for both the search and recommender phases and emits the final result as the last event.

### Query Parameters

The parameters are identical to `GET /expert/recommender`.

### Response Type

Content type:

```text
text/event-stream
```

Like the search stream, this endpoint only emits `data:` frames containing JSON.

### Event Object

The JSON event object uses the same structure as the search stream:

```json
{
  "event": "started|step|completed|error",
  "timestamp": 1740000000.0,
  "stage": "search|recommender|stream",
  "step": "some_step_name",
  "message": "Human-readable progress message",
  "result": null
}
```

### Recommender Stream Steps

The recommender stream can emit both search-stage and recommender-stage step names.

Search-stage steps:

- `search_works`
- `expand_query` when enabled
- `extract_reference_authors`
- `fetch_reference_authors`
- `collect_topics`
- `select_shared_topics`
- `find_authors_by_topics`
- `aggregate_authors`
- `assemble_response`

Recommender-stage steps:

- `start`
- `select_candidates`
- `filter_search_result`
- `fetch_author_works`
- `process_author_works`
- `build_graph_and_score`
- `refine_scores_and_connections`
- `trim_response`
- `prepare_summaries` when summaries are enabled
- `request_summaries` when summaries are enabled
- `summaries_completed` when summaries are enabled
- `assemble_response`
- `completed`

### Empty Query Behavior

If `query` is empty, this route does not return a JSON error body. Instead it emits an SSE error event:

```json
{
  "event": "error",
  "stage": "recommender",
  "step": "validate_query",
  "message": "You must pass a search query."
}
```

### Example

```bash
curl -N \
  -H "Authorization: Bearer $API_KEY" \
  "http://localhost:8000/expert/recommender/stream?query=wild%20bee%20population%20decline%20bee%20monitoring"
```

## Error Handling Summary

Different failure paths return different payload styles.

### Application Errors From Route Handlers

Usually returned as:

```json
{
  "Status": "Error",
  "Response": "error message"
}
```

Examples:

- `GET /expert/recommender` with empty `query` returns HTTP `200` and `{"Status":"Error","Response":"You must pass a search query."}`
- internal exceptions in `/expert/search` and `/expert/recommender` are caught and wrapped the same way

### Validation Errors

FastAPI validation errors are converted in [`src/app.py`](/Users/karin/_programming/academic-expert-search/src/app.py) to:

```json
{
  "Status": "Error",
  "Response": "Value error, ..."
}
```

These use HTTP `400`.

### Missing Endpoint

Unknown paths return HTTP `404` with:

```json
{
  "Status": "Error",
  "Response": "Endpoint not existing"
}
```

### Authentication Errors

Auth errors use FastAPI's default `HTTPException` format:

```json
{
  "detail": "Invalid token"
}
```

### Stream Errors

Streaming routes do not return the standard JSON envelope after streaming starts. They emit SSE error events instead.

In addition, the internal stream wrapper can emit:

- `event="error"`
- `stage="stream"`
- `step="failed"`

when an unhandled exception occurs in the worker task.

## Integration Recommendations

- Start with `short_response=true` unless you explicitly need internal scoring or graph details.
- Treat `toon=true` as a different payload type, not just a formatting tweak.
- For UI progress, prefer the `/stream` endpoints and read the `step` field rather than only the `message`.
- Do not rely only on HTTP status for application success; inspect the JSON `Status` field for non-streaming routes.
- Consume `instituitions_count` exactly as returned even though the field name is misspelled.

## Related Documents

- [`docs/application-overview.md`](/Users/karin/_programming/academic-expert-search/docs/application-overview.md)
- [`docs/abbr_short_search_response.json`](/Users/karin/_programming/academic-expert-search/docs/abbr_short_search_response.json)
- [`docs/abbr_short_recommender_response.json`](/Users/karin/_programming/academic-expert-search/docs/abbr_short_recommender_response.json)
