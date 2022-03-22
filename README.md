# Pinto
A command line utility for managing and running jobs in complex Python environments.

## Background
Most ongoing research in the [ML4GW](https://github.com/ML4GW) organization leverages [Poetry](https://python-poetry.org/) for managing Python virtual environments in the context of a [Python monorepo](https://medium.com/opendoor-labs/our-python-monorepo-d34028f2b6fa). In particular, Poetry makes managing a shared set of libraries between jobs within a project [simple and straightforward](https://python-poetry.org/docs/dependency-specification/#path-dependencies).

However, several tools in the Python gravitational wave analysis ecosystem can only be installed via Conda (in particular the [library](https://anaconda.org/conda-forge/python-ldas-tools-framecpp/) GWpy uses to read and write `.gwf` files and the library it uses for [reading archival data from the NDS2 server](https://anaconda.org/conda-forge/python-nds2-client)). This complicates the environment management picture by having some projects which use Poetry to install local libraries as well as their own code into _Conda_ virtual environments, and others which don't require Conda at all and can install all the libraries they need into _Poetry_ virtual environments.

### Enter: Pinto
Pinto  attempts to simplify this picture by installing a single tool in the base Conda environment which can dynamically detect whether a project requires Conda, create the appropriate virtual environment, and install all necessary libraries into it.

```console
pinto build /path/to/my/project
```

It can then be used to run jobs inside of that virtual environment.

```console
pinto run /path/to/my/project my-command --arg1
```

## Structuring a project with Pinto
To leverage Pinto in a project, all you need is the [`pyproject.toml` file](https://python-poetry.org/docs/pyproject/) required by Poetry which specifies your project's dependencies. This will treat your project as a "vanilla" Poetry project and manage all of its dependencies inside a Poetry virtual environment.

### But what if I need Conda?
Inidicating to Pinto that your project requires Conda is as simple as including a `poetry.toml` file in your project directory with the lines

```toml
[virtualenvs]
create = false
```

Alternatively, from you project directory you can run

```console
poetry config virtualenvs.create false --local
```

When building your project, Pinto will first look for an entry that looks like

```toml
[tool.pinto]
base_env = "/path/to/environment.yaml"
```

In your project's `pyproject.toml`. If this entry doesn't exist, Pinto will look for a file called either `environment.yaml` or `environment.yml` starting in your project's directory, then ascending up your directory tree to the root, using the first file it finds. This way, you can easily have a base `environment.yaml` in the root of a monorepo from on top of which all your projects build, while leaving projects the option of overriding this base image with their own `environment.yaml`.

In fact, if the `name` listed in the `environment.yaml` Pinto finds ends with `-base`, it will automatically name your project's virtual environment `<prefix>-<project-name>`. For example, if the name of your project (as given in the `pyproject.toml`) is `nn-trainer`, and the `environment.yaml` at the root of your monorepo looks like

```yaml
name: myproject-base
dependencies:
    - ...
```

then Pinto will name your project's virtual environment `myproject-nn-trainer`.

To see more examples of project structures, consult the [`examples`](./examples) folder.


## Installation
### Environment set up
Pinto requires local versions of both Conda and Poetry.
First make sure that you have a _local_ version of Conda installed in your environment (instructions found [here](https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html)).
Then ensure that you have the latest version of [Poetry](https://python-poetry.org/) installed following the instructions [here](https://python-poetry.org/docs/master/#installing-with-the-official-installer), the upshot being that you should just need to run

```console
curl -sSL https://install.python-poetry.org | python3 - --preview
```

Then from this directory, **and in your _base_ Conda environment**, first make sure that this project will install to your system Python `site-packages` (i.e. the base Conda environment's `site_packages`), run

```console
poetry config virtualenvs.create false --local
```

Then simply run

```console
poetry install
```

or, to install without develop dependencies like pytest and sphinx, run

```console
poetry install --without dev
```
