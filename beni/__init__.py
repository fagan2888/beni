"""
Generate environment.yml from pyproject.toml

"""


from __future__ import annotations

import argparse
import http.client
import typing

import flit_core.inifile
import packaging.requirements
import tqdm
import typeguard
import yaml

__version__ = "0.3.0"

parser = argparse.ArgumentParser(description="Generate an environment.yml.")
parser.add_argument(
    "paths", metavar="pyproject.toml", type=str, nargs="+", help="flit config files",
)
parser.add_argument(
    "--ignore",
    metavar=("foo", "bar"),
    type=str,
    nargs="*",
    help="Conda packages to ignore",
)


def is_conda_forge_package(name: str) -> bool:
    """
    Checks if something is a conda forge package by hitting conda page.

    If 200 then package, if 302 then not.
    """
    # Have to use http.client instead of urllib b/c no way to disable redirects
    # on urrlib and it's wasteful to follow (AFAIK)

    # Need user agent or else got unauthorized
    conn = http.client.HTTPSConnection("anaconda.org")
    conn.request("GET", f"/conda-forge/{name}/", headers={"User-Agent": "beni"})
    r = conn.getresponse()
    conn.close()
    return r.status == 200


class Environment(typing.TypedDict):
    name: str
    channels: typing.List[str]
    dependencies: typing.List[typing.Union[str, typing.Dict[str, typing.List[str]]]]


@typeguard.typechecked
def generate_environment(
    name: str,
    python_version: typing.Optional[str],
    requirements: typing.List[packaging.requirements.Requirement],
) -> Environment:
    dependencies = {"pip"}

    if python_version:
        dependencies.add(f"python{python_version}")
    else:
        dependencies.add("python")

    for r in tqdm.tqdm(requirements, desc="Checking packages"):
        if not is_conda_forge_package(r.name):
            continue
        dependencies.add(f"{r.name}{r.specifier}")

    return {
        "name": name,
        "channels": ["conda-forge"],
        "dependencies": [{"pip": ["flit"]}, *dependencies],
    }


def main() -> None:
    args = parser.parse_args()
    python_version: typing.Optional[str] = None
    requires: typing.List[packaging.requirements.Requirement] = []
    first_module = None
    ignored_modules: typing.List[str] = args.ignore or []
    for path in tqdm.tqdm(args.paths, desc="Parsing configs"):
        c = flit_core.inifile.read_flit_config(path)
        if not first_module:
            first_module = c.module
        ignored_modules.append(c.module)
        metadata = c.metadata
        if "requires_python" in metadata:
            python_version = metadata["requires_python"]
        if "requires_dist" in metadata:
            requires.extend(
                map(packaging.requirements.Requirement, metadata["requires_dist"])
            )

    env = generate_environment(
        first_module,
        python_version,
        [r for r in requires if r.name not in ignored_modules],
    )
    print(yaml.dump(env))
