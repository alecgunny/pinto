# Pinto
A command line utility for managing and running jobs in complex Python environments.

Support tested for:

![poetry 1.2.0a2](https://img.shields.io/badge/poetry-1.2.0a2-sucess)
![poetry 1.2.0b2](https://img.shields.io/badge/poetry-1.2.0b2-sucess)
![poetry 1.2.0b3](https://img.shields.io/badge/poetry-1.2.0b3-sucess)
![poetry 1.2.1](https://img.shields.io/badge/poetry-1.2.1-sucess)
![poetry 1.2.2](https://img.shields.io/badge/poetry-1.2.2-sucess)

![conda 4.10.3](https://img.shields.io/badge/conda-4.10.3-sucess)
![conda 4.11.0](https://img.shields.io/badge/conda-4.11.0-sucess)
![conda 4.12.0](https://img.shields.io/badge/conda-4.12.0-sucess)


## Background
Most ongoing research in the [ML4GW](https://github.com/ML4GW) organization leverages [Poetry](https://python-poetry.org/) for managing Python virtual environments in the context of a [Python monorepo](https://medium.com/opendoor-labs/our-python-monorepo-d34028f2b6fa). In particular, Poetry makes managing a shared set of libraries between jobs within a project [simple and straightforward](https://python-poetry.org/docs/dependency-specification/#path-dependencies).

However, several tools in the Python gravitational wave analysis ecosystem cannot be installed via Pip (in particular the [library](https://anaconda.org/conda-forge/python-ldas-tools-framecpp/) GWpy uses to read and write `.gwf` files and the library it uses for [reading archival data from the NDS2 server](https://anaconda.org/conda-forge/python-nds2-client)). This complicates the environment management picture by having some projects which use Poetry to install local libraries as well as their own code into _Conda_ virtual environments, and others which don't require Conda at all and can install all the libraries they need into _Poetry_ virtual environments.

### Enter: `pinto`
Pinto  attempts to simplify this picture by installing a single tool in the base Conda environment which can dynamically detect whether a project requires Conda, create the appropriate virtual environment, and install all necessary libraries into it.

```console
pinto -p /path/to/my/project build
```

It can then be used to run jobs inside of that virtual environment.

```console
pinto -p /path/to/my/project run my-command --arg1
```

If you're currently in the project's directory, you can drop the `-p/--project` flag altogether for any pinto command, e.g.

```console
pinto build
pinto run my-command --arg1
```

## Structuring a project with Pinto
To leverage Pinto in a project, all you need is the [`pyproject.toml` file](https://python-poetry.org/docs/pyproject/) required by Poetry which specifies your project's dependencies. If just this file is present, `pinto` will treat your project as a "vanilla" Poetry project and manage all of its dependencies inside a Poetry virtual environment.

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

When building your project, `pinto` will first look for an entry that looks like

```toml
[tool.pinto]
base_env = "/path/to/environment.yaml"
```

In your project's `pyproject.toml`. If this entry doesn't exist, `pinto` will look for a file called either `environment.yaml` or `environment.yml` starting in your project's directory, then ascending up your directory tree to the root, using the first file it finds. This way, you can easily have a base `environment.yaml` in the root of a monorepo from on top of which all your projects build, while leaving projects the option of overriding this base image with their own `environment.yaml`.

In fact, if the `name` listed in the `environment.yaml` discovered by `pinto` ends with `-base`, `pinto` will automatically name your project's virtual environment `<prefix>-<project-name>`. For example, if the name of your project (as given in the `pyproject.toml`) is `nn-trainer`, and the `environment.yaml` at the root of your monorepo looks like

```yaml
name: myproject-base
dependencies:
    - ...
```

then `pinto` will name your project's virtual environment `myproject-nn-trainer`.

To see more examples of project structures, consult the [`examples`](./examples) folder.


## Installation
For any non-containerized installation methods, please consult the support matrix at the top of this document to see which versions of Anaconda and Poetry are supported by `pinto`.

### Container
The simplest way to get started with pinto is to use the container published by this repository, which is made available through GitHub's container registry. You can pull it by running
```
docker pull ghcr.io/ML4GW/pinto:main
```
See [this document](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry#authenticating-to-the-container-registry) for information about how to authenticate to the GitHub container reigstry.

### Conda
Pinto can only be installed on top of Anaconda, so make sure you have a *local* install available to work with (instructions found [here](https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html). I particularly recommend using Miniconda for a bare install, since most your work will be in virtual environments anyway.

> **NOTE**: `pinto` is currently only compatible with 4.x Conda versions!! To find the appropriate Miniconda installer, please look at the [installer archives](https://repo.anaconda.com/miniconda/).

Your options are then to either install `pinto` in the `base` conda environment (recommended), or in a virtual environment. If you choose to go the latter route, the conda environments managed by pinto will be kept in a subdirectory of pinto's environment.

#### Installing in the base conda environment
First install poetry via pip
```console
(base) ~$ python -m pip install "poetry>1.2.0,<1.3.0"
```
then install pinto via pip
```console
(base) ~$ python -m pip install git+https://github.com/ML4GW/pinto@main
```

#### In a virtual environment
If you don't want to install pinto into your `base` conda environment, you can install it by creating an environment file like the one found [here](./environment.yaml), and creating a virtual environment like:
```console
(base) ~$ conda env create -f environment.yaml
```
You can then activate your pinto environment and execute commands inside of it
```console
(base) ~$ conda activate pinto
(pinto) ~$ pinto --version
```

### Setting the Poetry virtualenvs path
Whether you installed pinto your base environment or in a virtual environment, we recommend setting up Poetry's default virtual environment path so that it installs environments to the same location as conda. With the desired environment activated, run
```console
(base OR pinto) ~$ poetry config virtualenvs.path $CONDA_PREFIX/envs
```

### Development Installation
To develop pinto, clone the repo locally
```console
(base) ~$ git clone https://github.com/ML4GW/pinto.git
```
Then complete either installation method above, but with the local library installed editably. For base installs:
```console
(base) ~$ python -m pip install -e ./pinto[dev]
```

For virtual environment installs, edit the `environment.yaml` so that the pinto install line is replaced with
```yaml
  - -e .[dev]
```
Then run
```console
(base) ~$ cd pinto
(base) ~$ conda env create -f environment.yaml
```
