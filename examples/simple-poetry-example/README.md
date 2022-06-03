# Simple Poetry Example
This directory demonstrates what a simple Pinto project built on top of pure Poetry might look like. Unlike the Conda examples, no additional requirements beyond a [`pyproject.toml`](./pyproject.toml) with a `[tool.poetry]` table are required.

Building this project only requires running
```console
pinto build
```

which could just as easily be achieved via

```console
poetry install
```

The key is that the former requires no prior knowledge from users as to what the environmental demands of this project are (i.e. whether it requires Conda).

As with any Poetry project, the name given in the `[tool.poetry]` table of the  [`pyproject.toml`](./pyproject.toml) tells Poetry to look for a library (or file in this case) named `pinto_poetry_example` to install.
The `[tool.poetry.scripts]` table in `pyproject.toml` tells Poetry to install a command line executable named `testme` which executes the `main` function defined in [`pinto_poetry_example.py`](./pinto_poetry_example.py).
So once this project has been built, you can run

```console
pinto run testme
```

Which should print

```console
Good job!  You installed a pip module.

Now get back to work!
Everything's working!
```

If you wanted to do this _without_ `pinto`, you could always run the command inside the corresponding poetry environment explicitly

```console
poetry run testme
```

The point once again is that the former requires no prior knowledge from the user as to how exactly this project runs. Moreover, it gives you the freedom to execute this command from _any_ directory, rather than just this one (just add the flag `-p <path to project>` in the pinto command above).

Also note that `pinto_poetry_example` has been installed as a _library_ in this environment as well, so you could just as easily create a python script which imports it

```python
from pinto_poetry_example import main as pinto_poetry

pinto_poetry()
```
