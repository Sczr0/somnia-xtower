FROM mcr.microsoft.com/dotnet/sdk:10.0

RUN apt-get update -qq && \
    apt-get install -y -qq --no-install-recommends aria2 libvorbis-dev libogg-dev git wget python3 python3-pip python3-venv && \
    rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir --upgrade pip
