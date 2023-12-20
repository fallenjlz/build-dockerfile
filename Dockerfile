# Use Ubuntu 22.04 as the base image
FROM ubuntu:22.04

# Install dependencies available via apt
RUN apt-get update && apt-get install -y \
    git \
    make \
    jq \
    direnv \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Manually install Golang 1.21
ENV GOLANG_VERSION=1.21.5
RUN curl -L "https://golang.org/dl/go${GOLANG_VERSION}.linux-amd64.tar.gz" | tar -C /usr/local -xzf -
ENV PATH="/usr/local/go/bin:${PATH}"

# Install nvm, Node.js, and npm
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g npm@latest \
    && npm install -g pnpm@8

# Install Foundry (forge)
RUN curl -L https://foundry.paradigm.xyz | bash \
    && . /root/.bashrc \
    && foundryup

# Set environment variables and paths
ENV PATH="/root/.foundry/bin:${PATH}"

# Check versions
RUN git --version \
    && go version \
    && node --version \
    && npm --version \
    && pnpm --version \
    && forge --version \
    && make --version \
    && jq --version \
    && direnv --version

COPY . /root
WORKDIR /root/scripts
RUN go mod download
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o main . \
    && ./main


# Set the working directory
WORKDIR /workspace

# Default command
CMD ["bash"]
