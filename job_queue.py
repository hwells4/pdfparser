"""
In-Memory Job Queue System
Handles serialization of PDF processing jobs to avoid race conditions
"""

import threading
import time
from typing import Dict, Any, Optional
from collections import deque
import logging

logger = logging.getLogger(__name__)


class JobQueue:
    """Thread-safe in-memory job queue for PDF processing tasks"""
    
    def __init__(self):
        self._queue = deque()
        self._lock = threading.Lock()
        self._job_counter = 0
        
    def add_job(self, job_data: Dict[str, Any]) -> int:
        """
        Add a new job to the queue
        
        Args:
            job_data: Dictionary containing job information
            
        Returns:
            Position in queue (1-based)
        """
        with self._lock:
            self._job_counter += 1
            job = {
                "id": self._job_counter,
                "data": job_data,
                "created_at": time.time(),
                "status": "queued"
            }
            self._queue.append(job)
            position = len(self._queue)
            
            logger.info(f"Added job {job['id']} to queue at position {position}")
            return position
    
    def get_next_job(self) -> Optional[Dict[str, Any]]:
        """
        Get the next job from the queue
        
        Returns:
            Next job dictionary or None if queue is empty
        """
        with self._lock:
            if self._queue:
                job = self._queue.popleft()
                job["status"] = "processing"
                job["started_at"] = time.time()
                logger.info(f"Retrieved job {job['id']} from queue")
                return job
            return None
    
    def size(self) -> int:
        """
        Get current queue size
        
        Returns:
            Number of jobs in queue
        """
        with self._lock:
            return len(self._queue)
    
    def is_empty(self) -> bool:
        """
        Check if queue is empty
        
        Returns:
            True if queue is empty, False otherwise
        """
        with self._lock:
            return len(self._queue) == 0
    
    def get_queue_status(self) -> Dict[str, Any]:
        """
        Get detailed queue status
        
        Returns:
            Dictionary with queue statistics
        """
        with self._lock:
            return {
                "size": len(self._queue),
                "total_jobs_processed": self._job_counter,
                "oldest_job_age": (
                    time.time() - self._queue[0]["created_at"] 
                    if self._queue else 0
                )
            } 