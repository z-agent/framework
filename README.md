## framework

This framework provides the base for building an easy-to-use platform for agent creation & discovery. It mainly consists of a server-side component that stores a registry of tools & agents which are discoverable by users and can be used to build custom agent workflows on top of. It is built using `fastAPI`, `qdrant`, and the `crewAI` agents framework.

The main use-case can be described as follows:

  - Users visiting the platform want to create their own agents from scratch
  - They define the tasks to be performed by each agent in detail, and any tools that might be needed for the agents can be looked up and used from the registry, the user doesn't need to write any code
  - The agents can then be published to the platform, making them usable in a standalone manner by other users as well

An example of how the APIs could be used by a frontend is documented in the [`client.py`](src/client/client.py) file. All of the backend code is located in the [`server`](src/server) directory.

## APIs

In-depth API specifications can be found at the `/docs` endpoint of the backend

- `/tool_search`
  - Takes a search query and returns a list of suitable tools based on similarity search, eg. `/tool_search?query=serper`

- `/agent_search`
  - Same as the `/tool_search` endpoint, but for agents

- `/save_agent`
  - Takes a list of agents with their corresponding tasks, argument schema, along with the tools required and persists it into vector storage. The stored agent can later be interacted with using the `/agent_call` endpoint

- `/agent_call`
  - Takes an agent ID along with the arguments to be passed for execution. The agent workflow is internally executed on the backend by dynamically constructing a `crewAI` crew and providing it the necessary tools, returning the raw response

## Installation

The backend requires a hefty list of (transitive) dependencies that can be installed as follows:

```bash
$ python3 -m venv ./env
$ . ./env/bin/activate
$ pip install -r requirements.txt
```

Then, the server can be run with `python3 -m src.server.main` to expose a server accessible at port `8000`. Make sure that the `OPENAI_API_KEY` and `SERPER_API_KEY` (required for the serper search tool) environment variables are set.
