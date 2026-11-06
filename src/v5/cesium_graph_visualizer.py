"""
Cesium HTML visualization for networkX graphs representing satellite and ground station networks.
"""

import html
import json
import math
import pathlib
import re
from typing import Any
from typing import Optional, Dict, Tuple

import networkx as nx


def _snake_to_title(key: str) -> str:
    return re.sub(r"_+", " ", key).title()


class HtmlFormatter:
    """
    Html formatter that supports both Pydantic models and raw dicts.
    """

    def __init__(self, data: dict):
        if  isinstance(data, dict):
            self.data = data
        else:
            raise TypeError(
                f"Expected BaseModel or dict, got {type(data)}"
            )

    def format(self) -> str:
        return self._format_dict(self.data)

    def _format_dict(self, data: dict, level: int = 0) -> str:
        html_output = "<table border='1' style='border-collapse: collapse;'>"
        for key, value in data.items():
            readable_key = _snake_to_title(str(key))
            html_output += "<tr>"
            html_output += (
                f"<td style='padding: 4px;'>"
                f"<b>{html.escape(str(readable_key))}</b></td>"
            )
            html_output += "<td style='padding: 4px;'>"
            html_output += self._format_value(value, level + 1)
            html_output += "</td></tr>"
        html_output += "</table>"
        return html_output

    def _format_value(self, value: Any, level: int) -> str:
        if isinstance(value, dict):
            return self._format_dict(value, level)

        elif isinstance(value, list):
            return (
                "<ul>"
                + "".join(
                    f"<li>{self._format_value(v, level)}</li>" for v in value
                )
                + "</ul>"
            )

        else:
            return html.escape(str(value))

class CesiumGraphVisualizer:
    """
    Generates Cesium HTML files for visualizing networkX graphs with geographic positions.
    """
    
    # Color scheme for different node types
    NODE_COLORS = {
        "GroundStation": "RED",
        "Satellite": "BLUE",
        "Walker": "GREEN",
    }
    
    # Color scheme for different edge types
    EDGE_COLORS = {
        "InterSatelliteLink": "CYAN",
        "GroundStationLink": "YELLOW",
        "GroundToGround": "ORANGE",
    }
    
    def __init__(
        self,
        graph: nx.Graph,
        title: str = "Network Graph Visualization",
        cesium_token: Optional[str] = None,
    ):
        """
        Initialize the visualizer with a networkX graph.

        Args:
            graph: A networkX graph with node attributes including 'position' (dict with 'latitude', 'longitude', 'altitude')
            title: Title for the HTML document
            cesium_token: Cesium Ion token (https://ion.cesium.com/tokens). Without one, the
                globe uses the offline Natural Earth imagery shipped with CesiumJS.
        """
        self.graph = graph
        self.title = title
        self.cesium_token = cesium_token

    def _viewer_js(self, animated: bool = False) -> str:
        """JavaScript creating the Cesium `viewer`, with or without the clock widgets."""
        widgets = "true" if animated else "false"
        if self.cesium_token:
            return f"""
        Cesium.Ion.defaultAccessToken = {json.dumps(self.cesium_token)};
        var viewer = new Cesium.Viewer('cesiumContainer', {{
            timeline: {widgets},
            animation: {widgets},
            navigationInstructionsInitiallyVisible: false,
        }});"""
        return f"""
        // No Cesium Ion token: use the offline imagery shipped with CesiumJS.
        var viewer = new Cesium.Viewer('cesiumContainer', {{
            timeline: {widgets},
            animation: {widgets},
            navigationInstructionsInitiallyVisible: false,
            baseLayerPicker: false,
            geocoder: false,
            baseLayer: Cesium.ImageryLayer.fromProviderAsync(
                Cesium.TileMapServiceImageryProvider.fromUrl(
                    Cesium.buildModuleUrl("Assets/Textures/NaturalEarthII")
                )
            ),
        }});"""
    
    def _get_node_color(self, node_data: Dict) -> str:
        """Get color for a node based on its type."""
        node_type = node_data.get("type", "Unknown")
        return self.NODE_COLORS.get(node_type, "WHITE")
    
    def _get_edge_color(self, edge_data: Dict) -> str:
        """Get color for an edge based on its type."""
        edge_type = edge_data.get("type", "Unknown")
        return self.EDGE_COLORS.get(edge_type, "WHITE")
    
    def _extract_position(self, position_data: Dict) -> Tuple[float, float, float]:
        """
        Extract (longitude, latitude, altitude) from position data.
        
        Args:
            position_data: Dictionary with keys 'longitude', 'latitude', 'altitude'
            
        Returns:
            Tuple of (longitude, latitude, altitude)
        """
        lon = position_data.get("longitude", 0.0)
        lat = position_data.get("latitude", 0.0)
        alt = position_data.get("altitude", 0.0)
        return (lon, lat, alt)
    
    def _get_node_position(self, node_data: Dict) -> Tuple[float, float, float]:
        """
        Get node position, checking 'position' first, then 'spatial_position_info' as fallback.
        
        Args:
            node_data: The node data dictionary
            
        Returns:
            Tuple of (longitude, latitude, altitude)
        """
        # Try 'position' first
        position = node_data.get("position")
        if position and isinstance(position, dict):
            return self._extract_position(position)
        
        # Fallback to 'spatial_position_info'
        spatial_info = node_data.get("spatial_position_info")
        if spatial_info and isinstance(spatial_info, dict):
            return self._extract_position(spatial_info)
        
        # Default to (0, 0, 0)
        return (0.0, 0.0, 0.0)
    
    def _create_node_entity(self, node_id: int, node_data: Dict, node_index: int) -> str:
        """
        Create a Cesium entity for a node (satellite or ground station).
        
        Args:
            node_id: The node identifier
            node_data: The node data dictionary
            node_index: Index for unique ID generation
            
        Returns:
            JavaScript code for adding the entity
        """
        lon, lat, alt = self._get_node_position(node_data)
        
        node_type = node_data.get("type", "Unknown")
        color = self._get_node_color(node_data)
        radius = 50000 if node_type == "GroundStation" else 30000
        
        # Create properties for the entity
        properties = {
            "type": node_type,
            "id": node_id,
            "latitude": lat,
            "longitude": lon,
            "altitude": alt,
        }
        
        # Add any additional attributes
        for key, value in node_data.items():
            if key not in ["position", "type"] and isinstance(value, (str, int, float, bool)):
                properties[key] = value
        
        properties_json = json.dumps(properties)
        
        return f"""
    viewer.entities.add({{
        name: "{node_type}: {node_id}",
        id: "node_{node_index}",
        description: "{HtmlFormatter(node_data).format()}",
        properties: {properties_json},
        position: Cesium.Cartesian3.fromDegrees({lon}, {lat}, {alt}),
        ellipsoid: {{
            radii: new Cesium.Cartesian3({radius}, {radius}, {radius}),
            material: Cesium.Color.{color}.withAlpha(0.75),
            outline: true,
            outlineColor: Cesium.Color.{color}
        }},
        label: {{
            text: "{node_id}",
            font: "14px sans-serif",
            pixelOffset: new Cesium.Cartesian2(0, -20),
            fillColor: Cesium.Color.WHITE,
            outlineColor: Cesium.Color.BLACK,
            outlineWidth: 2,
            style: Cesium.LabelStyle.FILL_AND_OUTLINE
        }}
    }});
"""
    
    def _create_edge_entity(self, u: int, v: int, edge_data: Dict, edge_index: int) -> str:
        """
        Create a Cesium entity for an edge (link between nodes).
        
        Args:
            u: Source node
            v: Target node
            edge_data: The edge data dictionary
            edge_index: Index for unique ID generation
            
        Returns:
            JavaScript code for adding the entity
        """
        u_data = self.graph.nodes[u]
        v_data = self.graph.nodes[v]
        
        u_lon, u_lat, u_alt = self._get_node_position(u_data)
        v_lon, v_lat, v_alt = self._get_node_position(v_data)
        
        edge_type = edge_data.get("type", "Unknown")
        color = self._get_edge_color(edge_data)
        
        distance = edge_data.get("distance", 0)
        latency = edge_data.get("latency", 0)
        
        # Create properties for the edge
        properties = {
            "type": edge_type,
            "source": u,
            "target": v,
            "distance": distance,
            "latency": latency,
        }
        
        properties_json = json.dumps(properties)
        
        arc_type = "GEODESIC" if edge_type in ["GroundStationLink", "GroundObjectLink"] else "NONE"
        
        return f"""
    viewer.entities.add({{
        name: "Link {u} -> {v}",
        description: "{edge_type}: {u} to {v} (distance: {distance:.2f} km, latency: {latency:.6f} ms) {HtmlFormatter(edge_data).format()}",
        properties: {properties_json},
        polyline: {{
            positions: Cesium.Cartesian3.fromDegreesArrayHeights([
                {u_lon}, {u_lat}, {u_alt},
                {v_lon}, {v_lat}, {v_alt}
            ]),
            width: 2,
            arcType: Cesium.ArcType.{arc_type},
            material: Cesium.Color.{color}.withAlpha(0.6)
        }}
    }});
"""
    
    def generate_html(self, output_path: Optional[str] = None) -> str:
        """
        Generate the complete HTML file with Cesium visualization.
        
        Args:
            output_path: Path to save the HTML file. If None, returns HTML string.
            
        Returns:
            HTML string if output_path is None, otherwise None
        """
        # Generate node entities
        node_entities = []
        for node_index, (node_id, node_data) in enumerate(self.graph.nodes(data=True)):
            node_entities.append(self._create_node_entity(node_id, node_data, node_index))
        
        # Generate edge entities
        edge_entities = []
        for edge_index, (u, v, edge_data) in enumerate(self.graph.edges(data=True)):
            edge_entities.append(self._create_edge_entity(u, v, edge_data, edge_index))
        
        # Combine all entities
        all_entities = "\n".join(node_entities + edge_entities)
        
        # Get graph statistics
        num_nodes = self.graph.number_of_nodes()
        num_edges = self.graph.number_of_edges()
        
        ground_stations = sum(1 for _, d in self.graph.nodes(data=True) if d.get("type") == "GroundStation")
        satellites = sum(1 for _, d in self.graph.nodes(data=True) if d.get("type") == "Satellite")
        walkers = sum(1 for _, d in self.graph.nodes(data=True) if d.get("type") == "Walker")
        
        # Create the HTML template
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{self.title}</title>
<script src="https://cesium.com/downloads/cesiumjs/releases/1.110/Build/Cesium/Cesium.js"></script>
<link href="https://cesium.com/downloads/cesiumjs/releases/1.110/Build/Cesium/Widgets/widgets.css" rel="stylesheet">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        html, body {{
            width: 100%;
            height: 100%;
            font-family: Arial, sans-serif;
        }}
        #cesiumContainer {{
            width: 100%;
            height: calc(100% - 200px);
            position: relative;
            overflow: hidden;
        }}
        #info-panel {{
            width: 100%;
            height: 200px;
            background-color: #f0f0f0;
            border-top: 2px solid #333;
            overflow-y: auto;
            padding: 20px;
            box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.1);
        }}
        .info-row {{
            display: flex;
            justify-content: space-around;
            margin-bottom: 10px;
            flex-wrap: wrap;
        }}
        .info-item {{
            min-width: 200px;
            padding: 10px;
            background-color: white;
            border-radius: 5px;
            margin: 5px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }}
        .info-label {{
            font-weight: bold;
            color: #333;
        }}
        .info-value {{
            color: #666;
            margin-top: 5px;
        }}
        .color-legend {{
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
            margin-bottom: 15px;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .legend-color {{
            width: 20px;
            height: 20px;
            border-radius: 50%;
            border: 1px solid #333;
        }}
        @import url(https://cesium.com/downloads/cesiumjs/releases/1.104/Widgets/widgets.css);
    </style>
</head>
<body>
    <div id="cesiumContainer"></div>
    <div id="info-panel">
        <h3>{self.title}</h3>
        <div class="color-legend">
            <div class="legend-item">
                <div class="legend-color" style="background-color: #FF0000;"></div>
                <span>Ground Station</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background-color: #0000FF;"></div>
                <span>Satellite</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background-color: #00FF00;"></div>
                <span>Walker Satellite</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background-color: #00FFFF;"></div>
                <span>Inter-Satellite Link</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background-color: #FFFF00;"></div>
                <span>Ground Station Link</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background-color: #FFA500;"></div>
                <span>Ground-to-Ground Link</span>
            </div>
        </div>
        <div class="info-row">
            <div class="info-item">
                <div class="info-label">Total Nodes</div>
                <div class="info-value">{num_nodes}</div>
            </div>
            <div class="info-item">
                <div class="info-label">Total Edges</div>
                <div class="info-value">{num_edges}</div>
            </div>
            <div class="info-item">
                <div class="info-label">Ground Stations</div>
                <div class="info-value">{ground_stations}</div>
            </div>
            <div class="info-item">
                <div class="info-label">SSO Satellites</div>
                <div class="info-value">{satellites}</div>
            </div>
            <div class="info-item">
                <div class="info-label">Walker Satellites</div>
                <div class="info-value">{walkers}</div>
            </div>
        </div>
    </div>

    <script>
{self._viewer_js(animated=False)}

        // Set default view to show the whole Earth
        viewer.camera.setView({{
            destination: Cesium.Cartesian3.fromDegrees(0, 30, 50000000)
        }});

        // Add all entities
{all_entities}

        // Handle entity selection
        var handler = new Cesium.ScreenSpaceEventHandler(viewer.canvas);
        handler.setInputAction(function onLeftClick(movement) {{
            var pickedObject = viewer.scene.pick(movement.position);
            if (Cesium.defined(pickedObject)) {{
                var entity = pickedObject.id;
                if (entity && entity.properties) {{
                    console.log("Selected Entity:", entity.name);
                    console.log("Properties:", entity.properties);
                }}
            }}
        }}, Cesium.ScreenSpaceEventType.LEFT_CLICK);

        // Enable depth testing for better visualization
        viewer.scene.globe.depthTestAgainstTerrain = true;
    </script>
</body>
</html>
"""
        
        if output_path:
            # Create parent directories if needed
            output_file = pathlib.Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, 'w') as f:
                f.write(html_content)
            
            print(f"Cesium HTML file generated: {output_file}")
            return None
        else:
            return html_content


class AnimatedCesiumGraphVisualizer(CesiumGraphVisualizer):
    """
    Generates a time-animated Cesium HTML page from a networkX graph recorded over a
    simulation. Same input as `CesiumGraphVisualizer`, with extra attributes:

    - node `positions`: list of samples `(time, longitude, latitude, altitude_m)`,
      `time` being a `datetime`. Cesium interpolates between samples. A node with
      `static=True` (e.g. a ground station) only needs one sample.
    - node `label_samples` (optional): list of `(time, text)`: the label of the node
      changes over time (e.g. a latency). Defaults to its `name`.
    - node `label_offset` (optional): `(x, y)` pixel offset of the label, to separate
      the labels of close nodes. Defaults to `(0, -18)`.
    - edge `intervals`: list of `(start, end)` datetimes during which the link exists.

    Nodes are colored per `shell` (falls back to `type`), edges per `direction`
    (`orbital`, `adjacent`, `inter_shell`, `ground`).

    `live_values`: `{label: [(time, text), ...]}`, values shown in the info panel,
    each one updated to its latest sample as the clock runs.

    `highlighted_paths`: `{label: {"color": css, "samples": [(time, [node ids])]}}`,
    a path per sample time (e.g. a shortest path computed at each tick). Each hop is
    underlined in the path color until the next sample. Other links are dimmed.

    `time_series`: `{"title": str, "unit": str, "series": {label: {"color": css,
    "samples": [(time, value)]}}}`, drawn as a line chart below the globe, with a
    cursor following the clock. A `None` or infinite value leaves a gap. Click the
    chart to jump to that time.

    `trail_seconds`: length of the trail drawn behind each moving node. 0 draws none.

    The page plays the simulation with Cesium's clock: use the timeline to scrub.
    """

    SHELL_PALETTE = ["#4FC3F7", "#FFB74D", "#81C784", "#E57373", "#BA68C8", "#FFF176"]

    # direction -> (color, legend label)
    LINK_STYLES = {
        "orbital": ("#26C6DA", "orbital ISL"),
        "adjacent": ("#5C6BC0", "adjacent ISL"),
        "inter_shell": ("#FF4081", "inter-shell ISL"),
        "ground": ("#FFEB3B", "ground link"),
    }

    def __init__(
        self,
        graph: nx.Graph,
        start_time,
        end_time,
        title: str = "Animated Network Graph",
        cesium_token: Optional[str] = None,
        trail_seconds: int = 900,
        playback_speed: int = 60,
        live_values: Optional[Dict[str, list]] = None,
        highlighted_paths: Optional[Dict[str, dict]] = None,
        time_series: Optional[dict] = None,
    ):
        super().__init__(graph, title, cesium_token)
        self.start_time = start_time
        self.end_time = end_time
        self.trail_seconds = trail_seconds
        self.playback_speed = playback_speed
        self.live_values = live_values or {}
        self.highlighted_paths = highlighted_paths or {}
        self.time_series = time_series

        groups = sorted({self._node_group(data) for _, data in graph.nodes(data=True)})
        self.group_colors = {
            group: self.SHELL_PALETTE[index % len(self.SHELL_PALETTE)]
            for index, group in enumerate(groups)
        }

    @staticmethod
    def _node_group(node_data: Dict) -> str:
        return str(node_data.get("shell") or node_data.get("type", "Unknown"))

    def _seconds(self, moment) -> float:
        return round((moment - self.start_time).total_seconds(), 3)

    def _text_samples(self, samples) -> list:
        """[(time, text), ...] -> [[seconds, text], ...] sorted by time."""
        return [[self._seconds(moment), str(text)] for moment, text in sorted(samples, key=lambda s: s[0])]

    @staticmethod
    def _static_attributes(data: Dict) -> Dict:
        return {
            key: value
            for key, value in data.items()
            if key not in ("positions", "intervals", "label_samples") and isinstance(value, (str, int, float, bool))
        }

    def _nodes_payload(self) -> list:
        nodes = []
        for node_id, data in self.graph.nodes(data=True):
            samples = []
            for moment, longitude, latitude, altitude in sorted(data.get("positions", []), key=lambda s: s[0]):
                samples += [self._seconds(moment), round(longitude, 5), round(latitude, 5), round(altitude, 1)]
            if not samples:
                continue
            nodes.append(
                {
                    "id": str(node_id),
                    "name": str(data.get("name", node_id)),
                    "group": self._node_group(data),
                    "color": self.group_colors[self._node_group(data)],
                    "static": bool(data.get("static", False)),
                    "description": HtmlFormatter(self._static_attributes(data)).format(),
                    "samples": samples,
                    "labels": self._text_samples(data.get("label_samples", [])),
                    "offset": list(data.get("label_offset", (0, -18))),
                }
            )
        return nodes

    def _edges_payload(self) -> list:
        edges = []
        for u, v, data in self.graph.edges(data=True):
            intervals = [[self._seconds(start), self._seconds(end)] for start, end in data.get("intervals", [])]
            if not intervals:
                continue
            direction = str(data.get("direction", data.get("type", "Unknown")))
            edges.append(
                {
                    "a": str(u),
                    "b": str(v),
                    "direction": direction,
                    "color": self.LINK_STYLES.get(direction, ("#FFFFFF", direction))[0],
                    "description": HtmlFormatter(self._static_attributes(data)).format(),
                    "intervals": intervals,
                }
            )
        return edges

    PATH_WIDTHS = [12, 7, 4]

    @staticmethod
    def _hop_key(a, b) -> tuple:
        a, b = str(a), str(b)
        return (a, b) if a <= b else (b, a)

    def _routes_payload(self) -> list:
        """Each path sample holds until the next one: merge it into per-hop intervals."""
        routes = []
        for index, (label, route) in enumerate(self.highlighted_paths.items()):
            samples = sorted(route["samples"], key=lambda sample: sample[0])
            hops = {}
            for position, (moment, path) in enumerate(samples):
                begin = self._seconds(moment)
                end = self._seconds(samples[position + 1][0] if position + 1 < len(samples) else self.end_time)
                if end <= begin:
                    continue
                for a, b in zip(path, path[1:]):
                    intervals = hops.setdefault(self._hop_key(a, b), [])
                    if intervals and intervals[-1][1] == begin:
                        intervals[-1][1] = end
                    else:
                        intervals.append([begin, end])
            routes.append(
                {
                    "label": label,
                    "color": route["color"],
                    "width": self.PATH_WIDTHS[min(index, len(self.PATH_WIDTHS) - 1)],
                    "hops": [{"a": a, "b": b, "intervals": intervals} for (a, b), intervals in hops.items()],
                }
            )
        return routes

    def _chart_payload(self) -> Optional[dict]:
        if not self.time_series:
            return None

        def clean(value):
            if value is None or (isinstance(value, float) and math.isinf(value)):
                return None
            return round(float(value), 3)

        return {
            "title": self.time_series.get("title", ""),
            "unit": self.time_series.get("unit", ""),
            "series": [
                {
                    "label": label,
                    "color": series["color"],
                    "points": [
                        [self._seconds(moment), clean(value)]
                        for moment, value in sorted(series["samples"], key=lambda sample: sample[0])
                    ],
                }
                for label, series in self.time_series["series"].items()
            ],
        }

    def _link_styles_in_use(self) -> Dict[str, tuple]:
        """The link styles of the directions present in the graph (legend and counters)."""
        directions = {
            str(data.get("direction", data.get("type", "Unknown"))) for _, _, data in self.graph.edges(data=True)
        }
        return {direction: style for direction, style in self.LINK_STYLES.items() if direction in directions}

    def _legend_html(self) -> str:
        items = [
            f'<div class="legend-item"><div class="legend-color" style="background-color: {color};"></div>'
            f"<span>{html.escape(group)}</span></div>"
            for group, color in self.group_colors.items()
        ]
        items += [
            f'<div class="legend-item"><div class="legend-line" style="background-color: {color};"></div>'
            f"<span>{html.escape(label)}</span></div>"
            for color, label in self._link_styles_in_use().values()
        ]
        items += [
            f'<div class="legend-item"><div class="legend-path" style="background-color: {route["color"]};"></div>'
            f"<span>{html.escape(label)}</span></div>"
            for label, route in self.highlighted_paths.items()
        ]
        return "\n".join(items)

    def generate_html(self, output_path: Optional[str] = None) -> Optional[str]:
        live_labels = list(self.live_values)
        payload = json.dumps(
            {
                "start": self.start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "stop": self._seconds(self.end_time),
                "trail": self.trail_seconds,
                "speed": self.playback_speed,
                "nodes": self._nodes_payload(),
                "edges": self._edges_payload(),
                "live": [self._text_samples(self.live_values[label]) for label in live_labels],
                "routes": self._routes_payload(),
                "chart": self._chart_payload(),
            }
        ).replace("</", "<\\/")
        panel_height = 320 if (self.time_series or self.highlighted_paths) else 210
        chart_html = '<div class="panel-chart" id="chart"></div>' if self.time_series else ""

        counters = "".join(
            f'<div class="info-item"><div class="info-label">{html.escape(label)}s</div>'
            f'<div class="info-value" id="count-{direction}">0</div></div>'
            for direction, (_, label) in self._link_styles_in_use().items()
        )
        live_items = "".join(
            f'<div class="info-item live"><div class="info-label">{html.escape(label)}</div>'
            f'<div class="info-value" id="live-{index}">-</div></div>'
            for index, label in enumerate(live_labels)
        )

        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{html.escape(self.title)}</title>
    <script src="https://cdn.jsdelivr.net/npm/cesium@1.110.0/Build/Cesium/Cesium.js"></script>
    <link href="https://cdn.jsdelivr.net/npm/cesium@1.110.0/Build/Cesium/Widgets/widgets.css" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        html, body {{ width: 100%; height: 100%; font-family: Arial, sans-serif; background: #111; }}
        #cesiumContainer {{ width: 100%; height: calc(100% - {panel_height}px); position: relative; overflow: hidden; }}
        #info-panel {{ width: 100%; height: {panel_height}px; background-color: #f0f0f0; border-top: 2px solid #333;
                       overflow-y: auto; padding: 10px 20px; }}
        .panel-grid {{ display: flex; gap: 16px; flex-wrap: wrap; align-items: flex-start; }}
        .panel-info {{ flex: 1 1 520px; min-width: 0; }}
        .panel-chart {{ flex: 1 1 460px; min-width: 0; position: relative; background: #fcfcfb; border-radius: 5px;
                        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1); padding: 8px 10px; color: #0b0b0b; }}
        .chart-title {{ font-weight: bold; font-size: 13px; }}
        .chart-legend {{ display: flex; gap: 14px; font-size: 12px; color: #52514e; margin: 4px 0 2px; }}
        .chart-legend span.swatch {{ display: inline-block; width: 14px; height: 3px; border-radius: 2px;
                                     vertical-align: middle; margin-right: 5px; }}
        .chart-tooltip {{ position: absolute; pointer-events: none; background: #ffffff; border: 1px solid #d9d8d4;
                          border-radius: 4px; padding: 5px 8px; font-size: 12px; color: #0b0b0b; display: none;
                          box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15); white-space: nowrap; }}
        .chart-tooltip .row {{ display: flex; align-items: center; gap: 6px; font-variant-numeric: tabular-nums; }}
        .chart-tooltip .muted {{ color: #52514e; }}
        .legend-path {{ width: 22px; height: 7px; border-radius: 4px; box-shadow: 0 0 6px rgba(0, 0, 0, 0.25); }}
        .info-row {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }}
        .info-item {{ min-width: 140px; padding: 5px 10px; background-color: white; border-radius: 5px;
                      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1); }}
        .info-item.live {{ border-left: 4px solid #FF4081; }}
        .info-label {{ font-weight: bold; color: #333; font-size: 12px; }}
        .info-value {{ color: #444; margin-top: 2px; font-variant-numeric: tabular-nums; }}
        .color-legend {{ display: flex; gap: 18px; flex-wrap: wrap; margin: 4px 0 8px; font-size: 13px; }}
        .legend-item {{ display: flex; align-items: center; gap: 6px; }}
        .legend-color {{ width: 14px; height: 14px; border-radius: 50%; border: 1px solid #333; }}
        .legend-line {{ width: 22px; height: 4px; border-radius: 2px; }}
    </style>
</head>
<body>
    <div id="cesiumContainer"></div>
    <div id="info-panel">
        <h3>{html.escape(self.title)}</h3>
        <div class="panel-grid">
            <div class="panel-info">
                <div class="color-legend">{self._legend_html()}</div>
                <div class="info-row">{live_items}</div>
                <div class="info-row">
                    <div class="info-item"><div class="info-label">Simulation time (UTC)</div><div class="info-value" id="sim-time">-</div></div>
                    {counters}
                </div>
            </div>
            {chart_html}
        </div>
    </div>

    <script>
{self._viewer_js(animated=True)}
        var data = {payload};

        var start = Cesium.JulianDate.fromIso8601(data.start);
        var stop = Cesium.JulianDate.addSeconds(start, data.stop, new Cesium.JulianDate());
        var at = function (seconds) {{ return Cesium.JulianDate.addSeconds(start, seconds, new Cesium.JulianDate()); }};
        var secondsAt = function (time) {{ return Cesium.JulianDate.secondsDifference(time, start); }};

        // Latest [seconds, text] sample at or before `seconds` (samples sorted by time).
        var latest = function (samples, seconds, fallback) {{
            var low = 0, high = samples.length - 1, found = -1;
            while (low <= high) {{
                var middle = (low + high) >> 1;
                if (samples[middle][0] <= seconds) {{ found = middle; low = middle + 1; }} else {{ high = middle - 1; }}
            }}
            return found < 0 ? fallback : samples[found][1];
        }};

        viewer.clock.startTime = start.clone();
        viewer.clock.stopTime = stop.clone();
        viewer.clock.currentTime = start.clone();
        viewer.clock.clockRange = Cesium.ClockRange.LOOP_STOP;
        viewer.clock.multiplier = data.speed;
        viewer.clock.shouldAnimate = true;
        viewer.timeline.zoomTo(start, stop);
        viewer.camera.setView({{ destination: Cesium.Cartesian3.fromDegrees(0, 30, 30000000) }});

        // Nodes: one sampled position per recorded tick, interpolated in between.
        var positions = {{}};
        data.nodes.forEach(function (node) {{
            var position;
            if (node.static) {{
                position = new Cesium.ConstantPositionProperty(
                    Cesium.Cartesian3.fromDegrees(node.samples[1], node.samples[2], node.samples[3])
                );
            }} else {{
                position = new Cesium.SampledPositionProperty();
                position.setInterpolationOptions({{
                    interpolationDegree: 3,
                    interpolationAlgorithm: Cesium.LagrangePolynomialApproximation
                }});
                for (var i = 0; i < node.samples.length; i += 4) {{
                    position.addSample(
                        at(node.samples[i]),
                        Cesium.Cartesian3.fromDegrees(node.samples[i + 1], node.samples[i + 2], node.samples[i + 3])
                    );
                }}
            }}
            positions[node.id] = position;
            var color = Cesium.Color.fromCssColorString(node.color);
            var labelText = node.labels.length === 0 ? node.name : new Cesium.CallbackProperty(function (time) {{
                return latest(node.labels, secondsAt(time), node.name);
            }}, false);
            viewer.entities.add({{
                id: "node_" + node.id,
                name: node.group + ": " + node.name,
                description: node.description,
                position: position,
                point: {{
                    pixelSize: node.static ? 12 : 8, color: color,
                    outlineColor: node.static ? Cesium.Color.WHITE : Cesium.Color.BLACK, outlineWidth: node.static ? 2 : 1
                }},
                path: node.static || !data.trail ? undefined
                    : {{ leadTime: 0, trailTime: data.trail, width: 1, material: color.withAlpha(0.35) }},
                label: {{
                    text: labelText, font: node.labels.length || node.static ? "bold 12px sans-serif" : "11px sans-serif",
                    fillColor: Cesium.Color.WHITE, outlineColor: Cesium.Color.BLACK, outlineWidth: 2,
                    style: Cesium.LabelStyle.FILL_AND_OUTLINE, showBackground: node.labels.length > 0,
                    backgroundColor: new Cesium.Color(0.1, 0.1, 0.1, 0.6),
                    pixelOffset: new Cesium.Cartesian2(node.offset[0], node.offset[1]),
                    distanceDisplayCondition: node.labels.length || node.static ? undefined
                        : new Cesium.DistanceDisplayCondition(0, 12000000)
                }}
            }});
        }});

        // Links: shown only while they exist, their ends follow both nodes.
        var widths = {{ inter_shell: 3, ground: 2.5 }};
        data.edges.forEach(function (edge, index) {{
            if (!positions[edge.a] || !positions[edge.b]) {{ return; }}
            var availability = new Cesium.TimeIntervalCollection(edge.intervals.map(function (interval) {{
                return new Cesium.TimeInterval({{ start: at(interval[0]), stop: at(interval[1]) }});
            }}));
            var highlighted = edge.direction in widths;
            viewer.entities.add({{
                id: "edge_" + index,
                name: edge.direction + " link " + edge.a + " <-> " + edge.b,
                description: edge.description,
                availability: availability,
                polyline: {{
                    positions: new Cesium.PositionPropertyArray([positions[edge.a], positions[edge.b]]),
                    width: widths[edge.direction] || 1.5,
                    arcType: Cesium.ArcType.NONE,
                    material: Cesium.Color.fromCssColorString(edge.color).withAlpha(
                        (highlighted ? 1.0 : 0.6) * (data.routes.length ? 0.45 : 1.0)
                    )
                }}
            }});
        }});

        // Highlighted paths: each hop glows in the path color while it is part of the path.
        data.routes.forEach(function (route, routeIndex) {{
            var color = Cesium.Color.fromCssColorString(route.color);
            route.hops.forEach(function (hop, hopIndex) {{
                if (!positions[hop.a] || !positions[hop.b]) {{ return; }}
                viewer.entities.add({{
                    id: "route_" + routeIndex + "_" + hopIndex,
                    name: route.label,
                    availability: new Cesium.TimeIntervalCollection(hop.intervals.map(function (interval) {{
                        return new Cesium.TimeInterval({{ start: at(interval[0]), stop: at(interval[1]) }});
                    }})),
                    polyline: {{
                        positions: new Cesium.PositionPropertyArray([positions[hop.a], positions[hop.b]]),
                        width: route.width,
                        arcType: Cesium.ArcType.NONE,
                        material: new Cesium.PolylineGlowMaterialProperty({{ glowPower: 0.25, color: color.withAlpha(0.95) }})
                    }}
                }});
            }});
        }});

        // Latency chart: SVG line chart, cursor on the clock, hover readout, click to seek.
        var chart = (function () {{
            if (!data.chart) {{ return null; }}
            var container = document.getElementById("chart");
            var svgNS = "http://www.w3.org/2000/svg";
            var ink = {{ primary: "#0b0b0b", secondary: "#52514e", grid: "#e6e5e1", surface: "#fcfcfb" }};
            var height = 200, margin = {{ left: 44, right: 124, top: 10, bottom: 22 }};
            var tooltip = document.createElement("div");
            tooltip.className = "chart-tooltip";
            var state = {{}};

            var valueAt = function (points, seconds) {{
                var value = latest(points, seconds, null);
                return value;
            }};
            var clock = function (seconds) {{
                return Cesium.JulianDate.toIso8601(at(seconds), 0).slice(11, 16);
            }};
            var niceStep = function (raw) {{
                var power = Math.pow(10, Math.floor(Math.log10(raw)));
                var unit = raw / power;
                return (unit <= 1 ? 1 : unit <= 2 ? 2 : unit <= 5 ? 5 : 10) * power;
            }};
            var element = function (name, attributes, parent) {{
                var node = document.createElementNS(svgNS, name);
                Object.keys(attributes).forEach(function (key) {{ node.setAttribute(key, attributes[key]); }});
                parent.appendChild(node);
                return node;
            }};

            function draw() {{
                container.innerHTML = "";
                var title = document.createElement("div");
                title.className = "chart-title";
                title.textContent = data.chart.title;
                container.appendChild(title);
                var legend = document.createElement("div");
                legend.className = "chart-legend";
                data.chart.series.forEach(function (series) {{
                    var item = document.createElement("div");
                    item.innerHTML = '<span class="swatch" style="background:' + series.color + '"></span>';
                    item.appendChild(document.createTextNode(series.label));
                    legend.appendChild(item);
                }});
                container.appendChild(legend);

                var width = Math.max(320, container.clientWidth - 20);
                var innerWidth = width - margin.left - margin.right;
                var innerHeight = height - margin.top - margin.bottom;
                var maximum = 0;
                data.chart.series.forEach(function (series) {{
                    series.points.forEach(function (point) {{ if (point[1] !== null) {{ maximum = Math.max(maximum, point[1]); }} }});
                }});
                var yStep = niceStep(Math.max(maximum, 1) / 4);
                var yMax = Math.ceil(maximum / yStep) * yStep || yStep;
                var x = function (seconds) {{ return margin.left + seconds / data.stop * innerWidth; }};
                var y = function (value) {{ return margin.top + innerHeight - value / yMax * innerHeight; }};

                var svg = element("svg", {{ width: width, height: height, role: "img",
                    "aria-label": data.chart.title }}, container);
                for (var tick = 0; tick <= yMax + 1e-9; tick += yStep) {{
                    element("line", {{ x1: margin.left, x2: margin.left + innerWidth, y1: y(tick), y2: y(tick),
                        stroke: ink.grid, "stroke-width": 1 }}, svg);
                    element("text", {{ x: margin.left - 6, y: y(tick) + 4, "text-anchor": "end", "font-size": 11,
                        fill: ink.secondary }}, svg).textContent = tick + (tick === yMax ? " " + data.chart.unit : "");
                }}
                var xStep = [300, 600, 900, 1800, 3600, 7200].find(function (step) {{ return data.stop / step <= 6; }}) || 7200;
                for (var seconds = 0; seconds <= data.stop + 1e-9; seconds += xStep) {{
                    element("text", {{ x: x(seconds), y: height - 6, "text-anchor": "middle", "font-size": 11,
                        fill: ink.secondary }}, svg).textContent = clock(seconds);
                }}

                var ends = [];
                data.chart.series.forEach(function (series) {{
                    var path = "", drawing = false, last = null;
                    series.points.forEach(function (point) {{
                        if (point[1] === null) {{ drawing = false; return; }}
                        path += (drawing ? "L" : "M") + x(point[0]).toFixed(1) + " " + y(point[1]).toFixed(1);
                        drawing = true;
                        last = point;
                    }});
                    element("path", {{ d: path, fill: "none", stroke: series.color, "stroke-width": 2,
                        "stroke-linejoin": "round", "stroke-linecap": "round" }}, svg);
                    if (last) {{ ends.push({{ series: series, point: last }}); }}
                }});
                // Direct labels at the end of each line, pushed apart when they collide.
                ends.sort(function (a, b) {{ return y(a.point[1]) - y(b.point[1]); }});
                var previous = -Infinity;
                ends.forEach(function (end) {{
                    var labelY = Math.max(y(end.point[1]) + 4, previous + 14);
                    previous = labelY;
                    element("circle", {{ cx: x(end.point[0]), cy: y(end.point[1]), r: 4, fill: end.series.color,
                        stroke: ink.surface, "stroke-width": 2 }}, svg);
                    element("text", {{ x: margin.left + innerWidth + 8, y: labelY, "font-size": 11,
                        fill: ink.secondary }}, svg).textContent = end.series.label;
                }});

                var cursor = element("line", {{ y1: margin.top, y2: margin.top + innerHeight, stroke: ink.primary,
                    "stroke-width": 1, "stroke-opacity": 0.55 }}, svg);
                var cursorDots = data.chart.series.map(function (series) {{
                    return element("circle", {{ r: 4, fill: series.color, stroke: ink.surface, "stroke-width": 2 }}, svg);
                }});
                var hoverLine = element("line", {{ y1: margin.top, y2: margin.top + innerHeight, stroke: ink.secondary,
                    "stroke-width": 1, "stroke-dasharray": "3 3", visibility: "hidden" }}, svg);
                var hitArea = element("rect", {{ x: margin.left, y: margin.top, width: innerWidth, height: innerHeight,
                    fill: "transparent", style: "cursor: pointer" }}, svg);
                container.appendChild(tooltip);

                var secondsFromEvent = function (event) {{
                    var box = svg.getBoundingClientRect();
                    var seconds = (event.clientX - box.left - margin.left) / innerWidth * data.stop;
                    return Math.min(Math.max(seconds, 0), data.stop);
                }};
                hitArea.addEventListener("mousemove", function (event) {{
                    var seconds = secondsFromEvent(event);
                    hoverLine.setAttribute("x1", x(seconds));
                    hoverLine.setAttribute("x2", x(seconds));
                    hoverLine.setAttribute("visibility", "visible");
                    var rows = data.chart.series.map(function (series) {{
                        var value = valueAt(series.points, seconds);
                        return '<div class="row"><span class="swatch" style="display:inline-block;width:10px;height:3px;'
                            + 'border-radius:2px;background:' + series.color + '"></span><span>' + series.label
                            + '</span><b>' + (value === null ? "no path" : value.toFixed(2) + " " + data.chart.unit)
                            + '</b></div>';
                    }});
                    tooltip.innerHTML = '<div class="muted">' + clock(seconds) + " UTC</div>" + rows.join("");
                    tooltip.style.display = "block";
                    var box = container.getBoundingClientRect();
                    var left = event.clientX - box.left + 14;
                    if (left + tooltip.offsetWidth > box.width) {{ left = event.clientX - box.left - tooltip.offsetWidth - 14; }}
                    tooltip.style.left = left + "px";
                    tooltip.style.top = (event.clientY - box.top - 10) + "px";
                }});
                hitArea.addEventListener("mouseleave", function () {{
                    tooltip.style.display = "none";
                    hoverLine.setAttribute("visibility", "hidden");
                }});
                hitArea.addEventListener("click", function (event) {{
                    viewer.clock.currentTime = at(secondsFromEvent(event));
                }});

                state = {{ x: x, y: y, cursor: cursor, cursorDots: cursorDots }};
                if (lastSecond !== null) {{ update(lastSecond); }}
            }}

            function update(seconds) {{
                if (!state.cursor) {{ return; }}
                state.cursor.setAttribute("x1", state.x(seconds));
                state.cursor.setAttribute("x2", state.x(seconds));
                data.chart.series.forEach(function (series, index) {{
                    var value = valueAt(series.points, seconds);
                    var dot = state.cursorDots[index];
                    dot.setAttribute("visibility", value === null ? "hidden" : "visible");
                    if (value !== null) {{
                        dot.setAttribute("cx", state.x(seconds));
                        dot.setAttribute("cy", state.y(value));
                    }}
                }});
            }}

            window.addEventListener("resize", draw);
            return {{ draw: draw, update: update }};
        }})();

        // Live panel: link counters and live values at the current time.
        var lastSecond = null;
        viewer.clock.onTick.addEventListener(function (clock) {{
            var seconds = Math.floor(secondsAt(clock.currentTime));
            if (seconds === lastSecond) {{ return; }}
            lastSecond = seconds;
            document.getElementById("sim-time").textContent =
                Cesium.JulianDate.toIso8601(clock.currentTime, 0).replace("T", " ").replace("Z", "");
            var counts = {{}};
            data.edges.forEach(function (edge) {{
                var alive = edge.intervals.some(function (interval) {{
                    return interval[0] <= seconds && seconds < interval[1];
                }});
                if (alive) {{ counts[edge.direction] = (counts[edge.direction] || 0) + 1; }}
            }});
            document.querySelectorAll("[id^='count-']").forEach(function (element) {{
                element.textContent = counts[element.id.slice(6)] || 0;
            }});
            if (chart) {{ chart.update(seconds); }}
            data.live.forEach(function (samples, index) {{
                document.getElementById("live-" + index).textContent = latest(samples, seconds, "-");
            }});
        }});
        if (chart) {{ chart.draw(); }}
    </script>
</body>
</html>
"""
        if output_path:
            output_file = pathlib.Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(html_content)
            print(f"Animated Cesium HTML file generated: {output_file}")
            return None
        return html_content


def create_cesium_graph_visualization(
    graph: nx.Graph,
    output_path: str,
    title: str = "Network Graph Visualization"
) -> None:
    """
    Convenience function to create a Cesium HTML visualization from a networkX graph.
    
    Args:
        graph: A networkX graph with node attributes including 'position'
        output_path: Path where to save the HTML file
        title: Title for the visualization
        
    Example:
        >>> create_cesium_graph_visualization(G_only_sso, "output/graph_visualization.html")
    """
    visualizer = CesiumGraphVisualizer(graph, title)
    visualizer.generate_html(output_path)


def main():
    """
    Main entry point for command-line usage.
    
    Usage:
        python cesium_graph_visualizer.py --input graph.json --output output.html
    """
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(
        description="Convert a NetworkX JSON graph to a Cesium visualization.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cesium_graph_visualizer.py --input graph.json --output visualization.html
  python cesium_graph_visualizer.py -i network.json -o cesium_output.html -t "My Network"
        """
    )
    
    parser.add_argument(
        "--input", "-i",
        type=str,
        required=True,
        help="Path to the NetworkX JSON graph file"
    )
    
    parser.add_argument(
        "--output", "-o",
        type=str,
        required=True,
        help="Path where to save the Cesium HTML visualization"
    )
    
    parser.add_argument(
        "--title", "-t",
        type=str,
        default="Network Graph Visualization",
        help="Title for the visualization (default: 'Network Graph Visualization')"
    )
    
    args = parser.parse_args()
    
    try:
        # Load the NetworkX graph from JSON file
        input_path = pathlib.Path(args.input)
        
        if not input_path.exists():
            print(f"Error: Input file '{args.input}' not found", file=sys.stderr)
            sys.exit(1)
        
        print(f"Loading graph from: {args.input}")
        with open(input_path, 'r') as f:
            graph_data = json.load(f)
        
        # Convert JSON to NetworkX graph
        graph = nx.node_link_graph(graph_data)
        print(f"Graph loaded successfully: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")
        
        # Generate Cesium visualization
        output_path = pathlib.Path(args.output)
        print(f"Generating Cesium visualization...")
        create_cesium_graph_visualization(graph, str(output_path), args.title)
        
        print(f"Successfully generated: {output_path}")
        
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON file - {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
