import os
import socket
import sys
import threading

def pump_down():
  while True:
    buf = sock.recv(16384)
    if not buf:
      break
    n = os.write(1, buf)
    if n < len(buf):
      exit(1)
  os.close(1)

def pump_up():
  while True:
    buf = os.read(0, 16384)
    if not buf:
      break
    n = sock.send(buf)
    if n < len(buf):
      exit(1)
  sock.shutdown(socket.SHUT_WR)

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((sys.argv[1], int(sys.argv[2])))
t_down = threading.Thread(target=pump_down)
t_up = threading.Thread(target=pump_up)
t_down.start()
t_up.start()

t_down.join()
t_up.join()
