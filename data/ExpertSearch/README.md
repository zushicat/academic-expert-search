# xxxx

## Step 0: Query
```
wild bee population decline bee monitoring
```

## Step 1: Openalex Request: Seach works
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
    - [ttps://api.openalex.org/works?filter=title_and_abstract.search:...](https://api.openalex.org/works?search=wild%20bee%20decline%20bee%20monitoring&filter=type:article&per_page=1&select=title|publication_year|relevance_score|authorships|cited_by_count|primary_topic|topics)
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
    &select=title|publication_year|relevance_score|authorships|cited_by_count|primary_topic|topics
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
[https://api.openalex.org/authors?filter=id:A5085952515|A5100995230 ... ...&select=id,display_name,affiliations,summary_stats,topics&per_page=38](https://api.openalex.org/authors?filter=id:A5015695171|A5076351210|A5017487819|A5039999199|A5078525299|A5033279590|A5022069215|A5101684869|A5007801614|A5079176981|A5005192858|A5061655812|A5008498925|A5070927118|A5084349484|A5035816075|A5037725540|A5028598963|A5035027734|A5078861569|A5055832161|A5100995230|A5085477907|A5045082865|A5085952515|A5088698878|A5039013257|A5044410338|A5003036339|A5012301888|A5089895033|A5084859594|A5043714176|A5067099702|A5007581267|A5054459536|A5006181984|A5083070664&select=id,display_name,affiliations,summary_stats,topics&per_page=38)


## Step 3: Get Authors by topics filter
[https://api.openalex.org/authors?filter=topics.id:T10487+T11641+(T10702|T12475|T10005)&select=id|display_name|affiliations|summary_stats|topics&sort=summary_stats.h_index:desc&per_page=100](https://api.openalex.org/authors?filter=topics.id:T10487+T11641+(T10702|T12475|T10005)&select=id,display_name,affiliations,summary_stats,topics&sort=summary_stats.h_index:desc&per_page=100)