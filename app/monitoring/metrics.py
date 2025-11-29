import time

class Metrics:
    def __init__(self):
        # Global variables
        self.latencies = []
        self.msg_count = 0
        self.start = time.time()

    def record_latency(self, ns):
        # store milliseconds
        self.latencies.append(ns / 1e6)
        self.msg_count += 1

    def summary(self):
        if not self.latencies:
            return 0, 0
        
        elapsed = time.time() - self.start 
        throughput = self.msg_count / elapsed
        
        lat_sorted = sorted(self.latencies) 
        p99 = lat_sorted[int(0.99 * len(self.latencies))]

        return throughput, p99
    
    def reset(self):
        self.latencies = []
        self.msg_count = 0
        self.start = time.time()