import socket
import time
import random
from cryptography.fernet import Fernet

SERVER_IP = "192.168.40.130"
PORT = 9999

key = b'7QluHyBCTCsVy9G-qMHrV9paH2fw-BnawNacDG5pUIg='
cipher = Fernet(key)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

paths = ["/api/data", "/api/metrics", "/api/health", "/api/stream", "/api/events"]
methods = ["GET", "POST"]

while True:
    timestamp = time.time()
    method = random.choice(methods)
    path = random.choice(paths)
    status = random.choice([200, 200, 200, 404, 500, 503])
    size = random.randint(50, 500)

    log = f"CLIENT2|{timestamp}|192.168.1.11|{method}|{path}|{status}|{size}B"

    encrypted = cipher.encrypt(log.encode())
    sock.sendto(encrypted, (SERVER_IP, PORT))

    time.sleep(random.uniform(0.3, 1.2))
