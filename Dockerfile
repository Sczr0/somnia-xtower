FROM python:3.10

RUN sed -i 's|http://deb.debian.org|http://mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's|http://deb.debian.org|http://mirrors.aliyun.com|g' /etc/apt/sources.list && \
    apt-get update -qq && \
    apt-get install -y -qq --no-install-recommends aria2 libvorbis-dev libogg-dev git wget && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -U pip setuptools wheel

# 安装 .NET 10 SDK (下载 + 静默等待完成后打印确认)
RUN wget -q --show-progress https://dot.net/v1/dotnet-install.sh -O /tmp/dotnet-install.sh && \
    chmod +x /tmp/dotnet-install.sh && \
    /tmp/dotnet-install.sh --channel 10.0 && \
    echo "DOTNET 10 installed successfully"

ENV DOTNET_ROOT=/root/.dotnet
ENV PATH=/root/.dotnet:$PATH
ENV DEBIAN_FRONTEND=noninteractive
