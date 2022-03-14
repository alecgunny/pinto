ARG CONDA_TAG=4.10.3
FROM continuumio/miniconda3:${CONDA_TAG}

SHELL ["/bin/bash", "-c"]
ENV POETRY_VERSION=1.2.0a2 \
    POETRY_VIRTUALENVS_PATH=/opt/conda/envs \
    CONDA_INIT=$CONDA_PREFIX/etc/profile.d/conda.sh

# install poetry in the base conda environment
RUN set +x \
        && source $CONDA_INIT \
        \
        && python -m pip install poetry==$POETRY_VERSION \
        \
        && poetry --version \
        \
        && rm -rf /var/lib/apt/lists/*

# add in pinto and install it into the
# base environment as well
ADD . /opt/pinto
RUN set +x \
        \
        && source $CONDA_INIT \
        \
        && cd /opt/pinto \
        \
        && poetry config virtualenvs.create false --local \
        \
        && poetry install --no-interaction \
        \
        && pinto --version
