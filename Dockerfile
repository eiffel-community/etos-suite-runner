FROM python:3.9-buster AS build

COPY . /src
WORKDIR /src/projects/etos_suite_runner
RUN python3 setup.py bdist_wheel

FROM python:3.9-slim-buster

COPY --from=build /src/projects/etos_suite_runner/dist/*.whl /tmp
# hadolint ignore=DL3008
# hadolint ignore=DL3013
RUN apt-get update && \
    apt-get install -y gcc libc-dev --no-install-recommends && \
    pip install --no-cache-dir /tmp/*.whl && \
    apt-get purge -y --auto-remove gcc libc-dev && \
    rm -rf /var/lib/apt/lists/* && \
    groupadd -r etos && useradd -r -m -s /bin/false -g etos etos

USER etos

LABEL org.opencontainers.image.source=https://github.com/eiffel-community/etos-suite-runner
LABEL org.opencontainers.image.authors=etos-maintainers@googlegroups.com
LABEL org.opencontainers.image.licenses=Apache-2.0

CMD ["python", "-u", "-m", "etos_suite_runner"]
