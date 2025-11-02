"""
Paper-out job queue for printer receiver
Holds print jobs when paper is out and processes them when paper becomes available
"""
import threading
import time
from datetime import datetime
from typing import List, Dict, Optional
import json
from pathlib import Path


class PrintJobQueue:
    """Queue to hold print jobs when paper is out"""
    
    def __init__(self, queue_file: Path):
        self.queue: List[Dict] = []
        self.queue_file = queue_file
        self.lock = threading.Lock()
        self.check_interval = 45  # Start checking every 45 seconds
        self.max_interval = 3600  # Max interval: 1 hour
        self.check_thread: Optional[threading.Thread] = None
        self.running = False
        self.load_queue()
    
    def add_job(self, job_data: Dict):
        """Add a job to the queue"""
        with self.lock:
            job_data['queued_at'] = datetime.utcnow().isoformat()
            self.queue.append(job_data)
            self.save_queue()
            print(f"[JobQueue] Job queued ({len(self.queue)} total)")
    
    def get_all_jobs(self) -> List[Dict]:
        """Get all queued jobs"""
        with self.lock:
            return self.queue.copy()
    
    def clear_queue(self):
        """Clear all jobs from the queue"""
        with self.lock:
            count = len(self.queue)
            self.queue.clear()
            self.save_queue()
            if count > 0:
                print(f"[JobQueue] Queue cleared ({count} jobs processed)")
    
    def queue_size(self) -> int:
        """Get current queue size"""
        with self.lock:
            return len(self.queue)
    
    def save_queue(self):
        """Save queue to disk"""
        try:
            with open(self.queue_file, 'w') as f:
                json.dump(self.queue, f, indent=2)
        except Exception as e:
            print(f"[JobQueue] Error saving queue: {e}")
    
    def load_queue(self):
        """Load queue from disk"""
        try:
            if self.queue_file.exists():
                with open(self.queue_file, 'r') as f:
                    self.queue = json.load(f)
                if len(self.queue) > 0:
                    print(f"[JobQueue] Loaded {len(self.queue)} queued job(s) from disk")
        except Exception as e:
            print(f"[JobQueue] Error loading queue: {e}")
            self.queue = []
    
    def start_periodic_check(self, check_paper_func, print_func):
        """Start periodic paper checking in background thread"""
        if self.running:
            return
        
        self.running = True
        self.check_thread = threading.Thread(
            target=self._periodic_check_loop,
            args=(check_paper_func, print_func),
            daemon=True
        )
        self.check_thread.start()
        print(f"[JobQueue] Paper check started (checking every {self.check_interval}s)")
    
    def stop_periodic_check(self):
        """Stop periodic checking"""
        self.running = False
        if self.check_thread:
            self.check_thread.join(timeout=2)
    
    def _periodic_check_loop(self, check_paper_func, print_func):
        """Periodic check loop with exponential backoff"""
        consecutive_failures = 0
        
        while self.running:
            queue_size = self.queue_size()
            
            if queue_size > 0:
                # Check if paper is available
                paper_status = check_paper_func()
                
                if paper_status.get('paper_ok', False):
                    print(f"[JobQueue] Paper available - printing {queue_size} queued job(s)")
                    consecutive_failures = 0
                    
                    # Process all queued jobs
                    jobs = self.get_all_jobs()
                    all_succeeded = True
                    
                    for job in jobs:
                        result = print_func(job['escpos_data'])
                        if not result.get('success', False):
                            print(f"[JobQueue] Failed to print queued job: {result.get('message')}")
                            all_succeeded = False
                            break
                        time.sleep(0.5)  # Small delay between jobs
                    
                    if all_succeeded:
                        print(f"[JobQueue] Successfully printed {queue_size} queued job(s)")
                        self.clear_queue()
                        self.check_interval = 45
                        sleep_time = 45
                    else:
                        # If printing failed, keep jobs in queue and increase interval
                        print(f"[JobQueue] Some jobs failed, keeping {queue_size} jobs in queue")
                        self.check_interval = min(int(self.check_interval * 1.5), self.max_interval)
                        sleep_time = self.check_interval
                else:
                    consecutive_failures += 1
                    # Increase check interval with exponential backoff (up to max)
                    self.check_interval = min(int(self.check_interval * 1.5), self.max_interval)
                    sleep_time = self.check_interval
            
            # If no queue, keep checking at base interval
            if queue_size == 0:
                sleep_time = 45
            
            # Sleep, but check self.running periodically
            for _ in range(int(sleep_time)):
                if not self.running:
                    return
                time.sleep(1)


# Global queue instance
_queue: Optional[PrintJobQueue] = None


def get_queue() -> PrintJobQueue:
    """Get or create the global queue instance"""
    global _queue
    if _queue is None:
        queue_file = Path('print_logs') / 'paper_out_queue.json'
        queue_file.parent.mkdir(exist_ok=True)
        _queue = PrintJobQueue(queue_file)
    return _queue

