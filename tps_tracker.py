"""TPS (Transactions Per Second) tracking utility for PingOne API operations.

This module provides a simple tracker to measure transaction throughput during
bulk import/export operations, calculating average, mean, and peak TPS metrics.
"""

import time
from collections import defaultdict
from typing import Dict, List


class TPSTracker:
    """Tracks transactions per second and calculates statistics.
    
    The tracker records timestamps of each transaction and can calculate:
    - Average TPS: total transactions / total elapsed time
    - Mean TPS: average of all 1-second window TPS values
    - Peak TPS: maximum TPS achieved in any 1-second window
    """
    
    def __init__(self):
        """Initialize a new TPS tracker."""
        self.transaction_times: List[float] = []
        self.start_time: float = None
        self.end_time: float = None
        
    def start(self):
        """Mark the start of tracking."""
        self.start_time = time.time()
        self.transaction_times = []
        
    def record_transaction(self):
        """Record a single transaction at the current time."""
        if self.start_time is None:
            self.start()
        self.transaction_times.append(time.time())
        
    def finish(self):
        """Mark the end of tracking."""
        self.end_time = time.time()
        
    def get_statistics(self) -> Dict[str, float]:
        """Calculate and return TPS statistics.
        
        Returns:
            Dictionary with keys:
            - total_transactions: Total number of transactions recorded
            - total_duration: Total elapsed time in seconds
            - average_tps: Total transactions / total duration
            - mean_tps: Average of all 1-second window TPS values
            - peak_tps: Maximum TPS in any 1-second window
        """
        if not self.transaction_times:
            return {
                "total_transactions": 0,
                "total_duration": 0.0,
                "average_tps": 0.0,
                "mean_tps": 0.0,
                "peak_tps": 0.0,
            }
        
        total_transactions = len(self.transaction_times)
        
        # Use end_time if set, otherwise use the last transaction time
        end = self.end_time if self.end_time else self.transaction_times[-1]
        total_duration = end - self.start_time
        
        # Calculate average TPS
        average_tps = total_transactions / total_duration if total_duration > 0 else 0.0
        
        # Calculate per-second buckets for mean and peak TPS
        # Group transactions by 1-second windows
        second_buckets = defaultdict(int)
        for tx_time in self.transaction_times:
            # Floor to the nearest second relative to start_time
            second_bucket = int(tx_time - self.start_time)
            second_buckets[second_bucket] += 1
        
        # Calculate mean and peak TPS from the buckets
        if second_buckets:
            tps_values = list(second_buckets.values())
            mean_tps = sum(tps_values) / len(tps_values)
            peak_tps = max(tps_values)
        else:
            mean_tps = 0.0
            peak_tps = 0.0
        
        return {
            "total_transactions": total_transactions,
            "total_duration": total_duration,
            "average_tps": average_tps,
            "mean_tps": mean_tps,
            "peak_tps": peak_tps,
        }
