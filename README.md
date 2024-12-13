# netcat test framework

I used a container.

```sh
docker run -it --rm -v .:/root/ncwarts --workdir /root/ncwarts --cap-add=SYS_PTRACE debian:testing
```

Here's some commands for setting up various implementations and tools.

```sh
cat >/etc/apt/sources.list.d/debug.list <<EOF
deb http://deb.debian.org/debian-debug testing-debug main
EOF
cat >/etc/apt/sources.list.d/sources.list <<EOF
deb-src http://deb.debian.org/debian testing main
EOF
apt update && apt install netcat-openbsd netcat-traditional socat ncat tcputils netpipes busybox toybox inetutils-telnet \
  python3 procps iproute2 strace less gdb build-essential golang-go git curl

go install github.com/u-root/u-root/cmds/core/netcat@v0.14.0

curl -L 'https://sourceforge.net/projects/netcat/files/netcat/0.7.1/netcat-0.7.1.tar.gz/download' | tar -xzv
(cd netcat-0.7.1 && ./configure && make)
```

And then you run a test.

```sh
python3 exp.py netcat-openbsd client out_filled
```
