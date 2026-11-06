"""DynamicTopologyGraph: an igraph.Graph that mirrors a SimulationManager through its EventBus events.

Extracted from the `sat_com_dynamic_graph` package of the satgonetem test environment.

Vertices: one per topology object, named str(topology_uniq_id) (TO_CREATED; also created on the fly by a link event).
Edges: one per usable link, with attributes link_id, kind (isl / gsl / utl / gol) and distance_km.
- *_CREATED adds the edge, *_REMOVED deletes it, *_UPDATED refreshes distance_km;
- an ISL updated with temporary_unavailable=True leaves the graph until an update clears it.
The links are also kept in a dict (link_id -> record), the source of truth; igraph only holds the usable ones.
"""
import logging
import math
from dataclasses import dataclass
from typing import Optional

import igraph as ig
from sat_com_application.event_bus.bus import EventBus
from sat_com_application.event_bus.events import Event, EventType

logger = logging.getLogger(__name__)

SPEED_OF_LIGHT_KM_S = 299_792.458

# event type -> (kind, action)
_LINK_EVENTS = {
    EventType.ISL_CREATED: ("isl", "created"),
    EventType.ISL_UPDATED: ("isl", "updated"),
    EventType.ISL_REMOVED: ("isl", "removed"),
    EventType.GSL_CREATED: ("gsl", "created"),
    EventType.GSL_UPDATED: ("gsl", "updated"),
    EventType.GSL_REMOVED: ("gsl", "removed"),
    EventType.UTL_CREATED: ("utl", "created"),
    EventType.UTL_UPDATED: ("utl", "updated"),
    EventType.UTL_REMOVED: ("utl", "removed"),
    EventType.GOL_CREATED: ("gol", "created"),
    EventType.GOL_UPDATED: ("gol", "updated"),
    EventType.GOL_REMOVED: ("gol", "removed"),
}
# kind -> endpoint fields of the event
_ENDPOINT_FIELDS = {
    "isl": ("satellite_a_id", "satellite_b_id"),
    "gsl": ("ground_station_id", "satellite_id"),
    "utl": ("user_terminal_id", "satellite_id"),
    "gol": ("ground_object_a_id", "ground_object_b_id"),
}


@dataclass
class LinkRecord:
    link_id: str
    kind: str
    a: int
    b: int
    distance_km: Optional[float] = None
    usable: bool = True


class DynamicTopologyGraph:
    def __init__(self):
        self.graph = ig.Graph(directed=False)
        self.links: dict[str, LinkRecord] = {}
        self.object_types: dict[int, str] = {}
        self.events_seen = 0

    # ---- EventBus ---- #

    def attach(self, event_bus: EventBus) -> "DynamicTopologyGraph":
        """Subscribes to every link event and to topology object creation/removal.
        Attach before `load_simulation()` so the graph sees the whole topology."""
        for event_type in _LINK_EVENTS:
            event_bus.subscribe(event_type, self._on_event)
        event_bus.subscribe(EventType.TO_CREATED, self._on_event)
        event_bus.subscribe(EventType.TO_REMOVED, self._on_event)
        return self

    async def _on_event(self, event: Event) -> None:
        self.apply(event)

    def apply(self, event: Event) -> None:
        """Applies one event (synchronous: the bus handlers call it, tests can too)."""
        self.events_seen += 1
        if event.type == EventType.TO_CREATED:
            self._vertex(event.topology_object_uniq_id)
            self.object_types[event.topology_object_uniq_id] = event.topology_object_type
            return
        if event.type == EventType.TO_REMOVED:
            self._remove_object(event.topology_object_uniq_id)
            return
        kind, action = _LINK_EVENTS[event.type]
        field_a, field_b = _ENDPOINT_FIELDS[kind]
        a, b = getattr(event, field_a), getattr(event, field_b)
        if action == "created":
            self._add_link(LinkRecord(event.link_id, kind, a, b, getattr(event, "distance_km", None)))
        elif action == "removed":
            self._remove_link(event.link_id)
        else:
            record = self.links.get(event.link_id)
            if record is None:  # an update for a link created before we attached
                record = LinkRecord(event.link_id, kind, a, b)
                self._add_link(record)
            if getattr(event, "distance_km", None) is not None:
                record.distance_km = event.distance_km
                if record.usable:
                    self.graph.es[self._edge_index(record.link_id)]["distance_km"] = event.distance_km
            unavailable = bool(getattr(event, "temporary_unavailable", False))
            if unavailable and record.usable:
                self._drop_edge(record)
            elif not unavailable and not record.usable:
                self._put_edge(record)

    # ---- graph upkeep ---- #

    def _vertex(self, uid: int) -> int:
        name = str(uid)
        try:
            return self.graph.vs.find(name=name).index
        except (ValueError, KeyError):
            self.graph.add_vertex(name=name, uid=uid)
            return self.graph.vcount() - 1

    def _edge_index(self, link_id: str) -> int:
        return self.graph.es.find(link_id=link_id).index

    def _add_link(self, record: LinkRecord) -> None:
        if record.link_id in self.links:
            self._remove_link(record.link_id)
        self.links[record.link_id] = record
        record.usable = False
        self._put_edge(record)

    def _put_edge(self, record: LinkRecord) -> None:
        va, vb = self._vertex(record.a), self._vertex(record.b)
        self.graph.add_edge(va, vb, link_id=record.link_id, kind=record.kind, distance_km=record.distance_km)
        record.usable = True

    def _drop_edge(self, record: LinkRecord) -> None:
        self.graph.delete_edges(self._edge_index(record.link_id))
        record.usable = False

    def _remove_link(self, link_id: str) -> None:
        record = self.links.pop(link_id, None)
        if record is None:
            logger.debug("removal of unknown link %s", link_id)
            return
        if record.usable:
            self._drop_edge(record)

    def _remove_object(self, uid: int) -> None:
        for link_id in [link.link_id for link in self.links.values() if uid in (link.a, link.b)]:
            self._remove_link(link_id)
        try:
            self.graph.delete_vertices(self.graph.vs.find(name=str(uid)).index)
        except (ValueError, KeyError):
            pass
        self.object_types.pop(uid, None)

    # ---- queries ---- #

    def vertex_ids(self, uids) -> list:
        return [self._vertex(uid) for uid in uids]

    def neighbours(self, uid: int) -> set:
        v = self._vertex(uid)
        return {self.graph.vs[n]["uid"] for n in self.graph.neighbors(v)}

    def shortest_path_lengths(self, sources, targets=None, weighted: bool = True) -> list:
        """Matrix [source][target] of shortest-path lengths (km if weighted and every edge has a distance, else hops);
        inf when there is no path."""
        targets = sources if targets is None else targets
        weights = None
        if weighted and self.graph.ecount() and all(d is not None for d in self.graph.es["distance_km"]):
            weights = "distance_km"
        return self.graph.distances(source=self.vertex_ids(sources), target=self.vertex_ids(targets), weights=weights)

    def hop_counts(self, sources, targets=None) -> list:
        return self.shortest_path_lengths(sources, targets, weighted=False)

    def shortest_path_with_latency_ms(self, source: int, target: int) -> tuple[list, float]:
        """Shortest path by distance from `source` to `target`, as the list of topology_uniq_id it goes through,
        and its propagation latency (ms). ([], inf) when there is no path."""
        if self.graph.ecount() == 0:
            return [], math.inf
        source_vertex, target_vertex = self.vertex_ids([source, target])
        vertices = self.graph.get_shortest_path(source_vertex, to=target_vertex, weights="distance_km", output="vpath")
        if not vertices:
            return [], math.inf
        length_km = sum(
            self.graph.es[self.graph.get_eid(a, b)]["distance_km"] for a, b in zip(vertices, vertices[1:])
        )
        return [self.graph.vs[vertex]["uid"] for vertex in vertices], length_km / SPEED_OF_LIGHT_KM_S * 1000

    def propagation_latencies_ms(self, sources, targets) -> list:
        """Matrix [source][target] of the propagation latency (ms) of the shortest path, at the speed of light in
        vacuum; inf when there is no path. Needs a distance on every edge."""
        if self.graph.ecount() and any(distance is None for distance in self.graph.es["distance_km"]):
            raise ValueError("Every link needs a distance_km to compute latencies (hop counts are not latencies).")
        lengths_km = self.shortest_path_lengths(sources, targets, weighted=True)
        return [
            [length / SPEED_OF_LIGHT_KM_S * 1000 if not math.isinf(length) else math.inf for length in row]
            for row in lengths_km
        ]
