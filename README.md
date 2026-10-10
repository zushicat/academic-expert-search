# Academic Expert Recommender
Get academic experts recommendations for a fuzzy query based on [Openalex](https://developers.openalex.org/) entities.

## Table of Contents
- [Overview](#overview)
- [Core Principle](#core-principle)
- [Search Endpoint](#search-endpoint)
  - [What Search Is Really Doing](#what-search-is-really-doing)
  - [Why Search Is Useful](#why-search-is-useful)
- [Recommender Endpoint](#recommender-endpoint)
  - [What Recommender Adds](#what-recommender-adds)
- [Search vs Recommender](#search-vs-recommender)
  - [Search](#search)
  - [Recommender](#recommender)
- [Why This Overall Approach Works Well](#why-this-overall-approach-works-well)
- [Practical Mental Model](#practical-mental-model)
- [Installation](#installation)
  - [Openalex Api key](#openalex-api-key)
- [References](#references)
  - [General app flow graph](#general-app-flow-graph)
  - [Api Usage](#api-usage)
  - [Abbreviated Response Examples](#abbreviated-response-examples)
  - [Short Response Recommender JSON Schema](#short-response-recommender-json-schema)

## Overview
This application finds relevant researchers by using a simple but effective idea:

If several papers that match a query point to authors who repeatedly share the same topics, those shared topics are a strong signal for the real subject area behind the query. Once those topics are identified, the application can look for other authors who are active in the same topic cluster.

One important challenge is that author-level topics are often too broad to serve as a precise starting point on their own. They usually describe a researcher’s general area, but not always the specific question behind a query. That is why the application takes a detour through works first: works are usually much closer to the actual research problem, and from there the system can infer a more focused topic signature.    

That works quite well because it does not rely on a single keyword match or a single paper. Instead, it uses overlap across multiple search results and multiple authors. In practice, this often reduces noise and surfaces people who are genuinely active in the area, even if their names did not appear in the first paper search.

It is also relatively fast because the process stays compact:

- it starts with a limited work search
- it extracts reference authors from those works
- it derives a small topic set from those authors
- it uses that topic set to fetch a broader but still focused candidate pool

So the application first narrows the problem by topic structure, and only then expands to expert candidates.    

**Note 1**: Although Openalex significantly enhanced their capabilities (i.e. for fuzzy searches) they also switched to an Api key based request with different daily credit costs for different request types (i.e. a list lookup uses less credits than a search and so on). The daily rate limit with 10000 free credits is still very generous but this app tries *not* to burn through the daily credits and to be as credit effective as possible.    
    
**Note 2**: You can find a quick&dirty vibe coded frontend demo for this Api here: [academic-expert-search-demo-frontend](https://github.com/zushicat/academic-expert-search-demo-frontend)    
    
**Note 3**: This is still kind of in construction. Hence, take the current state of the repo with a grain of salt or use it as a starting point for your own implementation.


## Core Principle
At a high level, the application treats the first batch of search results as a way to discover the topic signature of a query.

The rough logic is:

1. Search for works related to the query.
2. Collect the authors of those works.
3. Inspect which topics those authors have in common.
4. Keep the most meaningful shared topics.
5. Use those topics to find more authors.
6. Rank or refine the resulting author list depending on the endpoint.

This is why the system is stronger than a plain text search over author names or paper titles. It uses topic overlap as a semantic bridge between the original query and the broader expert landscape.

## Search Endpoint
The `/expert/search` endpoint is the application’s discovery step. Its job is to build a topic-based map of the query and return a broad set of potentially relevant experts.

In general, it does four things:

1. It searches OpenAlex works for the query.
2. It extracts the authors from those works and looks at their topics.
3. It identifies the topics that are most strongly shared across those reference authors.
4. It searches for additional authors who match that topic combination.

The result is a structured response with:

- topics
- works
- institutions
- authors
- metadata about the search

### What Search Is Really Doing
Search is not yet trying to decide who the single best experts are.

Instead, it is building a relevant candidate pool. You can think of it as:

"Given this query, which topics seem to define the area, and which authors appear to belong to that area?"

Authors are then sorted mainly by how many of the selected shared topics they match. This makes the search result useful as a broad expert set, but it is still intentionally generous.

### Why Search Is Useful
The search endpoint is good when you want:

- a topic-grounded set of experts
- the works and institutions around those experts
- transparency into which topics were used
- a broad pool before stronger ranking or filtering

## Recommender Endpoint
The `/expert/recommender` endpoint starts with the search result and then applies stronger filtering and scoring.

So while Search says:

"These authors seem relevant to the topic cluster,"

the Recommender says:

"Among the relevant authors, which ones look strongest as recommendations?"

### What Recommender Adds
After running the search flow, the recommender:

1. filters the search result to keep the stronger topic matches
2. fetches additional works for the remaining authors
3. builds a graph connecting authors, works, topics, and institutions
4. scores authors using multiple signals
5. optionally creates author summaries

The scoring is broader than the Search endpoint. It does not only look at topic overlap, but also considers signals such as:

- topic alignment
- scholarly impact
- productivity
- recency
- connectivity through coauthorship and institutions

That makes the recommender more selective and more opinionated than search.

## Search vs Recommender
The two endpoints are related, but they are not doing the same job.

### Search
Search is mainly for finding the relevant landscape.

- broader result set
- topic-driven discovery
- lighter ranking
- good for inspection and downstream processing

### Recommender
Recommender is mainly for prioritizing the strongest candidates.

- starts from the search result
- applies extra filtering
- enriches authors with more works and relationships
- computes a stronger recommendation score

In short:

- Search finds the relevant space.
- Recommender ranks the best candidates inside that space.

## Why This Overall Approach Works Well
The application performs well because it combines two useful ideas:

- text search to find an initial foothold
- shared-topic structure to generalize from that foothold

This helps avoid a common problem in expert search: a query can be too narrow, too broad, or phrased differently from the exact terms an expert uses. Shared topics help bridge that gap.

It is also efficient because most of the heavy narrowing happens early. Once the application has identified a compact set of shared topics, later steps can stay focused instead of exploring the full author space.

## Practical Mental Model
A simple way to think about the system is:

- Search asks: "Who belongs in this area?"
- Recommender asks: "Who should rise to the top?"

That separation is useful because it keeps the first step broad and interpretable, while allowing the second step to be more selective and recommendation-oriented.

## Installation
- Copy and/or rename env.example to .env
    - OPENALEX_API_KEY: enter your Openalex Api key
    - The LLM endpoint values: the app uses LiteLLM and needs OpenAi compatible model endpoints. 
        - Default: OSS 120B model via Groq
        - Use values of the provider and model of your choice accordingly
- Build Docker image and start container with docker-compose:
```
$ docker-compose build
$ docker-compose up
```
- You may want to change the port in docker-compose.yml (from now 10101 to i.e. 8000)
- Refer to [Api Usage](docs/api-usage.md) on how to use the Api

### Openalex Api key
Openalex changed to Api key based requests. The requests are still free of charge but you have a (really generous) daily rate limit.    
- See their docs on [Authentication & Pricing](https://developers.openalex.org/guides/authentication)
- When you have an Api key you can check your daily consumption: ```https://api.openalex.org/rate-limit?api_key=<your Api key>```

## References
### General app flow graph
- [App Flow image](docs/app-flow-d2.png)
- [App Flow D2 graph](docs/app-flow.d2)
### Api Usage
- [Api Usage](docs/api-usage.md)
### Abbreviated Response Examples
- [Short Search Response (abbreviated)](docs/abbr_short_search_response.json)
- [Short Recommender Response (abbreviated)](docs/abbr_short_recommender_response.json)
### Short Response Recommender JSON Schema
- [JSON schema](expert_recommender_short_response.schema.json)
