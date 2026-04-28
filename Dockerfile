FROM mcr.microsoft.com/dotnet/sdk:10.0

RUN apt-get update -qq && \
    apt-get install -y -qq --no-install-recommends aria2 libvorbis-dev libogg-dev git wget python3 python3-pip python3-venv python3-full && \
    rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
