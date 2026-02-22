"""
YantraOS — Vector Memory Module (ChromaDB)
Model Route: Gemini 3.1 Pro (High)

Implements local ChromaDB instance for storing successful execution paths,
enabling One-Shot Learning. When the daemon determines a successful sequence
of commands, it stores the execution path as an embedding. Before generating
new code, it queries the store for semantic similarity to retrieve verified
past solutions.

Usage:
    from core.memory import VectorMemory

    memory = VectorMemory()
    memory.store_execution("deploy-react-app", steps, result="success")
    similar = memory.recall("deploy a React application")
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("yantra.memory")


@dataclass
class ExecutionRecord:
    """A stored execution path with metadata."""
    id: str
    task: str
    steps: list[str]
    result: str              # "success", "failure", "partial"
    context: dict = field(default_factory=dict)
    timestamp: str = ""
    similarity: float = 0.0  # Set during recall


@dataclass
class RecallResult:
    """Result of a semantic similarity search."""
    records: list[ExecutionRecord]
    query: str
    search_time_ms: int
    total_stored: int


class VectorMemory:
    """
    Local ChromaDB vector store for Skill Acquisition via RAG.

    The memory system implements One-Shot Learning:
        1. After successful task execution → store the execution path
        2. Before generating new code → query for similar past solutions
        3. High-similarity match → retrieve verified solution
        4. Creates permanent skill retention

    Storage location: /var/lib/yantra/chroma (configurable)
    """

    def __init__(
        self,
        persist_directory: str = "/var/lib/yantra/chroma",
        collection_name: str = "yantra_executions",
        similarity_threshold: float = 0.85,
        max_results: int = 5,
    ):
        """
        Initialize ChromaDB vector memory.

        Args:
            persist_directory: Path for persistent ChromaDB storage.
            collection_name: Name of the ChromaDB collection.
            similarity_threshold: Minimum cosine similarity for recall (0-1).
            max_results: Maximum results to return from recall.
        """
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.similarity_threshold = similarity_threshold
        self.max_results = max_results

        # Initialize ChromaDB
        try:
            import chromadb
            from chromadb.config import Settings

            os.makedirs(persist_directory, exist_ok=True)

            self.client = chromadb.PersistentClient(
                path=persist_directory,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=False,
                ),
            )

            # Get or create the collection
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={
                    "description": "YantraOS execution paths for one-shot learning",
                    "hnsw:space": "cosine",
                },
            )

            count = self.collection.count()
            logger.info(
                f"ChromaDB initialized: {persist_directory}, "
                f"collection='{collection_name}', "
                f"records={count}"
            )

        except ImportError:
            logger.error("chromadb not installed. Vector memory unavailable.")
            raise
        except Exception as e:
            logger.error(f"ChromaDB initialization failed: {e}")
            raise

    def store_execution(
        self,
        task: str,
        steps: list[str],
        result: str = "success",
        context: Optional[dict] = None,
    ) -> str:
        """
        Store a successful execution path as a vector embedding.

        Args:
            task: Description of the task executed.
            steps: Ordered list of commands/actions taken.
            result: Outcome — "success", "failure", or "partial".
            context: Optional metadata (model used, duration, etc.)

        Returns:
            The generated record ID.
        """
        # Generate deterministic ID from task + steps
        content_hash = hashlib.sha256(
            f"{task}:{json.dumps(steps)}".encode()
        ).hexdigest()[:16]

        record_id = f"exec_{content_hash}"
        timestamp = datetime.now(timezone.utc).isoformat()

        # Build the document text for embedding
        document = self._build_document(task, steps, result)

        # Build metadata
        metadata = {
            "task": task,
            "result": result,
            "step_count": len(steps),
            "timestamp": timestamp,
        }
        if context:
            # ChromaDB metadata values must be str, int, float, or bool
            for key, value in context.items():
                if isinstance(value, (str, int, float, bool)):
                    metadata[f"ctx_{key}"] = value

        try:
            # Upsert (update if same task+steps already stored)
            self.collection.upsert(
                ids=[record_id],
                documents=[document],
                metadatas=[metadata],
            )

            logger.info(
                f"Stored execution: id={record_id}, task='{task}', "
                f"steps={len(steps)}, result={result}"
            )
            return record_id

        except Exception as e:
            logger.error(f"Failed to store execution: {e}")
            raise

    def recall(
        self,
        query: str,
        n_results: Optional[int] = None,
        filter_result: Optional[str] = None,
    ) -> RecallResult:
        """
        Search for similar past execution paths.

        Args:
            query: Natural language description of the current task.
            n_results: Max results to return. Defaults to self.max_results.
            filter_result: Filter by result type ("success", "failure").

        Returns:
            RecallResult with matching ExecutionRecords.
        """
        start_time = time.monotonic()

        if n_results is None:
            n_results = self.max_results

        # Build query filters
        where_filter = None
        if filter_result:
            where_filter = {"result": filter_result}

        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )

            records: list[ExecutionRecord] = []

            if results and results["ids"] and results["ids"][0]:
                for i, record_id in enumerate(results["ids"][0]):
                    # ChromaDB returns distances, not similarities
                    # For cosine: similarity = 1 - distance
                    distance = results["distances"][0][i]
                    similarity = 1.0 - distance

                    # Filter by similarity threshold
                    if similarity < self.similarity_threshold:
                        continue

                    metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                    document = results["documents"][0][i] if results["documents"] else ""

                    # Parse steps from document
                    steps = self._parse_steps(document)

                    records.append(ExecutionRecord(
                        id=record_id,
                        task=metadata.get("task", ""),
                        steps=steps,
                        result=metadata.get("result", "unknown"),
                        context={
                            k.replace("ctx_", ""): v
                            for k, v in metadata.items()
                            if k.startswith("ctx_")
                        },
                        timestamp=metadata.get("timestamp", ""),
                        similarity=round(similarity, 4),
                    ))

            search_time_ms = int((time.monotonic() - start_time) * 1000)

            logger.info(
                f"Recall: query='{query[:50]}...', "
                f"found={len(records)}, "
                f"time={search_time_ms}ms"
            )

            return RecallResult(
                records=records,
                query=query,
                search_time_ms=search_time_ms,
                total_stored=self.collection.count(),
            )

        except Exception as e:
            logger.error(f"Recall failed: {e}")
            search_time_ms = int((time.monotonic() - start_time) * 1000)
            return RecallResult(
                records=[],
                query=query,
                search_time_ms=search_time_ms,
                total_stored=0,
            )

    def _build_document(self, task: str, steps: list[str], result: str) -> str:
        """Build a text document for embedding from task components."""
        parts = [
            f"Task: {task}",
            f"Result: {result}",
            "Steps:",
        ]
        for i, step in enumerate(steps, 1):
            parts.append(f"  {i}. {step}")

        return "\n".join(parts)

    def _parse_steps(self, document: str) -> list[str]:
        """Parse steps from a stored document."""
        steps = []
        in_steps = False
        for line in document.split("\n"):
            if line.strip() == "Steps:":
                in_steps = True
                continue
            if in_steps and line.strip():
                # Remove step numbering
                step = line.strip()
                if step[0].isdigit() and ". " in step:
                    step = step.split(". ", 1)[1]
                steps.append(step)
        return steps

    def count(self) -> int:
        """Return the total number of stored execution records."""
        return self.collection.count()

    def delete(self, record_id: str) -> None:
        """Delete a specific execution record."""
        try:
            self.collection.delete(ids=[record_id])
            logger.info(f"Deleted record: {record_id}")
        except Exception as e:
            logger.error(f"Failed to delete record {record_id}: {e}")

    def clear(self) -> None:
        """Clear all stored execution records. USE WITH CAUTION."""
        try:
            # ChromaDB doesn't have a clear method — delete and recreate
            self.client.delete_collection(self.collection_name)
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={
                    "description": "YantraOS execution paths for one-shot learning",
                    "hnsw:space": "cosine",
                },
            )
            logger.warning("Vector memory cleared — all execution records deleted.")
        except Exception as e:
            logger.error(f"Failed to clear memory: {e}")

    def get_stats(self) -> dict:
        """Get memory store statistics."""
        count = self.count()
        return {
            "provider": "chromadb",
            "persist_directory": self.persist_directory,
            "collection": self.collection_name,
            "total_records": count,
            "similarity_threshold": self.similarity_threshold,
        }
