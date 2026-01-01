import asyncio
import time
import json
from typing import Dict, Any, List

from models.stream_request_models import StreamEvent, MergedBook

BOOK_DB_MOCK_RESPONSES = [
    [
        {"id": "id_1", "title": "The Black Art of 3D Programming"},
        {"id": "id_2", "title": "When Cats Paint"},
    ],
    [
        {"id": "id_3", "title": "Best Of Asimov"},
        {"id": "id_4", "title": "Building Construction Illustrated"},
    ],
]

TOPICS_DB_MOCK_RESPONSES = [
    [
        {"id": "id_1", "topics": ["programming", "3d game engine"]},
        {"id": "id_2", "topics": ["cats", "art", "painting"]},
    ],
    [
        {"id": "id_3", "topics": ["science fiction", "short stories"]},
        {"id": "id_4", "topics": ["science fiction", "short stories"]},
    ],
]


class StreamRequest:
    def __init__(self):
        pass

    # ************
    # The event data
    # ************
    def _sse_event(self, event: StreamEvent) -> str:
        return f"data: {event.model_dump_json()}\n\n"

    # ************
    # The actual processing call (i.e. from router)
    # ************
    async def process_sse(self):
        try:
            batch_count = min(
                len(BOOK_DB_MOCK_RESPONSES),
                len(TOPICS_DB_MOCK_RESPONSES),
            )

            yield self._sse_event(
                StreamEvent(
                    event="collection_started",
                    batches=batch_count,
                    timestamp=time.time(),
                )
            )

            book_tasks = [
                self.request_book_api(batch_index) for batch_index in range(batch_count)
            ]

            topic_tasks = [
                self.request_topics_api(batch_index)
                for batch_index in range(batch_count)
            ]

            books_batches, topics_batches = await asyncio.gather(
                asyncio.gather(*book_tasks),
                asyncio.gather(*topic_tasks),
            )

            all_books = [book for batch in books_batches for book in batch]
            all_topics = [topic for batch in topics_batches for topic in batch]

            yield self._sse_event(
                StreamEvent(
                    event="collection_completed",
                    books=len(all_books),
                    topics=len(all_topics),
                    timestamp=time.time(),
                )
            )

            yield self._sse_event(
                StreamEvent(event="merge_started", timestamp=time.time())
            )

            merged = self.merge_data(all_books, all_topics)

            yield self._sse_event(
                StreamEvent(
                    event="final_result",
                    result=merged,
                    timestamp=time.time(),
                )
            )

        except Exception as e:
            yield self._sse_event(
                StreamEvent(
                    event="error",
                    message=str(e),
                    timestamp=time.time(),
                )
            )

    # ************
    # Simulate a more complex processing pipeline
    # ************
    async def request_book_api(self, batch_index: int) -> List[Dict[str, Any]]:
        await asyncio.sleep(2)
        return BOOK_DB_MOCK_RESPONSES[batch_index]

    async def request_topics_api(self, batch_index: int) -> List[Dict[str, Any]]:
        await asyncio.sleep(2)
        return TOPICS_DB_MOCK_RESPONSES[batch_index]

    def merge_data(
        self,
        books: List[Dict[str, Any]],
        topics: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        time.sleep(3)

        topic_index = {item["id"]: item.get("topics", []) for item in topics}

        merged = []
        for book in books:
            merged.append(
                {
                    "id": book["id"],
                    "title": book.get("title"),
                    "topics": topic_index.get(book["id"], []),
                }
            )

        return merged
