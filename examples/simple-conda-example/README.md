# Simple Conda Example
This directory demonstrates what a simple Pinto project built on top of Conda might look like. Note in particular the [`poetry.toml`](./poetry.toml) that indicates that this project depends on Conda via the

```toml
[virtualenvs]
create = false
```

table, as well as the `environment.yaml` that describes the dependencies Conda will be in charge of installing and gives the project's virtual environment its name, `pinto-conda-example`. Therefore, after buildling this project via

```console
pinto build
```

you could just as easily activate this environment with Conda

```console
conda activate pinto-conda-example
```

and do your work inside of there.

As with any Poetry project, the name given in the `[tool.poetry]` table of the  [`pyproject.toml`](./pyproject.toml) tells Poetry to look for a library (or file in this case) named `pinto_conda_example` to install. The `[tool.poetry.scripts]` table in `pyproject.toml` tells Poetry to install a command line executable named `testme` which executes the `main` function defined in [`pinto_conda_example.py`](./pinto_conda_example.py). So once this project has been built, you can run

```console
pinto run testme
```

Which should print

```console
Good job!  You installed a pip module.

Now get back to work!
Everything's working!
```

If you wanted to do this _without_ `pinto`, you could always activate the conda environment and run things in there

```console
conda activate pinto-conda-example
testme
```

The point is just that the unfamiliar user would need to know that this required execution inside a Conda environment. There are also potential sticking points with using Conda inside containers that this alleviates.

Also note that `pinto_conda_example` has been installed as a _library_ in this environment as well, so you could just as easily create a python script which imports it

```python
from pinto_conda_example import main as pinto_conda

pinto_conda()
```
