import os
import socket
import subprocess
import sys
import threading
import time

fill_bytes = b'0' * (1 << 20)
one_byte = b'1'
hostname = '127.0.0.1'
port = 9988
port_str = str(port)
strace = False
telnet = False

def out_fill(nc, sock):
  print('out fill stdin writing', file=sys.stderr)
  try:
    total = 0
    n = nc.stdin.write(fill_bytes[:512])
    total += n
    print('out fill stdin wrote %d bytes' % total, file=sys.stderr)
    time.sleep(0.5)
    while True:
      n = nc.stdin.write(fill_bytes)
      total += n
      print('out fill stdin wrote %d bytes' % total, file=sys.stderr)
  except BrokenPipeError:
    print('out fill done', file=sys.stderr)

def in_fill(nc, sock):
  print('in fill socket sending', file=sys.stderr)
  try:
    total = 0
    n = sock.send(fill_bytes[:512]) # %%%
    total += n
    print('in fill socket sent %d bytes' % total, file=sys.stderr)
    time.sleep(0.5)
    while True:
      n = sock.send(fill_bytes)
      total += n
      print('in fill socket sent %d bytes' % total, file=sys.stderr)
  except BrokenPipeError:
    print('in fill done', file=sys.stderr)

def out_fill_thread(nc, sock):
  t = threading.Thread(target=out_fill, args=(nc, sock))
  t.start()
  return t

def in_fill_thread(nc, sock):
  t = threading.Thread(target=in_fill, args=(nc, sock))
  t.start()
  return t

def out_one(nc, sock):
  print('out one stdin writing one %r' % one_byte, file=sys.stderr)
  nc.stdin.write(one_byte)
  print('out one socket receiving data', file=sys.stderr)
  data = sock.recv(4096)
  print('out one socket received %r' % data, file=sys.stderr)
  if data != one_byte:
    raise Exception('wrote %r, received %r' % (one_byte, data))

def in_one(nc, sock):
  print('in one socket sending %r' % one_byte, file=sys.stderr)
  sock.send(one_byte)
  print('in one stdout reading data', file=sys.stderr)
  data = nc.stdout.read(4096)
  print('in one stdout read %r' % data, file=sys.stderr)
  if data != one_byte:
    raise Exception('sent %r, read %r' % (one_byte, data))

def out_eof_close(nc, sock):
  print('out eof stdin closing', file=sys.stderr)
  nc.stdin.close()

def in_eof_shutdown(nc, sock):
  print('in eof socket shutting down write', file=sys.stderr)
  sock.shutdown(socket.SHUT_WR)

def out_eof_recv(nc, sock):
  print('out eof socket receiving eof', file=sys.stderr)
  eof = sock.recv(4096)
  print('out eof socket received %r' % eof, file=sys.stderr)
  if eof:
    raise Exception('closed, received %r' % eof)

def in_eof_read(nc, sock):
  print('in eof stdout reading eof', file=sys.stderr)
  eof = nc.stdout.read(4096)
  print('in eof stdout read %r' % eof, file=sys.stderr)
  if eof:
    raise Exception('shut down write, read %r' % eof)

def out_eof(nc, sock):
  out_eof_close(nc, sock)
  out_eof_recv(nc, sock)

def in_eof(nc, sock):
  in_eof_shutdown(nc, sock)
  in_eof_read(nc, sock)

def out_general(nc, sock):
  for i in range(10):
    print('attempt %d' % (i + 1), file=sys.stderr)
    out_one(nc, sock)
  out_eof(nc, sock)
  print('good', file=sys.stderr)

def in_general(nc, sock):
  for i in range(10):
    print('attempt %d' % (i + 1), file=sys.stderr)
    in_one(nc, sock)
  in_eof(nc, sock)
  print('good', file=sys.stderr)

def behavior_out_quiet(nc, sock):
  time.sleep(1)
  in_general(nc, sock)
  out_eof_close(nc, sock)

def behavior_in_quiet(nc, sock):
  time.sleep(1)
  out_general(nc, sock)
  in_eof_shutdown(nc, sock)

def behavior_out_filled(nc, sock):
  fill_t = out_fill_thread(nc, sock)
  time.sleep(1)
  in_general(nc, sock)
  print('nc terminating', file=sys.stderr)
  nc.terminate()
  print('fill thread joining', file=sys.stderr)
  fill_t.join()

def behavior_in_filled(nc, sock):
  fill_t = in_fill_thread(nc, sock)
  time.sleep(1)
  out_general(nc, sock)
  print('nc terminating', file=sys.stderr)
  nc.terminate()
  print('fill thread joining', file=sys.stderr)
  fill_t.join()

def behavior_out_done(nc, sock):
  out_eof_close(nc, sock)
  time.sleep(1)
  in_general(nc, sock)

def behavior_in_done(nc, sock):
  in_eof_shutdown(nc, sock)
  time.sleep(1)
  out_general(nc, sock)

behaviors = {
  'out_quiet': behavior_out_quiet,
  'in_quiet': behavior_in_quiet,
  'out_filled': behavior_out_filled,
  'in_filled': behavior_in_filled,
  'out_done': behavior_out_done,
  'in_done': behavior_in_done,
}

def test_client(command, behavior):
  sock_listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  sock_listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
  sock_listener.bind((hostname, port))
  sock_listener.listen(1)
  nc = subprocess.Popen(command, bufsize=0, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
  sock, _ = sock_listener.accept()
  if telnet:
    print('telnet junk:', next(nc.stdout), file=sys.stderr)
    print('telnet junk:', next(nc.stdout), file=sys.stderr)
    print('telnet junk:', next(nc.stdout), file=sys.stderr)
  try:
    behavior(nc, sock)
  except:
    print('behavior raised', file=sys.stderr)
    print('nc terminating', file=sys.stderr)
    nc.terminate()
    raise
  finally:
    print('nc waiting', file=sys.stderr)
    rv = nc.wait()
    print('nc exit %d' % rv, file=sys.stderr)
  sock_listener.close()

def test_server(command, behavior):
  nc = subprocess.Popen(command, bufsize=0, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
  time.sleep(1)
  sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  sock.connect((hostname, port))
  try:
    behavior(nc, sock)
  except:
    print('behavior raised', file=sys.stderr)
    print('nc terminating', file=sys.stderr)
    nc.terminate()
    raise
  finally:
    print('nc waiting', file=sys.stderr)
    rv = nc.wait()
    print('nc exit %d' % rv, file=sys.stderr)

side_tests = {
  'client': test_client,
  'server': test_server,
}

impls = {
  'netcat-traditional': {
    'client': ('nc.traditional', hostname, port_str),
    'server': ('nc.traditional', '-l', '-s', hostname, '-p', port_str),
  },
  'netcat-traditional-q': {
    'client': ('nc.traditional', '-q', '0', hostname, port_str),
    'server': ('nc.traditional', '-q', '0', '-l', '-s', hostname, '-p', port_str),
  },
  'netcat-traditional-qq': {
    'client': ('nc.traditional', '-q', '999999999', hostname, port_str),
    'server': ('nc.traditional', '-q', '999999999', '-l', '-s', hostname, '-p', port_str),
  },
  'telnet': {
    'client': ('telnet', hostname, port_str),
  },
  'netcat-openbsd': {
    'client': ('nc.openbsd', hostname, port_str),
    'server': ('nc.openbsd', '-l', hostname, port_str),
  },
  'netcat-openbsd-n': {
    'client': ('nc.openbsd', '-N', hostname, port_str),
    'server': ('nc.openbsd', '-N', '-l', hostname, port_str),
  },
  'netcat6': {
    'client': ('nc6', hostname, port_str),
    'server': ('nc6', '-l', '-s', hostname, '-p', port_str),
  },
  'netcat6-h': {
    'client': ('nc6', '--half-close', '--hold-timeout', '-:-', hostname, port_str),
    'server': ('nc6', '--half-close', '--hold-timeout', '-:-', '-l', '-s', hostname, '-p', port_str),
  },
  'netcat-giacobbi': {
    'client': ('./netcat-0.7.1/src/netcat', hostname, port_str),
    'server': ('./netcat-0.7.1/src/netcat', '-l', '-s', hostname, '-p', port_str),
  },
  'socat': {
    'client': ('socat', '-', 'TCP:%s:%s' % (hostname, port_str)),
    'server': ('socat', '-', 'TCP-LISTEN:%s,bind=%s' % (port_str, hostname)),
  },
  'socat-t': {
    'client': ('socat', '-t', '999999999', '-', 'TCP:%s:%s' % (hostname, port_str)),
    'server': ('socat', '-t', '999999999', '-', 'TCP-LISTEN:%s,bind=%s' % (port_str, hostname)),
  },
  'ncat': {
    'client': ('ncat', hostname, port_str),
    'server': ('ncat', '-l', hostname, port_str),
  },
  'tcputils': {
    'client': ('tcpconnect', hostname, port_str),
    'server': ('tcplisten', hostname, port_str),
  },
  'netpipes': {
    'client': ('hose', hostname, port_str, '--slave'),
  },
  'netpipes-3': {
    'client': ('hose', hostname, port_str, '--fd', '3', 'sh', '-c', 'cat <&3 & exec >- && cat >&3 && sockdown 3 && wait'),
    'server': ('faucet', port_str, '--fd', '3', '--once', 'sh', '-c', 'cat <&3 & exec >- && cat >&3 && sockdown 3 && wait'),
  },
  'busybox': {
    'client': ('busybox', 'nc', hostname, port_str),
    'server': ('busybox', 'nc', '-l', hostname, '-p', port_str),
  },
  'toybox': {
    'client': ('toybox', 'nc', hostname, port_str),
    'server': ('toybox', 'nc', '-l', '-s', hostname, '-p', port_str),
  },
  'u-root': {
    'client': (os.path.expanduser('~/go/bin/netcat'), '%s:%s' % (hostname, port_str)),
    'server': (os.path.expanduser('~/go/bin/netcat'), '-l', '%s:%s' % (hostname, port_str)),
  },
  'bash': {
    'client': ('bash', 'nc.sh', hostname, port_str),
  },
  'python': {
    'client': ('python3', 'nc.py', hostname, port_str),
    'server': ('python3', 'ncl.py', hostname, port_str),
  },
  'perl': {
    'client': ('perl', 'nc.pl', hostname, port_str),
    'server': ('perl', 'ncl.pl', hostname, port_str),
  },
}

args = sys.argv[1:]
if args[0] == '-t':
  strace = True
  args = args[1:]
impl_name, side_name, behavior_name = args

side_test = side_tests[side_name]
impl = impls[impl_name][side_name]
behavior = behaviors[behavior_name]
if strace:
  impl = ('strace', '-tt') + impl
side_test(impl, behavior)
