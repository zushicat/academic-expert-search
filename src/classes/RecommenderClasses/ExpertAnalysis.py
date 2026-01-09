import asyncio
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
LLM_ANALYZER_MODEL = os.environ["LLM_ANALYZER_MODEL"]
LLM_ANALYZER_BASE_URL = os.environ["LLM_ANALYZER_BASE_URL"]
LLM_ANALYZER_API_KEY = os.environ["LLM_ANALYZER_API_KEY"]
LLM_ANALYZER_MAX_CONCURRENCY = int(os.environ["LLM_ANALYZER_MAX_CONCURRENCY"])

LLM_ANALYZER_MODEL = "openai/gpt-oss-120b-llmlb"

# LLM_ANALYZER_MODEL = "groq/openai/gpt-oss-120b"
# LLM_ANALYZER_BASE_URL = "https://api.groq.com/openai/v1"
# LLM_ANALYZER_API_KEY = "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"


class ExpertAnalysis:
    def __init__(self):
        self.class_name = self.__class__.__name__

    async def analyze_author(
        self,
        authors: ExpertRecommender_Authors,
        works: ExpertSearch_Works,
        batch_size: int = 5,
    ):
        # ********
        # Prepare data
        # ********
        author_data_batches = self._create_title_batches(
            authors=authors, works=works, batch_size=batch_size
        )

        toon_batches = self._create_toon_batches(
            author_data_batches=author_data_batches
        )

        prompts = self._create_prompts(toon_batches=toon_batches, batch_size=batch_size)

        request_results = await self._request_llm_batches(
            prompts=prompts, max_concurrency=LLM_ANALYZER_MAX_CONCURRENCY
        )

        # print(json.dumps(request_results, ensure_ascii=False))
        # print()
        print(len(request_results))

    # *********
    # data preparation
    # *********
    def _create_toon_batches(self, author_data_batches: Dict[str, Any]) -> List[str]:
        toon_batches: List[str] = []
        for author_data_batche in author_data_batches:
            try:
                toon_batches.append(encode_toon(json_data=author_data_batche))
            except:
                pass

        return toon_batches

    def _create_title_batches(
        self,
        authors: ExpertRecommender_Authors,
        works: ExpertSearch_Works,
        batch_size: int = 5,
    ) -> List[Dict[str, Dict[int, List[str]]]]:
        """
        Create batches of 5 authors per batch.
        Per author collect batches per year with a list of works titles.
            {
                author_id 1:
                {
                    2019: [title 1, title 2, ...], ...
                },
                author_id 1:
                {
                    2019: [title 1, title 2, ...], ...
                }
            }
        """
        author_work_map: Dict[str, Dict[int, List[str]]] = {}

        for author_id, author in authors.root.items():
            if not author.works:
                continue

            per_year: Dict[int, List[str]] = {}

            for work_id in author.works:
                work = works.root.get(work_id)
                if not work:
                    continue

                year = work.publication_year
                title = work.title

                if not isinstance(year, int) or not title:
                    continue

                per_year.setdefault(year, []).append(title)

            if not per_year:
                continue

            # deduplicate and sort titles per year, sort years
            cleaned_per_year: Dict[int, List[str]] = {}
            for year in sorted(per_year.keys()):
                cleaned_per_year[year] = sorted(set(per_year[year]))

            author_work_map[author_id] = cleaned_per_year

        # batch authors in groups of 5
        author_ids = list(author_work_map.keys())
        batches: List[Dict[str, Dict[int, List[str]]]] = []

        for i in range(0, len(author_ids), batch_size):
            batch_ids = author_ids[i : i + batch_size]
            batch = {aid: author_work_map[aid] for aid in batch_ids}
            batches.append(batch)

        return batches

    def _create_prompts(self, toon_batches: List[str], batch_size: int) -> List[str]:
        prompts: List[str] = []
        prompt_template = read_text_file(
            file_path=f"{self.class_name}/prompts/author_works_summary.txt"
        )
        for toon_batch in toon_batches:
            prompt = prompt_template.format(
                toon_batch=toon_batch, batch_size=batch_size
            )
            prompts.append(prompt)

        return prompts

    # *********
    #
    # *********
    async def _request_llm_batches(
        self,
        prompts: List[str],
        max_concurrency: int = 5,
    ) -> Dict[str, Any]:
        semaphore = asyncio.Semaphore(max_concurrency)

        async def bounded_request(prompt: str):
            async with semaphore:
                return await self._request_llm(
                    prompt=prompt,
                    model=LLM_ANALYZER_MODEL,
                    api_key=LLM_ANALYZER_API_KEY,
                    base_url=LLM_ANALYZER_BASE_URL,
                )

        tasks = [bounded_request(prompt) for prompt in prompts]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        results: Dict[str, Any] = {}
        for r in responses:
            try:
                results.update(json.loads(r))
            except Exception:
                try:
                    print("-----> ERROR  1")
                    repaired_json = await self._repair_json_response(json_response=r)
                    results.update(json.loads(repaired_json))
                except Exception as e:
                    print("-----> ERROR  2")
                    # print(f"      {e}")
                    pass

        return results

    async def _repair_json_response(self, json_response: str) -> str:
        """
        Try to let a model repair a buggy json response (from the batch prcessing).
        """
        prompt_template = read_text_file(
            file_path=f"{self.class_name}/prompts/repair_json.txt"
        )
        prompt = prompt_template.format(buggy_json_result=json_response)

        repaired_json = await self._request_llm(
            prompt=prompt,
            model=LLM_ANALYZER_MODEL,
            api_key=LLM_ANALYZER_API_KEY,
            base_url=LLM_ANALYZER_BASE_URL,
        )

        return repaired_json

    async def _request_llm(
        self,
        prompt: str,
        model: str,
        api_key: str,
        base_url: str | None,
        temperature: float = 0.2,
        reasoning_effort: str = "low",
    ) -> str:
        litellm_params = {
            "model": model,
            "temperature": temperature,
            "api_key": api_key,
            "reasoning_effort": reasoning_effort,  # Options: "low", "medium", "high"
        }

        if LLM_ANALYZER_BASE_URL:
            litellm_params["api_base"] = base_url

        litellm_params["messages"] = [
            {"role": "user", "content": prompt},
        ]

        try:
            # response = litellm.completion(**litellm_params, timeout=20)
            response = await litellm.acompletion(**litellm_params, timeout=20)
            content = response.choices[0].message.get("content")

            return content
        except Exception as e:
            raise RuntimeError(f"{self.class_name} LLM request failed: {e}")


if __name__ == "__main__":
    analyzer = ExpertAnalysis()
    prompt = "Tell me a cat joke."
    result = asyncio.run(analyzer._request_llm(prompt=prompt))
    print(result)
