"""
Execution logger for tracking task executions.
Replaces multiple log lists with a unified logging system.
"""

import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from .task import Task


@dataclass
class ExecutionLog:
    """Execution log entry with dataflow tracking"""
    step: int
    action: str
    target: str
    result: str
    extra_actions: Optional[List[Dict[str, Any]]] = None
    dataflow_info: Optional[Dict[str, Any]] = None
    tool_usage: Optional[List[Dict[str, Any]]] = None
    security_analysis: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "step": self.step,
            "action": self.action,
            "target": self.target,
            "result": self.result
        }
        if self.extra_actions:
            data["extra_actions"] = self.extra_actions
        if self.dataflow_info:
            data["dataflow_analysis"] = self.dataflow_info
        if self.tool_usage:
            data["tool_usage"] = self.tool_usage
        if self.security_analysis:
            data["security_analysis"] = self.security_analysis
        return data


class ExecutionLogger:
    """Simplified execution logging system"""

    def __init__(self):
        self._logs: List[ExecutionLog] = []
        self._step_counter = 0

    def log_execution(self, task: Task, result: Dict[str, Any], step: int,
                     extra_actions: Optional[List[Dict[str, Any]]] = None) -> None:
        """Record a task execution with dataflow trace logging"""
        success = result.get("success", False)

        # Extract dataflow and tool information from security analysis
        dataflow_info = None
        tool_usage = None
        security_analysis = None

        if success and "security_result" in result:
            sec_result = result["security_result"]
            agent_analysis = sec_result.get("agent_analysis", {})
            
            # Extract dataflow information
            if agent_analysis.get("dataflow_patterns"):
                dataflow_info = {
                    "patterns_count": len(agent_analysis["dataflow_patterns"]),
                    "high_risk_flows": [
                        flow for flow in agent_analysis["dataflow_patterns"] 
                        if flow.get("risk_level") == "HIGH"
                    ],
                    "external_input_flows": [
                        flow for flow in agent_analysis["dataflow_patterns"]
                        if flow.get("external_input") == "yes"
                    ]
                }

            # Extract tool usage information
            if agent_analysis.get("agent_tools"):
                tool_usage = [
                    {
                        "tool_name": tool.get("tool_name", "unknown"),
                        "tool_type": tool.get("tool_type", "unknown"),
                        "security_implications": tool.get("security_implications", "unknown")
                    }
                    for tool in agent_analysis["agent_tools"]
                ]

            # Extract security analysis summary
            security_analysis = {
                "risk_level": sec_result.get("risk_assessment", {}).get("overall_risk", "UNKNOWN"),
                "findings_count": len(sec_result.get("findings", [])),
                "tool_summary": agent_analysis.get("tool_summary", "")
            }

        # Create result description
        if success:
            if task.type.value == "explore":
                task_result = result.get("result", {})
                files_count = len(task_result.get("files", []))
                dirs_count = len(task_result.get("directories", []))
                result_desc = f"Found {files_count} files, {dirs_count} directories"
            elif task.type.value == "read":
                task_result = result.get("result", {})
                lines = task_result.get("total_lines", task_result.get("lines_read", task_result.get("lines", 0)))
                
                # Add dataflow context to result description
                if dataflow_info and dataflow_info["patterns_count"] > 0:
                    result_desc = f"Read {lines} lines, found {dataflow_info['patterns_count']} dataflow patterns"
                    if dataflow_info["high_risk_flows"]:
                        result_desc += f", {len(dataflow_info['high_risk_flows'])} high-risk flows"
                else:
                    result_desc = f"Read {lines} lines"
            else:
                result_desc = "Completed"
        else:
            error_msg = result.get("error", "Unknown error")
            result_desc = f"Failed: {error_msg}"

        log_entry = ExecutionLog(
            step=step,
            action=task.type.value.upper(),
            target=task.target,
            result=result_desc,
            extra_actions=extra_actions,
            dataflow_info=dataflow_info,
            tool_usage=tool_usage,
            security_analysis=security_analysis
        )

        self._logs.append(log_entry)
    
    def get_recent_logs(self, n: int = 10) -> List[ExecutionLog]:
        """Get the most recent n log entries"""
        return self._logs[-n:] if n > 0 else self._logs
    
    def get_summary(self) -> Dict[str, Any]:
        """Get simplified execution statistics summary"""
        if not self._logs:
            return {"total_executions": 0}

        return {
            "total_executions": len(self._logs),
            "latest_step": max((log.step for log in self._logs), default=0)
        }

    def get_trace_logs(self) -> List[Dict[str, Any]]:
        """Get all execution logs in trace format"""
        return [log.to_dict() for log in self._logs]
    
    def get_logs_by_action(self, action: str) -> List[ExecutionLog]:
        """Get all logs for a specific action type"""
        return [log for log in self._logs if log.action == action]

    def get_failed_logs(self) -> List[ExecutionLog]:
        """Get all failed execution logs"""
        return [log for log in self._logs if "Failed" in log.result]
    
    def clear(self) -> None:
        """Clear all execution logs"""
        self._logs.clear()
    
    def get_logs_count(self) -> int:
        """Get total number of logs"""
        return len(self._logs)

    def get_dataflow_summary(self) -> Dict[str, Any]:
        """Get summary of dataflow analysis from all logged executions"""
        total_patterns = 0
        total_high_risk_flows = 0
        total_external_flows = 0
        tools_found = []
        files_with_dataflows = []

        for log in self._logs:
            if log.dataflow_info:
                total_patterns += log.dataflow_info.get("patterns_count", 0)
                total_high_risk_flows += len(log.dataflow_info.get("high_risk_flows", []))
                total_external_flows += len(log.dataflow_info.get("external_input_flows", []))
                files_with_dataflows.append(log.target)

            if log.tool_usage:
                for tool in log.tool_usage:
                    tool_summary = f"{tool.get('tool_name', 'unknown')} ({tool.get('tool_type', 'unknown')})"
                    if tool_summary not in tools_found:
                        tools_found.append(tool_summary)

        return {
            "total_dataflow_patterns": total_patterns,
            "high_risk_flows_count": total_high_risk_flows,
            "external_input_flows_count": total_external_flows,
            "files_with_dataflows": len(files_with_dataflows),
            "unique_tools_found": tools_found,
            "tools_count": len(tools_found)
        }

    def get_logs_with_dataflow(self) -> List[ExecutionLog]:
        """Get all logs that contain dataflow information"""
        return [log for log in self._logs if log.dataflow_info is not None]

    def get_high_risk_dataflow_logs(self) -> List[ExecutionLog]:
        """Get logs with high-risk dataflow patterns"""
        high_risk_logs = []
        for log in self._logs:
            if (log.dataflow_info and 
                log.dataflow_info.get("high_risk_flows") and 
                len(log.dataflow_info["high_risk_flows"]) > 0):
                high_risk_logs.append(log)
        return high_risk_logs