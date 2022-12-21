ARG CONDA_TAG=4.11.0
ARG dev=false

FROM continuumio/miniconda3:${CONDA_TAG} as base

SHELL ["/bin/bash", "-c"]
ARG POETRY_VERSION=1.2.0b3
ENV POETRY_VIRTUALENVS_PATH=/opt/conda/envs \
    CONDA_INIT=$CONDA_PREFIX/etc/profile.d/conda.sh

# install poetry in the base conda environment
RUN set +x \
        && source $CONDA_INIT \
        \
        && python -m pip install poetry==$POETRY_VERSION \
        \
        && poetry --version \
        \
        && apt-get update \
        \
        && apt-get install -y --no-install-recommends \
            gcc \
            linux-libc-dev \
            libc6-dev \
        \
        && rm -rf /var/lib/apt/lists/*

ADD . /opt/pinto

# use dev flag to decide how to install pinto in container
FROM base AS true
ENV DEV="-e"
RUN set +x \
        \
        && source $CONDA_INIT \
        \
        && cd /opt/pinto \
        \
        && poetry export \
            --with dev \
            -f requirements.txt \
            --output requirements-dev.txt \
        \
        && python -m pip install -r requirements-dev.txt

FROM base AS false
ENV DEV=""

FROM ${dev}
RUN python -m pip install ${DEV} /opt/pinto && pinto --version
