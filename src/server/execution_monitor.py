import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class ExecutionMonitor:
    """Real-time execution monitoring for streaming"""
    
    def __init__(self):
        self.active_executions = {}
        self.tool_calls = {}
        self.execution_results = {}
    
    def start_execution(self, execution_id: str, agent_id: str):
        """Start monitoring an execution"""
        self.active_executions[execution_id] = {
            'agent_id': agent_id,
            'start_time': datetime.now(timezone.utc),
            'tool_calls': [],
            'progress_updates': [],
            'status': 'running',
            'current_step': 'initialized',
            'step_count': 0
        }
        logger.info(f"🔍 Started monitoring execution: {execution_id}")
    
    def update_progress(self, execution_id: str, step: str, message: str, details: Any = None):
        """Update execution progress with current step"""
        if execution_id in self.active_executions:
            progress_update = {
                'step': step,
                'message': message,
                'details': str(details)[:200] + '...' if details and len(str(details)) > 200 else details,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'step_number': self.active_executions[execution_id]['step_count'] + 1
            }
            self.active_executions[execution_id]['progress_updates'].append(progress_update)
            self.active_executions[execution_id]['current_step'] = step
            self.active_executions[execution_id]['step_count'] += 1
            logger.info(f"📊 Progress update: {step} - {message} for execution {execution_id}")
    
    def log_tool_call(self, execution_id: str, tool_name: str, input_data: Any, output_data: Any):
        """Log a tool call with input/output data"""
        if execution_id in self.active_executions:
            tool_call = {
                'tool_name': tool_name,
                'input': str(input_data)[:500] + '...' if len(str(input_data)) > 500 else str(input_data),
                'output': str(output_data)[:1000] + '...' if len(str(output_data)) > 1000 else str(output_data),
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'execution_time': None,  # Will be set when tool completes
                'step_number': self.active_executions[execution_id]['step_count'] + 1
            }
            self.active_executions[execution_id]['tool_calls'].append(tool_call)
            self.active_executions[execution_id]['step_count'] += 1
            logger.info(f"🔧 Tool call logged: {tool_name} for execution {execution_id}")
    
    def log_tool_execution(self, execution_id: str, tool_name: str, input_data: Any, output_data: Any):
        """Log a tool execution (alias for log_tool_call for compatibility)"""
        self.log_tool_call(execution_id, tool_name, input_data, output_data)
    
    def log_agent_step(self, execution_id: str, agent_name: str, action: str, details: Any = None):
        """Log an agent's step in the execution"""
        if execution_id in self.active_executions:
            agent_step = {
                'agent_name': agent_name,
                'action': action,
                'details': str(details)[:300] + '...' if details and len(str(details)) > 300 else details,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'step_number': self.active_executions[execution_id]['step_count'] + 1
            }
            self.active_executions[execution_id]['progress_updates'].append(agent_step)
            self.active_executions[execution_id]['step_count'] += 1
            logger.info(f"🤖 Agent step: {agent_name} - {action} for execution {execution_id}")
    
    def log_task_completion(self, execution_id: str, task_name: str, result: Any):
        """Log completion of a specific task"""
        if execution_id in self.active_executions:
            task_completion = {
                'task_name': task_name,
                'result': str(result)[:400] + '...' if len(str(result)) > 400 else str(result),
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'step_number': self.active_executions[execution_id]['step_count'] + 1
            }
            self.active_executions[execution_id]['progress_updates'].append(task_completion)
            self.active_executions[execution_id]['step_count'] += 1
            logger.info(f"✅ Task completed: {task_name} for execution {execution_id}")
    
    def complete_execution(self, execution_id: str, result: Any):
        """Complete execution monitoring"""
        if execution_id in self.active_executions:
            self.active_executions[execution_id]['status'] = 'completed'
            self.active_executions[execution_id]['end_time'] = datetime.now(timezone.utc)
            self.active_executions[execution_id]['result'] = str(result)[:2000] + '...' if len(str(result)) > 2000 else str(result)
            self.active_executions[execution_id]['current_step'] = 'completed'
            logger.info(f"✅ Execution completed: {execution_id}")
    
    def get_execution_status(self, execution_id: str) -> Optional[Dict]:
        """Get current execution status"""
        return self.active_executions.get(execution_id)
    
    def get_agent_executions(self, agent_id: str) -> list:
        """Get all executions for a specific agent"""
        return [
            exec_data for exec_data in self.active_executions.values() 
            if exec_data['agent_id'] == agent_id
        ]
    
    def get_execution_summary(self, execution_id: str) -> Optional[Dict]:
        """Get a summary of execution progress and results"""
        if execution_id not in self.active_executions:
            return None
        
        exec_data = self.active_executions[execution_id]
        return {
            'execution_id': execution_id,
            'agent_id': exec_data['agent_id'],
            'status': exec_data['status'],
            'current_step': exec_data['current_step'],
            'total_steps': exec_data['step_count'],
            'tool_calls_count': len(exec_data.get('tool_calls', [])),
            'progress_updates_count': len(exec_data.get('progress_updates', [])),
            'start_time': exec_data.get('start_time'),
            'end_time': exec_data.get('end_time'),
            'duration': (exec_data.get('end_time') - exec_data.get('start_time')).total_seconds() if exec_data.get('end_time') and exec_data.get('start_time') else None
        }

# Global execution monitor instance
execution_monitor = ExecutionMonitor()
