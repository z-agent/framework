import asyncio
import agentipy
import os
from crewai import Agent, Crew, Task
from crewai.tools import BaseTool
import inspect
import typing
from pydantic import Field, BaseModel, create_model
from solders.pubkey import Pubkey


# Check whether the argument is marked as optional with the
# typing.Optional hint
def is_optional_arg(annotation):
    return isinstance(annotation, typing._GenericAlias) and (
        annotation.__origin__ is typing.Union
        and type(None) in annotation.__args__
    )


def gen_tool(method_name, method):
    model_fields = {}
    arg_type_mapping = {}

    for arg, arg_type in typing.get_type_hints(method).items():
        if arg_type == Pubkey:
            arg_type_mapping[arg] = Pubkey.from_string
            arg_type = str

        if not (arg_type in (bool, str, int, float, type(None))):
            if is_optional_arg(arg_type):
                continue

            raise ValueError(
                f"arg {arg} of {method_name} not of primitive type: {arg_type}"
            )

        model_fields[arg] = (
            arg_type,
            Field(..., description=arg.replace("_", " ").title()),
        )

    class Tool(BaseTool):
        name: str = method_name
        description: str = (
            inspect.getdoc(method) or f"Invoke {method_name} method."
        )
        args_schema: typing.Type[BaseModel] = create_model(
            method_name.replace("_", " ").title(), **model_fields
        )

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def _run(self, **kwargs):
            print(f"Invoked {method_name}: {kwargs}")

            for arg in kwargs:
                if arg in arg_type_mapping:
                    kwargs[arg] = arg_type_mapping[arg](kwargs[arg])

            return asyncio.run(method(**kwargs))

    return Tool()


def gen_tools():
    agent = agentipy.SolanaAgentKit(rpc_url="https://api.devnet.solana.com")
    tools = []

    methods = inspect.getmembers(agent, predicate=inspect.iscoroutinefunction)
    for method_name, method in methods:
        if method_name.startswith("_"):
            continue
        if method_name not in {
            "trade",
            "fetch_price",
            "get_tps",
            "stake",
            "get_address_name",
        }:
            continue

        tools.append(
            (
                f"Solana {method_name.replace('_', ' ').title()}",
                gen_tool(method_name, method),
            )
        )

    return tools
