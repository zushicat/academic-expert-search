import asyncio
import csv
from io import StringIO
import json
import os
from typing import Dict, Any, List, Set, Tuple
import warnings

# import classes.LlmRequestHandler
from helpers.filehandler import read_text_file
from helpers.toon import encode_toon, decode_toon

from models.expert_recommender_models import ExpertRecommender_Authors
from models.expert_search_models import ExpertSearch_Works

import litellm

warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")
warnings.filterwarnings("ignore", category=RuntimeWarning, module="litellm")

litellm.drop_params = True
# litellm.suppress_debug_info = True

# ******************************
# model configs from environment
# ******************************
TIMEOUT = 20

LLM_QUERY_EXPANSION_MODEL = os.environ["LLM_QUERY_EXPANSION_MODEL"]
LLM_QUERY_EXPANSION_BASE_URL = os.environ["LLM_QUERY_EXPANSION_BASE_URL"]
LLM_QUERY_EXPANSION_API_KEY = os.environ["LLM_QUERY_EXPANSION_API_KEY"]

LLM_QUERY_EXPANSION_MODEL = "openai/qwen/qwen3-32b"
LLM_QUERY_EXPANSION_REASONING_EFFORT = "none"


class ExpertQuery:
    def __init__(self):
        self.class_name = self.__class__.__name__
        self.prompt_template = read_text_file(
            file_path=f"{self.class_name}/prompts/query_expansion.txt"
        )

    async def expand_query(self, query: str):
        # print(query)
        # print("-" * 50)
        prompt = self.prompt_template.format(QUERY=query)
        # print(prompt)
        # print()

        response = await self._process_prompt(prompt=prompt)
        response = response.strip()

        new_queries = response.split("\n")
        limit = 20
        year_cutoff = 2020
        request_urls = []
        for q in new_queries:
            print(f"--> {q}")
            request_urls.append(
                f"https://api.openalex.org/works?filter=title_and_abstract.search:{q},type:article,publication_year:>{year_cutoff-1}&per_page={limit}&select=ids,title,publication_year,relevance_score,authorships,primary_topic"
            )

        print()
        print(json.dumps(request_urls, ensure_ascii=False, indent=2))

    # *********
    #
    # *********
    async def _process_prompt(self, prompt: str) -> Dict[str, Any]:
        response = await self._request_llm(
            prompt=prompt,
            model=LLM_QUERY_EXPANSION_MODEL,
            api_key=LLM_QUERY_EXPANSION_API_KEY,
            base_url=LLM_QUERY_EXPANSION_BASE_URL,
            reasoning_effort=LLM_QUERY_EXPANSION_REASONING_EFFORT,
        )

        return response

    async def _request_llm(
        self,
        prompt: str,
        model: str,
        api_key: str | None,
        base_url: str,
        reasoning_effort: str,
        temperature: float = 0.2,
        timeout: int = TIMEOUT,
    ) -> str:
        litellm_params = {
            "model": model,
            "temperature": temperature,
            "api_key": api_key,
            "reasoning_effort": reasoning_effort,
        }

        if base_url:
            litellm_params["api_base"] = base_url

        litellm_params["messages"] = [
            {"role": "user", "content": prompt},
        ]

        try:
            # response = litellm.completion(**litellm_params, timeout=20)
            response = await litellm.acompletion(**litellm_params, timeout=timeout)
            content = response.choices[0].message.get("content")

            return content
        except Exception as e:
            raise RuntimeError(f"{self.class_name} LLM request failed: {e}")


if __name__ == "__main__":
    query = "Transformers without Normalization"
    # query = "spruce forest drought"
    # query = "wild bee population decline bee monitoring"
    # query = "Forest and woodland stand structural complexity"
    # query = "Deep learning"

    # queries = [
    #     "Ein Land im Blackout Die Internet-Abschaltung im Iran ist deutlich umfassender als bei früheren Protesten. Einige finden trotzdem Wege, denn Sichtbarkeit entscheidet über Leben und Freiheit."
    #     "Proteste in Iran spitzen sich zu – offenbar kein Internet mehr Landesweit gehen die Menschen auf die Straße. Sie rufen Parolen, die einen Sturz der islamischen Republik fordern."
    # ]
    # query = " ".join(queries)

    query_expander = ExpertQuery()
    asyncio.run(query_expander.expand_query(query=query))
