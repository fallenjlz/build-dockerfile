FROM openresty/openresty:1.21.4.1-0-bullseye-fat
RUN apt clean && \
    apt update && \
    apt install -y vim && \
    apt install -y less && \
    apt install -y procps && \
    apt install -y net-tools && \
    apt install -y telnet && \
    apt install -y curl
COPY openresty-systemtap-toolkit/ /usr/local/openresty/openresty-systemtap-toolkit/
COPY stapxx/ /usr/local/openresty/stapxx/
COPY FlameGraph/ /usr/local/openresty/FlameGraph/
  
