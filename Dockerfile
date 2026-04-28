FROM mcr.microsoft.com/dotnet/sdk:10.0

RUN apt-get update -qq && \
    apt-get install -y -qq --no-install-recommends aria2 python3 && \
    rm -rf /var/lib/apt/lists/*
