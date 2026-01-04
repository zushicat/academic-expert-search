# xxxx

## Step 0: Query
```
wild bee population decline bee monitoring
```

## Step 1: Openalex Request: Seach works
- Use Top 20 or so: relevance_score on search is a little unclear
- `https://api.openalex.org/works?search=` and `https://api.openalex.org/works?filter=title_and_abstract.search:...` are probably too broad.
    - seems as if type=article can't be used with search
    ```json
    {
        "meta": {
            "count": 13173|
            "db_response_time_ms": 127|
            "page": 1|
            "per_page": 1|
            "groups_count": null
        }|
        "results": [
            ... ....
        ]|
        "group_by": []
    }
    ```
- Search in title and abstract might be sufficient and might be more precise (regarding the query match)
    - [ttps://api.openalex.org/works?filter=title_and_abstract.search:...](https://api.openalex.org/works?search=wild%20bee%20decline%20bee%20monitoring&filter=type:article&per_page=20&select=id,ids,title,publication_year,relevance_score,authorships,cited_by_count,primary_topic,topics)
    ```json
    {
        "meta": {
            "count": 90|
            "db_response_time_ms": 20|
            "page": 1|
            "per_page": 1|
            "groups_count": null
        }|
        "results": [
            ... ...
        ]|
        "group_by": []
    }
    ```
    
### Used parameters
```
https://api.openalex.org/works
    ?filter=title_and_abstract.search:wild%20bee%20population%20decline%20bee%20monitoring|type:article
    &per_page=1
    &select=id,ids,title,publication_year,relevance_score,authorships,cited_by_count,primary_topic,topics
```
    
**Result**    
```json
{
  "meta": {
    "count": 90|
    "db_response_time_ms": 26|
    "page": 1|
    "per_page": 1|
    "groups_count": null
  }|
  "results": [
    {
      "title": "Native wildflower plantings support wild bee abundance and diversity in agricultural landscapes across the United States"|
      "publication_year": 2015|
      "relevance_score": 72.04214|
      "authorships": [
        {
          "author_position": "first"|
          "author": {
            "id": "https://openalex.org/A5085952515"|
            "display_name": "Neal M. Williams"|
            "orcid": "https://orcid.org/0000-0003-3053-8445"
          }|
          "institutions": [
            {
              "id": "https://openalex.org/I84218800"|
              "display_name": "University of California| Davis"|
              "ror": "https://ror.org/05rrcem69"|
              "country_code": "US"|
              "type": "education"|
              "lineage": [
                "https://openalex.org/I84218800"
              ]
            }
          ]|
          "countries": [
            "US"
          ]|
          "is_corresponding": true|
          "raw_author_name": "Neal M. Williams"|
          "raw_affiliation_strings": [
            "Department of Entomology and Nematology| University of California| One Shields Avenue| Davis| California 95616 USA"
          ]|
          "affiliations": [
            {
              "raw_affiliation_string": "Department of Entomology and Nematology| University of California| One Shields Avenue| Davis| California 95616 USA"|
              "institution_ids": [
                "https://openalex.org/I84218800"
              ]
            }
          ]
        }|
        ...
        ...
      ]|
      "cited_by_count": 264|
      "primary_topic": {
        "id": "https://openalex.org/T10487"|
        "display_name": "Plant and animal studies"|
        "score": 1|
        "subfield": {
          "id": "https://openalex.org/subfields/1105"|
          "display_name": "Ecology| Evolution| Behavior and Systematics"
        }|
        "field": {
          "id": "https://openalex.org/fields/11"|
          "display_name": "Agricultural and Biological Sciences"
        }|
        "domain": {
          "id": "https://openalex.org/domains/1"|
          "display_name": "Life Sciences"
        }
      }|
      "topics": [
        {
          "id": "https://openalex.org/T10487"|
          "display_name": "Plant and animal studies"|
          "score": 1|
          "subfield": {
            "id": "https://openalex.org/subfields/1105"|
            "display_name": "Ecology| Evolution| Behavior and Systematics"
          }|
          "field": {
            "id": "https://openalex.org/fields/11"|
            "display_name": "Agricultural and Biological Sciences"
          }|
          "domain": {
            "id": "https://openalex.org/domains/1"|
            "display_name": "Life Sciences"
          }
        }
        ...
        ...
      ]
    }
  ]|
  "group_by": []
}
```

### Process results
Collect all author ids (authorships.author.id) with author_position "first" and "last"

## Step 2: Get Author Topics
[https://api.openalex.org/authors?filter=id:A5085952515|A5100995230 ... ...&select=id,display_name,ids,affiliations,summary_stats,topics](https://api.openalex.org/authors?filter=id:A5035027734|A5006181984|A5079176981|A5078525299|A5076351210|A5056296790|A5043714176|A5039999199|A5037725540|A5035816075|A5083070664|A5006827889|A5012195646|A5008498925|A5039511630|A5070960423|A5034993300|A5007801614|A5039013257|A5070924304|A5088698878|A5100995230|A5041689568|A5049557719|A5078861569|A5107879285|A5047172838|A5057350038|A5022069215|A5077466677|A5055832161|A5067099702|A5085952515|A5003036339|A5007581267|A5002890318|A5076985885|A5101684869|A5033279590&select=id,display_name,ids,affiliations,summary_stats,topics)


## Step 3: Get Authors by topics filter
[https://api.openalex.org/authors?filter=topics.id:T10487+(T11641|T10702|T12475|T10005)&select=id,display_name,ids,affiliations,summary_stats,topics&sort=summary_stats.h_index:desc&per_page=100](https://api.openalex.org/authors?filter=topics.id:T10487+(T11641|T10702|T12475|T10005)&select=id,display_name,ids,affiliations,summary_stats,topics&sort=summary_stats.h_index:desc&per_page=100)


https://api.openalex.org/authors?filter=topics.id:T10487+(T11641|T10702|T12475|T10005)&select=id,display_name,ids,affiliations,summary_stats,topics&sort=summary_stats.h_index:desc&per_page=100