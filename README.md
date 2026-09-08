# sat_com_topology_tutorials
## Install
### Clone the project
```shell
git clone git@github.com:elbarbi/satComTopologyTutorials.git
```
```shell
cd satComTopologyTutorials
```
### Install your workspace
Venv environment allow you to isolate your workspace and only use packages in this specific location.
#### Init your virtual environment
```shell
python -m venv .venv
```
#### Activate your virtual environment
```shell
source .venv/bin/activate
```
### Install dependencies
```shell
pip install -r requirements.txt
```
## Use
All tutorials live in [`src`](src). Suggested reading order:

1. [`src/create_my_first_simulation.ipynb`](src/create_my_first_simulation.ipynb) — build different constellations (Walker Delta / Walker Star) from a plain or YAML configuration.
2. [`src/deeply_understand_sat_com_topology.ipynb`](src/deeply_understand_sat_com_topology.ipynb) — build a simulation by hand, object by object, with `SimulationManager`.
3. [`src/shortest_path_lab.ipynb`](src/shortest_path_lab.ipynb) — a short lab computing the shortest path between a User Terminal and a Ground Station with `networkx`.
4. [`src/handover_lab.ipynb`](src/handover_lab.ipynb) — a short lab recording every Ground Station handover (`best-angle-until-disconnection`) as the constellation moves.
5. [`src/sat_com_topology_v4_networkx.ipynb`](src/sat_com_topology_v4_networkx.ipynb) — a reference example recording the network state at every tick.

Open a notebook and enjoy !