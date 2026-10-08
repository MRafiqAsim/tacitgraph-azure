"""
Gremlin Traversal Client for PathRAG and GraphRAG Retrieval
===========================================================

Targeted Gremlin traversal queries for Cosmos DB — replaces bulk
graph loading with server-side path finding and neighborhood queries.

Each query is designed for <50 RU and <100ms on Cosmos DB Gremlin.
Queries use server-side filtering (entity types, edge exclusion,
hop limits) to return only what the retrieval layer needs.

"""

import logging
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

logger = logging.getLogger(__name__)

# Structural edges connect entities to chunks/threads — not meaningful
# for path finding or neighborhood exploration.
_DEFAULT_EXCLUDE_EDGES = frozenset(
    {
        "MENTIONED_IN",
        "PARTICIPATED_IN",
        "HAS_ATTACHMENT",
        "PART_OF_THREAD",
    }
)


class GremlinGraphClient:
    """Targeted Gremlin traversal queries for PathRAG and GraphRAG.

    Instead of loading the entire graph into memory, this client runs
    focused traversals from seed entities.  Results are cached with
    TTL for reuse within the same conversation.
    """

    def __init__(self, cosmos_adapter, cache_ttl: int = 300):
        """
        Args:
            cosmos_adapter: CosmosAdapter with Gremlin connection
            cache_ttl: Cache time-to-live in seconds (default 5 min)
        """
        self.cosmos = cosmos_adapter
        self._cache: dict[str, tuple[Any, float]] = {}
        self._cache_ttl = cache_ttl

        # Load entity types from config
        try:
            from tacitgraph.entity_registry import get_entity_node_types, get_structural_edge_types

            self._entity_types = get_entity_node_types()
            self._structural_edges: set[str] | frozenset[str] = get_structural_edge_types()
        except Exception:
            self._entity_types = {
                "ORG",
                "GPE",
                "PERSON",
                "PRODUCT",
                "DOCUMENT",
                "PROJECT",
                "EVENT",
                "LAW",
                "LOC",
                "NORP",
                "CONCEPT",
                "PROCESS",
                "FACILITY",
                "EQUIPMENT",
                "DEPARTMENT",
                "ROLE",
            }
            self._structural_edges = _DEFAULT_EXCLUDE_EDGES

        self._exclude_labels = self._structural_edges | _DEFAULT_EXCLUDE_EDGES
        self._entity_within = ",".join(f"'{t}'" for t in sorted(self._entity_types))

        logger.info(
            f"GremlinGraphClient initialized: {len(self._entity_types)} entity types, "
            f"{len(self._exclude_labels)} excluded edge types"
        )

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    def _cache_get(self, key: str) -> Any | None:
        if key in self._cache:
            value, expiry = self._cache[key]
            if time.time() < expiry:
                return value
            del self._cache[key]
        return None

    def _cache_set(self, key: str, value: Any):
        self._cache[key] = (value, time.time() + self._cache_ttl)

    def clear_cache(self):
        self._cache.clear()

    # ------------------------------------------------------------------
    # 1. Path Finding (PathRAG core)
    # ------------------------------------------------------------------

    def find_paths(
        self,
        source_id: str,
        target_id: str,
        max_hops: int = 3,
        max_paths: int = 5,
    ) -> list[dict]:
        """Server-side path finding between two entities.

        Uses Gremlin repeat/until traversal with:
        - Entity-only nodes (filtered by node_type)
        - Structural edges excluded (MENTIONED_IN, etc.)
        - simplePath() to prevent cycles

        Returns list of paths, each with nodes and edges.
        Estimated cost: 10-30 RU per pair.
        """
        cache_key = f"paths:{min(source_id, target_id)}:{max(source_id, target_id)}:{max_hops}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        safe_source = self.cosmos._safe_gremlin_str(source_id)
        safe_target = self.cosmos._safe_gremlin_str(target_id)
        exclude = ",".join(f"'{e}'" for e in sorted(self._exclude_labels))

        # Gremlin traversal: find paths up to max_hops between two entities
        # Alternating node/edge projections in the path for full details
        query = (
            f"g.V('{safe_source}')"
            f".repeat("
            f"  bothE().not(hasLabel({exclude}))"
            f"  .otherV()"
            f"  .has('node_type', within({self._entity_within}))"
            f"  .simplePath()"
            f")"
            f".until(hasId('{safe_target}').or().loops().is({max_hops}))"
            f".hasId('{safe_target}')"
            f".path()"
            f".by(project('id','name','type').by(id()).by(values('name')).by(values('node_type')))"
            f".by(project('edge_type','weight').by(label()).by(coalesce(values('weight'), constant(1.0))))"
            f".limit({max_paths})"
        )

        try:
            results = self.cosmos._gremlin_query(query)
            paths = self._parse_paths(results)
            self._cache_set(cache_key, paths)
            return paths
        except Exception as e:
            logger.warning(f"Gremlin path query failed ({source_id} → {target_id}): {e}")
            return []

    def find_paths_batch(
        self,
        entity_pairs: list[tuple[str, str]],
        max_hops: int = 3,
        max_paths_per_pair: int = 5,
        max_workers: int = 5,
    ) -> dict[tuple[str, str], list[dict]]:
        """Find paths for multiple entity pairs in parallel.

        Args:
            entity_pairs: List of (source_id, target_id) tuples
            max_hops: Maximum hops per path
            max_paths_per_pair: Max paths to return per pair
            max_workers: Concurrent Gremlin queries

        Returns:
            Dict mapping (source_id, target_id) -> list of paths
        """
        results = {}
        uncached_pairs = []

        # Check cache first
        for s, t in entity_pairs:
            cache_key = f"paths:{min(s, t)}:{max(s, t)}:{max_hops}"
            cached = self._cache_get(cache_key)
            if cached is not None:
                results[(s, t)] = cached
            else:
                uncached_pairs.append((s, t))

        if not uncached_pairs:
            return results

        # Parallel Gremlin queries for uncached pairs
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(self.find_paths, s, t, max_hops, max_paths_per_pair): (s, t)
                for s, t in uncached_pairs
            }
            for future in as_completed(futures):
                pair = futures[future]
                try:
                    results[pair] = future.result()
                except Exception as e:
                    logger.warning(f"Path query failed for {pair}: {e}")
                    results[pair] = []

        return results

    def _parse_paths(self, raw_results: list) -> list[dict]:
        """Parse Gremlin path results into structured dicts.

        Gremlin path().by(node_projection).by(edge_projection) returns
        alternating node, edge, node, edge, ... objects.
        """
        paths = []
        for path_result in raw_results:
            objects = (
                path_result if isinstance(path_result, list) else path_result.get("objects", [])
            )
            nodes = []
            edges = []
            for i, obj in enumerate(objects):
                if i % 2 == 0:
                    # Node projection
                    nodes.append(
                        {
                            "id": obj.get("id", ""),
                            "name": obj.get("name", ""),
                            "type": obj.get("type", ""),
                        }
                    )
                else:
                    # Edge projection
                    weight = obj.get("weight", 1.0)
                    if isinstance(weight, list):
                        weight = weight[0] if weight else 1.0
                    edges.append(
                        {
                            "edge_type": obj.get("edge_type", "RELATED_TO"),
                            "weight": float(weight),
                        }
                    )

            if len(nodes) >= 2:
                paths.append(
                    {
                        "nodes": nodes,
                        "edges": edges,
                        "hop_count": len(nodes) - 1,
                    }
                )
        return paths

    # ------------------------------------------------------------------
    # 2. Entity Neighborhood (GraphRAG local_search)
    # ------------------------------------------------------------------

    def get_entity_neighborhood(
        self,
        entity_id: str,
        limit: int = 30,
    ) -> dict[str, Any]:
        """Get entity properties and semantic neighbors.

        Excludes structural edges (MENTIONED_IN, etc.) to focus on
        meaningful relationships between entities.

        Returns:
            {
                "entity": {"id", "name", "type"},
                "neighbors": [{"id", "name", "type", "edge_type", "weight"}, ...]
            }
        Estimated cost: ~5-10 RU.
        """
        cache_key = f"neighborhood:{entity_id}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        safe_id = self.cosmos._safe_gremlin_str(entity_id)
        exclude = ",".join(f"'{e}'" for e in sorted(self._exclude_labels))

        # Get entity properties
        entity_query = f"g.V('{safe_id}').project('id','name','type').by(id()).by(values('name')).by(values('node_type'))"

        # Get neighbors via non-structural edges
        neighbor_query = (
            f"g.V('{safe_id}')"
            f".bothE().not(hasLabel({exclude}))"
            f".project('edge_type','other_id','other_name','other_type','weight')"
            f".by(label())"
            f".by(otherV().id())"
            f".by(otherV().values('name'))"
            f".by(otherV().values('node_type'))"
            f".by(coalesce(values('weight'), constant(1.0)))"
            f".limit({limit})"
        )

        try:
            entity_results = self.cosmos._gremlin_query(entity_query)
            entity = (
                entity_results[0]
                if entity_results
                else {"id": entity_id, "name": entity_id, "type": "UNKNOWN"}
            )

            neighbor_results = self.cosmos._gremlin_query(neighbor_query)
            neighbors = []
            for r in neighbor_results:
                weight = r.get("weight", 1.0)
                if isinstance(weight, list):
                    weight = weight[0] if weight else 1.0
                neighbors.append(
                    {
                        "id": r.get("other_id", ""),
                        "name": r.get("other_name", ""),
                        "type": r.get("other_type", ""),
                        "edge_type": r.get("edge_type", ""),
                        "weight": float(weight),
                    }
                )

            result = {"entity": entity, "neighbors": neighbors}
            self._cache_set(cache_key, result)
            return result

        except Exception as e:
            logger.warning(f"Neighborhood query failed for {entity_id}: {e}")
            return {
                "entity": {"id": entity_id, "name": entity_id, "type": "UNKNOWN"},
                "neighbors": [],
            }

    # ------------------------------------------------------------------
    # 3. Source Chunks (evidence retrieval)
    # ------------------------------------------------------------------

    def get_source_chunks(self, entity_id: str, limit: int = 20) -> list[str]:
        """Get chunk IDs connected to entity via MENTIONED_IN edges.

        Estimated cost: ~3-5 RU.
        """
        cache_key = f"source_chunks:{entity_id}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        safe_id = self.cosmos._safe_gremlin_str(entity_id)
        query = f"g.V('{safe_id}').outE('MENTIONED_IN').inV().id().limit({limit})"
        logger.info(f"Gremlin source_chunks query: entity_id='{entity_id}', safe_id='{safe_id}'")

        try:
            results = self.cosmos._gremlin_query(query)
            chunk_ids = [str(r) for r in results] if results else []
            logger.info(f"Gremlin source_chunks result: {len(chunk_ids)} chunks for '{entity_id}'")
            self._cache_set(cache_key, chunk_ids)
            return chunk_ids
        except Exception as e:
            logger.warning(f"Source chunks query FAILED for {entity_id}: {e}")
            return []

    def get_source_chunks_batch(
        self,
        entity_ids: list[str],
        limit_per_entity: int = 10,
    ) -> dict[str, list[str]]:
        """Get source chunks for multiple entities.

        Uses individual queries in parallel (Cosmos doesn't support
        multi-V batch with per-vertex limits efficiently).
        Estimated cost: ~3-5 RU per entity.
        """
        result = {}
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = {
                pool.submit(self.get_source_chunks, eid, limit_per_entity): eid
                for eid in entity_ids
            }
            for future in as_completed(futures):
                eid = futures[future]
                try:
                    result[eid] = future.result()
                except Exception:
                    result[eid] = []
        return result

    # ------------------------------------------------------------------
    # 4. Intersection-ranked evidence chunks
    # ------------------------------------------------------------------

    def get_intersection_chunks(
        self,
        entity_ids: list[str],
        max_chunks: int = 20,
        limit_per_entity: int = 20,
    ) -> list[tuple[str, int]]:
        """Get evidence chunks ranked by how many path entities mention them.

        Chunks at the intersection of multiple entities rank first.
        Returns list of (chunk_id, mention_count) sorted descending.
        """
        all_chunks = self.get_source_chunks_batch(entity_ids, limit_per_entity)
        chunk_scores: dict[str, int] = defaultdict(int)
        for _eid, chunks in all_chunks.items():
            for cid in chunks:
                chunk_scores[cid] += 1

        ranked = sorted(chunk_scores.items(), key=lambda x: x[1], reverse=True)
        return ranked[:max_chunks]

    # ------------------------------------------------------------------
    # 5. Entity lookup by ID
    # ------------------------------------------------------------------

    def get_entity(self, entity_id: str) -> dict | None:
        """Get a single entity by ID.

        Estimated cost: ~2 RU.
        """
        cache_key = f"entity:{entity_id}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        safe_id = self.cosmos._safe_gremlin_str(entity_id)
        query = (
            f"g.V('{safe_id}')"
            f".project('id','name','type','mention_count')"
            f".by(id()).by(values('name')).by(values('node_type'))"
            f".by(coalesce(values('mention_count'), constant(0)))"
        )

        try:
            results = self.cosmos._gremlin_query(query)
            if results:
                entity = results[0]
                mc = entity.get("mention_count", 0)
                if isinstance(mc, list):
                    mc = mc[0] if mc else 0
                entity["mention_count"] = int(mc)
                self._cache_set(cache_key, entity)
                return entity
        except Exception as e:
            logger.warning(f"Entity lookup failed for {entity_id}: {e}")
        return None
