# sat_com_topology_tutorials
## Install
### Clone the project
```shell
git clone git@github.com:elbarbi/satComTopologyTutorials.git
```
```shell
cd satComTopologyTutorials
```
### Install your workspace with uv
The project is managed with [uv](https://docs.astral.sh/uv/). Install it once:
```shell
curl -LsSf https://astral.sh/uv/install.sh | sh
```
Then create the virtual environment (`.venv`) with every dependency, satComTopology V5 included, at the exact versions of `uv.lock`:
```shell
uv sync
```
The dependencies are declared in [`pyproject.toml`](pyproject.toml). satComTopology (`5.0.x`) comes from the `develop` branch of [its repository](https://github.com/elbarbi/satComTopology), pinned to a commit in `uv.lock`. To move to its latest commit:
```shell
uv lock --upgrade-package sat-com-topology
uv sync
```
### Start Jupyter
```shell
cd src
uv run jupyter lab
```
### Without uv
`requirements.txt` holds the same locked versions, for pip (it is generated from `uv.lock`: never edit it by hand). In your own virtual environment:
```shell
pip install -r requirements.txt
```
After a change of the dependencies, regenerate it with `uv export --no-hashes --no-dev -o requirements.txt`.
## Use
All tutorials live in [`src`](src), sorted by the satComTopology features they use. Every notebook runs with satComTopology V5 (`5.0.x`); start Jupyter from `src` (`uv run jupyter lab`) to see both folders.

### [`src/v4`](src/v4): the fundamentals (features available since V4)
Configuration, constellations, links, NetworkX and Cesium exports, and actions on the simulation clock. Suggested reading order:

1. [`create_my_first_simulation.ipynb`](src/v4/create_my_first_simulation.ipynb) — build different constellations (Walker Delta / Walker Star) from a plain or YAML configuration.
2. [`deeply_understand_sat_com_topology.ipynb`](src/v4/deeply_understand_sat_com_topology.ipynb) — build a simulation by hand, object by object, with `SimulationManager`.
3. [`shortest_path_lab.ipynb`](src/v4/shortest_path_lab.ipynb) — a short lab computing the shortest path between a User Terminal and a Ground Station with `networkx`.
4. [`handover_lab.ipynb`](src/v4/handover_lab.ipynb) — a short lab recording every Ground Station handover (`best-angle-until-disconnection`), by polling the links at each tick.
5. [`sat_com_topology_v4_networkx.ipynb`](src/v4/sat_com_topology_v4_networkx.ipynb) — a reference example recording the network state at every tick.

### [`src/v5`](src/v5): the V5 features
Event bus and event factories, optical terminals, dawn-dusk SSO shells and inter-shell links. Suggested reading order:

1. [`handover_events_lab.ipynb`](src/v5/handover_events_lab.ipynb) — the V5 version of the handover lab: the handovers come from the ground link events, and each link's predicted disconnection time is checked against the actual one.
2. [`optical_terminal_lab.ipynb`](src/v5/optical_terminal_lab.ipynb) — optical terminals: a small IRIS²-like constellation with 4 optical ISLs per satellite, and an event bus printing the optical constraints of both terminals at every ISL update.
3. [`inter_shell_cesium_lab.ipynb`](src/v5/inter_shell_cesium_lab.ipynb) — inter-shell links: EO Relay, an IRIS²-like relay shell, and a 6-satellite Earth observation SSO constellation, connected with the `inter-shell-sso-priority` strategy. Two ground stations in Toulouse (CNES for the EO satellites, ISAE-SUPAERO for EO Relay), a network graph (igraph) maintained in real time from the events to measure the propagation latency to every EO satellite, an inter-shell handover counter, and an animated Cesium replay of it all.
4. [`shortest_latency_paths_lab.ipynb`](src/v5/shortest_latency_paths_lab.ipynb) — routing: ground stations in Paris, New York and Sydney on a 12 × 22 IRIS²-like constellation, the shortest latency path from Paris to New York and to Sydney at every tick, underlined in Cesium with a latency chart.

The V5 labs share two helper modules: [`cesium_graph_visualizer.py`](src/v5/cesium_graph_visualizer.py) (animated Cesium pages) and [`dynamic_topology_graph.py`](src/v5/dynamic_topology_graph.py) (an igraph graph kept in sync with the simulation events).

Open a notebook and enjoy !
