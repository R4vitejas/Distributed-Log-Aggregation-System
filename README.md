# Distributed Log Aggregation System

## Overview

A real-time distributed log aggregation system that collects encrypted logs from multiple clients over UDP, processes them, and visualizes system performance.

---

## Features

* Real-time UDP log ingestion
* Encryption using Fernet
* Throughput monitoring (logs/sec)
* Time-ordered logs
* Congestion tracking
* Backpressure with spill to disk
* Latency simulation
* Packet loss simulation
* Multi-client system
* Live dashboard

---

## Setup

Install dependencies:

```
pip install flask cryptography
```

---

## Run

Start server:

```
python server.py
```

Open dashboard:

```
http://localhost:5000
```

Run clients:

```
python client1.py
python client2.py
```

---

## Architecture

Clients → UDP → Server → Processing → Dashboard

---

## Contributors

* Ravitejas
* Kavya Pandappa Korti
* Shreyas K
