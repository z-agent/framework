import asyncio
import logging
from typing import AsyncGenerator, Dict, Any
from datetime import datetime, timezone
import json
import threading
import queue
import io
import sys
from contextlib import redirect_stdout, redirect_stderr

class LogStreamer:
    """Real-time log streaming for agent executions"""
    
    def __init__(self):
        self.active_streams = {}
        self.log_queues = {}
        
    def start_stream(self, execution_id: str) -> queue.Queue:
        """Start a new log stream for an execution"""
        log_queue = queue.Queue()
        self.log_queues[execution_id] = log_queue
        self.active_streams[execution_id] = True
        return log_queue
    
    def stop_stream(self, execution_id: str):
        """Stop log stream for an execution"""
        if execution_id in self.active_streams:
            self.active_streams[execution_id] = False
        if execution_id in self.log_queues:
            del self.log_queues[execution_id]
    
    def emit_log(self, execution_id: str, log_type: str, message: str, **kwargs):
        """Emit a log event to the stream"""
        if execution_id in self.log_queues:
            event = {
                'type': log_type,
                'message': message,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                **kwargs
            }
            try:
                self.log_queues[execution_id].put_nowait(event)
            except queue.Full:
                pass  # Drop logs if queue is full
    
    async def stream_logs(self, execution_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Async generator for streaming logs"""
        if execution_id not in self.log_queues:
            return
        
        log_queue = self.log_queues[execution_id]
        
        while self.active_streams.get(execution_id, False):
            try:
                # Non-blocking get with timeout
                event = log_queue.get(timeout=0.1)
                yield event
            except queue.Empty:
                await asyncio.sleep(0.1)
                continue
            except Exception as e:
                print(f"Log streaming error: {e}")
                break

class LogCapturingHandler(logging.Handler):
    """Custom logging handler to capture logs for streaming"""
    
    def __init__(self, log_streamer: LogStreamer, execution_id: str):
        super().__init__()
        self.log_streamer = log_streamer
        self.execution_id = execution_id
        
    def emit(self, record):
        """Capture log records and emit to stream"""
        try:
            message = self.format(record)
            
            # Parse different types of log messages
            log_type = 'info'
            if 'ERROR' in message or '❌' in message:
                log_type = 'error'
            elif 'WARNING' in message or '⚠️' in message:
                log_type = 'warning'
            elif 'Creating agent' in message:
                log_type = 'agent_creation'
            elif 'Executing' in message and 'task' in message:
                log_type = 'task_execution'
            elif 'Tool' in message and 'executed' in message:
                log_type = 'tool_execution'
            elif 'completed' in message.lower():
                log_type = 'completion'
            
            self.log_streamer.emit_log(
                self.execution_id,
                log_type,
                message,
                level=record.levelname
            )
        except Exception as e:
            print(f"Error capturing log: {e}")

# Global log streamer instance
log_streamer = LogStreamer()