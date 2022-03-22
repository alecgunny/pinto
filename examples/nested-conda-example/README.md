# Nested Conda Example
Almost everything from the `simple-conda-example` [`README`](../simple-conda-example/README.md) should apply here, with one major exception.
Notice that the project itself, which is hosted in `src`, does _not_ have an `environment.yaml` (which instead lives in [this directory](./environment.yaml)).
However, since this is the first `environment.yaml` climbing up the `src` directory's tree, the `pinto-nested-conda-example` project hosted in `src` will still use it to build its environment, using Poetry to install its dependencies on top of this environment.
Moreover, since the `name` given in `environment.yaml` is `example-base`, ending in `-base`, the name of the environment `pinto-nested-conda-example` will build when you run

```console
pinto build src
```

is `example-pinto-nested-conda-example` (pardon the tautology), replacing `-base` with the name of the specific project.

There could therefore be multiple subprojects beside the one living in `src` underneath this directory that all build off of the same environment file.

In practice what happens is that when the first subproject gets built, let's say the one in `src`, the `example-base` environment gets built for the first time, then cloned to an environment named `example-pinto-nested-conda-example`, into which all the Poetry dependencies are installed.
All subsequent subprojects would clone the existing `example-base` environment and install their dependencies inside of their clones.
Therefore, if you make any changes to the base `environment.yaml`, you'll want to either delete or update the base environment so that subsequent builds have the updated Conda requirements.
