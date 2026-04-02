import socket
import time
import random
from cryptography.fernet import Fernet

SERVER_IP = "192.168.40.130"
PORT = 9999

key = b'7QluHyBCTCsVy9G-qMHrV9paH2fw-BnawNacDG5pUIg='
cipher = Fernet(key)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

methods = ["GET", "POST", "PUT", "DELETE"]
paths = ["/home", "/products", "/cart", "/login", "/checkout", "/profile", "/api/users"]

while True:
    timestamp = time.time()
    method = random.choice(methods)
    path = random.choice(paths)
    status = random.choice([200, 200, 200, 201, 301, 400, 404, 500])
    size = random.randint(100, 1000)

    log = f"CLIENT1|{timestamp}|192.168.1.10|{method}|{path}|{status}|{size}B"

    encrypted = cipher.encrypt(log.encode())
    sock.sendto(encrypted, (SERVER_IP, PORT))

    time.sleep(random.uniform(0.5, 1.5))
