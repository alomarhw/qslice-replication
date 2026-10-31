# srcSlice-Q with srcML 1.1.0 and patched srcSlice, and the pinned Python packages of the experiments.
#   docker build -t srcslice-q .
#   docker run --rm -v "$PWD":/work -w /work srcslice-q bash reproduce.sh
FROM ubuntu:24.04
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git build-essential cmake libxml2-dev libxslt1-dev libarchive-dev libcurl4-openssl-dev \
      python3 python3-venv python3-pip texlive-latex-extra texlive-fonts-extra texlive-science latexmk poppler-utils \
    && rm -rf /var/lib/apt/lists/*
# srcML 1.1.0, the release the study used
RUN for p in srcml srcml-dev; do \
      curl -fsSL -o /tmp/$p.deb https://github.com/srcML/srcML/releases/download/v1.1.0/${p}_1.1.0-1_ubuntu24.04_amd64.deb; \
    done && apt-get update && apt-get install -y /tmp/srcml.deb /tmp/srcml-dev.deb && rm -rf /tmp/*.deb /var/lib/apt/lists/*
# srcSlice at the commit the study used, with the patch of srcslice/ (accuracy fixes and Python support)
COPY srcslice/srcslice-python.diff /opt/srcslice-python.diff
RUN git clone --recursive https://github.com/srcML/srcSlice.git /opt/srcSlice && cd /opt/srcSlice \
    && git checkout ce86ef8 && git submodule update --init --recursive && git apply /opt/srcslice-python.diff \
    && mkdir /opt/build && cd /opt/build && cmake /opt/srcSlice && make -j"$(nproc)" \
    && find /opt/build -type f -name srcslice -perm -u+x -exec cp {} /usr/local/bin/srcslice \;
COPY . /opt/srcslice-q
RUN python3 -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir -r /opt/srcslice-q/experiments/requirements.lock \
    && /opt/venv/bin/pip install --no-cache-dir /opt/srcslice-q
ENV PATH="/opt/venv/bin:${PATH}"
WORKDIR /opt/srcslice-q
CMD ["srcslice-q", "--help"]
