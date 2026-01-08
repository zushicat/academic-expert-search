"""
LLM Request Handler using LiteLLM for flexibility across providers.

**API Key Handling:**
This handler automatically retrieves the required API key from the 'settings.config'
object based on the provided 'service' name. It expects the keys to be named
following the pattern UPPERCASE_SERVICE_NAME_API_KEY within the config object
(e.g., GROQ_API_KEY, OPENAI_API_KEY).

If the corresponding key is not found or is empty in the config object,
an error will be raised during initialization.

**Caching:**
Relies on LiteLLM's built-in caching. Configure it globally before using this handler.
Example:
import litellm
litellm.cache = litellm.Cache(type="local", ttl=3600)

See LiteLLM documentation for more caching options.
"""

import asyncio
import json
import os
import time
from typing import Dict, Any, Optional, Union, List
import traceback  # For detailed error logging

import litellm
from settings import config

from helpers.filehandler import read_text_file

# Optional: Configure LiteLLM settings globally if needed
# litellm.set_verbose = True
# litellm.drop_params = True

import logging

logging.getLogger("LiteLLM").setLevel(logging.WARNING)


class LlmRequestHandler:
    """
    Generic LLM API handler using LiteLLM. Automatically loads API keys from
    settings.config and relies on LiteLLM's external caching configuration.
    """

    def __init__(
        self,
        model: str,
        service: str,
        api_base: Optional[str] = None,  # Keep if needed for custom endpoints
        use_reranker: bool = False,
    ):
        """
        Initialize the LiteLLM request handler.

        Args:
            model: The base model identifier (e.g., 'llama3-70b-8192', 'gpt-4o-mini').
            service: LLM service provider prefix (e.g., 'groq', 'openai', 'anthropic').
                     Used to construct the full LiteLLM model name and find the API key.
            # api_base: Optional API base URL override for LiteLLM.

        Raises:
            ValueError: If the API key for the specified service is not found or is empty
                        in the settings.config object.
        """
        self.base_model = model

        # auto-load API key from settings.config
        self.api_key = self._get_api_key_from_config(service)
        self.api_base = api_base

        if service in ["rz", "openwebui", "litellm"]:
            if use_reranker:
                service = "cohere"
                self.api_base = f"{self.api_base}/rerank"
            else:
                service = "openai"

        self.service = service.lower()
        self.litellm_model = f"{self.service}/{self.base_model}"

        print(
            f"Initialized LlmRequestHandler for model: {self.litellm_model}. API key loaded for '{self.service}'."
        )
        if self.api_base:
            print(f"Using provided API base URL override: {self.api_base}")
        print("-")

    def _get_api_key_from_config(self, service: str) -> str:
        """
        Retrieves the API key for the given service from the settings.config object.

        Args:
            service: The name of the service (e.g., 'groq', 'openai').

        Returns:
            The API key string.

        Raises:
            ValueError: If the key is not found or is empty/None in config.
        """
        key_variable_name = f"{service.upper()}_API_KEY"
        try:
            # Access the attribute dynamically from the imported config object
            api_key = getattr(config, key_variable_name, None)

            if not api_key:  # Checks for None or empty string
                raise ValueError(
                    f"API key for service '{service}' not found or is empty. "
                    f"Ensure '{key_variable_name}' is set correctly in your "
                    f"environment variables and loaded into settings.config."
                )
            return api_key
        except AttributeError:
            # This case might be redundant if getattr default is None, but good practice
            raise ValueError(
                f"API key variable '{key_variable_name}' not found in settings.config "
                f"for service '{service}'. Check your settings.py and environment."
            )
        except Exception as e:
            # Catch other potential errors during config access
            raise ValueError(
                f"Error accessing API key for service '{service}' from settings.config: {e}"
            )

    # *****
    #
    # *****
    def load_prompt_template(self, file_path: str) -> str:
        """Load a prompt template from a file."""
        # if not os.path.exists(file_path):
        #     raise FileNotFoundError(f"Prompt template file not found: {file_path}")
        return read_text_file(file_path)

    def format_prompt(self, template: str, variables: Dict[str, Any]) -> str:
        """
        Format a prompt template by replacing placeholders.
        Assumes placeholders are in the format {key}.
        """
        try:
            formatted_prompt = template
            for key, value in variables.items():
                placeholder = f"{{{key}}}"
                if placeholder in formatted_prompt:
                    formatted_prompt = formatted_prompt.replace(placeholder, str(value))
            return formatted_prompt
        except KeyError as e:
            print(f"Error: Missing variable {e} needed by the prompt template.")
            raise
        except Exception as e:
            print(f"Error during prompt formatting: {e}")
            return template

    async def request(
        self,
        prompt_or_messages: Union[str, List[Dict[str, str]]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        force_json: bool = False,
        timeout: int = 60,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Make an asynchronous request to the LLM via LiteLLM.

        If force_json=True, it specifically requests JSON output format.
        If force_json=False, it will still *attempt* to parse the response as JSON
        if the model happened to return valid JSON based on prompt instructions.

        Args:
            prompt_or_messages: A single prompt string or a list of message dictionaries.
            temperature: Sampling temperature.
            max_tokens: Maximum number of tokens to generate.
            force_json: If True, specifically request JSON output format.
            timeout: Request timeout in seconds.
            **kwargs: Additional valid parameters for litellm.completion.

        Returns:
            - If successful and output is valid JSON (either forced or naturally):
              The parsed JSON dictionary/object.
            - If successful and output is not valid JSON:
              A dictionary {'text': <response_string>}.
            - If force_json=True and parsing fails:
              A dictionary {'text': <response_string>, 'warning': 'Failed to parse JSON'}.
            - On API error or other failure: An empty dictionary {}.
        """
        # ... (message preparation logic remains the same) ...
        if isinstance(prompt_or_messages, str):
            messages = [{"role": "user", "content": prompt_or_messages}]
        else:
            messages = prompt_or_messages

        litellm_params = {
            "model": self.litellm_model,
            "messages": messages,
            "temperature": temperature,
            "api_key": self.api_key,
            **kwargs,
        }

        # print(litellm_params)

        if max_tokens is not None:
            litellm_params["max_tokens"] = max_tokens
        if force_json:
            litellm_params["response_format"] = {"type": "json_object"}
        if self.api_base:
            litellm_params["api_base"] = self.api_base

        try:
            response = await litellm.acompletion(**litellm_params, timeout=timeout)

            if not response or not response.choices:
                print(
                    f"Error: LiteLLM response for {self.litellm_model} missing choices."
                )
                return {}

            content = response.choices[0].message.get("content")

            if content is None:
                print(
                    f"Warning: LiteLLM returned None content for {self.litellm_model}."
                )
                # Return empty text if content is None
                return {"text": ""}

            # --- PARSING LOGIC ---
            if force_json:
                # Behavior when JSON was explicitly requested
                try:
                    parsed_json = json.loads(content)
                    return parsed_json  # Return parsed JSON directly
                except json.JSONDecodeError:
                    print(
                        f"Warning: Failed to parse JSON response from {self.litellm_model} despite requesting JSON format."
                    )
                    # Return raw text with warning
                    return {"text": content, "warning": "Failed to parse JSON"}
                except TypeError:
                    print(
                        f"Warning: Expected string content for JSON parsing from {self.litellm_model}, got {type(content)}."
                    )
                    # Return stringified content with warning
                    return {
                        "text": str(content),
                        "warning": "Received non-string content for JSON parsing",
                    }
            else:
                if content.startswith("```"):  # check for markdown output
                    # Behavior when JSON was NOT explicitly requested
                    # but the model returned a JSON code block
                    try:
                        content = content[3:-3]  # Remove code block markers
                        if content.startswith("json"):
                            content = content[5:]
                        # Attempt to parse the content as JSON
                        parsed_json = json.loads(content)
                        return parsed_json
                    except json.JSONDecodeError:
                        print(
                            f"Warning: Failed to parse JSON code block from {self.litellm_model}."
                        )
                        return {"text": content}

                # print("---->", content)  # debug
                # Behavior when JSON was NOT explicitly requested via param
                # BUT, we still try to parse it in case the prompt instructions worked
                try:
                    # Attempt to parse the content as JSON
                    parsed_json = json.loads(content)
                    # If successful, return the parsed dictionary directly
                    return parsed_json
                except (json.JSONDecodeError, TypeError):
                    # If it fails (it's likely just plain text, or non-string), return it as plain text
                    return {"text": str(content)}  # Ensure content is stringified

        # --- Error Handling (remains the same) ---
        except litellm.exceptions.AuthenticationError as e:
            print(
                f"LiteLLM Authentication Error for {self.litellm_model}: {e}. Key loaded from config might be invalid."
            )
            return {}
        except ValueError as e:
            print(f"Initialization Error: {e}")
            raise
        except Exception as e:
            print(
                f"An unexpected error occurred during LiteLLM request or processing for {self.litellm_model}:"
            )
            print(f"{e}")
            # traceback.print_exc()
            return {}

    # *****
    #
    # *****
    def request_embeddings(
        self,
        input: List[str],
        timeout: int = 60,
    ):
        litellm_params = {
            "model": self.litellm_model,
            "input": input,
            "api_key": self.api_key,
            "api_base": self.api_base,
        }

        response = litellm.embedding(**litellm_params, timeout=timeout)

        return response.json()

    # *****
    #
    # *****
    def request_reranking(
        self,
        query: str,
        documents: List[str],
        top_n: int = 1,
        timeout: int = 60,
    ):
        litellm_params = {
            "model": self.litellm_model,
            "query": query,
            "documents": documents,
            "top_n": top_n,
            "api_key": self.api_key,
            "api_base": self.api_base,
        }

        response = litellm.rerank(**litellm_params, timeout=timeout)
        response = response.model_dump_json()

        if type(response) == str:
            try:
                response = json.loads(response)
            except:
                return {}

        return response


# --- Example Usage ---
if __name__ == "__main__":

    # --- Configure LiteLLM Caching Globally ---
    # print("Configuring LiteLLM global in-memory cache...")
    # litellm.cache = litellm.Cache(type="local", ttl=3600 * 24, maxsize=1000)

    async def generate():
        # --- Initialize Handlers (API keys now loaded automatically from settings.config) ---
        try:
            # service = "openwebui"
            # model = "openai/gpt-5-codex-llmlb"

            service = "litellm"
            model = "gpt-oss-120b-llmlb"

            # service = "groq"
            # model = "openai/gpt-oss-120b"

            # service = "anthropic"
            # model = "claude-haiku-4-5-20251001"

            # service = "openai"
            # model = "gpt-5-mini-2025-08-07"

            # service = "openrouter"
            # model = "google/gemini-3-pro-preview"

            llm_handler = LlmRequestHandler(
                model=model,
                service=service,
                api_base=getattr(config, f"{service.upper()}_API_BASE", None),
            )

        except ValueError as e:
            print(f"Failed to initialize LlmRequestHandler: {e}")
            return  # Exit if initialization fails

        formatted_prompt = (
            "tell me a faboulous story about cats and dogs in 3 sentences"
        )

        # --- Test ---
        print("\n--- Testing ---")

        start_time = time.time()

        # padjust arameters to respective model if necessary
        response = await llm_handler.request(
            prompt_or_messages=formatted_prompt,
            # temperature=1,
            # max_tokens=500,
            # force_json=False,
            # reasoning_effort="low",
        )

        timed = time.time() - start_time
        print(f"Time: {timed:.2f}s")
        print("Response:")
        print(json.dumps(response, indent=2, ensure_ascii=False))

    def embedding():
        # --- Initialize Handlers (API keys now loaded automatically from settings.config) ---
        try:
            service = "litellm"
            model = "bge-m3-llmlb"

            # service = "openai"
            # model = "text-embedding-3-small"

            llm_handler = LlmRequestHandler(
                model=model,
                service=service,
                api_base=getattr(config, f"{service.upper()}_API_BASE", None),
            )

        except ValueError as e:
            print(f"Failed to initialize LlmRequestHandler: {e}")
            return  # Exit if initialization fails

        input = ["example text", "more example text"]

        # --- Test ---
        print("\n--- Testing ---")

        start_time = time.time()

        # padjust arameters to respective model if necessary
        response = llm_handler.request_embeddings(
            input=input,
        )

        timed = time.time() - start_time
        print(f"Time: {timed:.2f}s")
        print("Response:")
        print(json.dumps(response, indent=2, ensure_ascii=False))

    def reranker():
        # --- Initialize Handlers (API keys now loaded automatically from settings.config) ---
        try:
            service = "litellm"
            model = "bge-reranker-v2-m3-llmlb"

            # service = "cohere"
            # model = "rerank-v3.5"

            llm_handler = LlmRequestHandler(
                model=model,
                service=service,
                api_base=getattr(config, f"{service.upper()}_API_BASE", None),
                use_reranker=True,
            )

        except ValueError as e:
            print(f"Failed to initialize LlmRequestHandler: {e}")
            return  # Exit if initialization fails

        # query = "My dog is cute."
        # documents = [
        #     "The car is brand new.",
        #     "The chihuaha is really tiny.",
        # ]
        # top_n = len(documents)

        query = "Wie gefährlich ist die neue Rebkrankheit „Goldgelbe Vergilbung“. Keywords: Flavescence dorée, grapevine disease, viticulture"
        documents = [
            "Pollution and Contaminants (air, water, soil, PFAS, microplastics, heavy metals)",
            "Renewable Energy, Carbon Capture and Emissions Reduction",
            "Sustainable Agriculture and Food Production",
        ]
        top_n = 1

        # --- Test ---
        print("\n--- Testing ---")

        start_time = time.time()

        response = llm_handler.request_reranking(
            query=query, documents=documents, top_n=top_n
        )

        timed = time.time() - start_time
        print(f"Time: {timed:.2f}s")
        print("Response:")
        print(json.dumps(response, indent=2, ensure_ascii=False))

    # asyncio.run(generate())
    embedding()
    # reranker()
