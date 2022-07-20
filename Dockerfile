FROM ubuntu:20.04
MAINTAINER Martin Dobias "martin.dobias@lutraconsulting.co.uk"

# this is to do choice of timezone upfront, because when "tzdata" package gets installed,
# it comes up with interactive command line prompt when package is being set up
ENV TZ=Europe/London
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN apt-get update && apt-get install -y \
    cmake \
    git \
    libpq-dev \
    libsqlite3-dev \
    python3-pip \
    python3-psycopg2 \
 && rm -rf /var/lib/apt/lists/*

# Python Mergin client
RUN python3 -m pip install --upgrade pip
RUN pip3 install dynaconf==3.1.7
RUN pip3 install scikit-build wheel cmake

# geodiff (version >= 1.0.0 is needed with PostgreSQL support - we have to compile it)
RUN git clone --branch master https://github.com/merginmaps/geodiff.git
RUN cd geodiff && mkdir build && cd build && \
    cmake -DWITH_POSTGRESQL=TRUE ../geodiff && \
    make

# build pygeodiff
RUN cd geodiff && python3 setup.py build && python3 setup.py install

# build mergin python client
RUN git clone --branch master https://github.com/merginmaps/mergin-py-client.git
RUN cd mergin-py-client && python3 setup.py build && python3 setup.py install

# DB sync code
WORKDIR /mergin-db-sync
COPY version.py .
COPY config.py .
COPY dbsync.py .
COPY dbsync_daemon.py .

# base DB sync config file (the rest is configured with env variables)
COPY config-dockerfile.yaml ./config.yaml
