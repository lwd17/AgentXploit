"""
Focus Tracking System for Deep Vulnerability Analysis
Maintains analysis focus and prevents shallow exploration
"""

from typing import Dict, List, Any, Optional, Set
from datetime import datetime
from pathlib import Path
import json


class AnalysisFocus:
    """Represents a specific analysis focus or line of investigation"""

    def __init__(self, focus_description: str, target: str = None, reason: str = "", priority: int = 50):
        # LLM-driven flexible focus - no rigid types
        self.focus_description = focus_description  # Free-form description from LLM
        self.target = target  # Optional: Main file/directory being investigated
        self.reason = reason  # Why this became a focus
        self.priority = priority  # 1-100, higher is more urgent
        self.created_at = datetime.now()
        self.last_updated = datetime.now()

        # Track investigation progress
        self.related_files: Set[str] = set()
        self.key_findings: List[Dict] = []
        self.investigation_depth = 0
        self.leads_to_follow: List[str] = []
        self.failed_paths: Set[str] = set()  # Track paths that failed to explore
        self.status = "active"  # active, completed, abandoned

        # Legacy compatibility (deprecated)
        self.focus_type = "llm_driven"  # For backward compatibility only
    
    def add_related_file(self, file_path: str, relationship: str = "related"):
        """Add a file that's related to this focus"""
        self.related_files.add(file_path)
        self.last_updated = datetime.now()
    
    def add_finding(self, finding):
        """Add a key finding to this focus"""
        # Handle both SecurityFinding objects and dict formats
        if hasattr(finding, 'severity'):
            # SecurityFinding object - convert to dict
            finding_dict = {
                'finding_id': finding.finding_id,
                'finding_type': finding.finding_type,
                'severity': finding.severity,
                'file_path': finding.file_path,
                'line_number': finding.line_number,
                'description': finding.description,
                'risk_score': finding.risk_score,
                'recommendation': finding.recommendation,
                'timestamp': datetime.now().isoformat()
            }
            risk_level = finding.severity
        else:
            # Dict format
            finding_dict = finding.copy()
            finding_dict['timestamp'] = datetime.now().isoformat()
            risk_level = finding.get('risk_level', finding.get('severity', '')).lower()

        self.key_findings.append(finding_dict)
        self.last_updated = datetime.now()

        # Auto-promote priority based on findings severity
        if risk_level == 'high':
            self.priority = min(95, self.priority + 20)
        elif risk_level == 'medium':
            self.priority = min(90, self.priority + 10)
    
    def add_lead(self, lead_path: str, reason: str):
        """Add a new lead to follow up on"""
        self.leads_to_follow.append({
            'path': lead_path,
            'reason': reason,
            'added_at': datetime.now().isoformat()
        })
        self.last_updated = datetime.now()

    def mark_path_failed(self, path: str):
        """Mark a path as failed to avoid retrying it"""
        self.failed_paths.add(path)
        self.last_updated = datetime.now()
        print(f"  [FOCUS_PATH_FAILED] Marked path as failed: {path}")
    
    def get_age_minutes(self) -> float:
        """Get age of this focus in minutes"""
        return (datetime.now() - self.created_at).total_seconds() / 60
    
    def is_stale(self, threshold_minutes: int = 30) -> bool:
        """Check if this focus has been stale for too long"""
        return (datetime.now() - self.last_updated).total_seconds() / 60 > threshold_minutes
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            'focus_description': self.focus_description,
            'focus_type': self.focus_type,  # Legacy field
            'target': self.target,
            'reason': self.reason,
            'priority': self.priority,
            'created_at': self.created_at.isoformat(),
            'last_updated': self.last_updated.isoformat(),
            'related_files': list(self.related_files),
            'key_findings': self.key_findings,
            'investigation_depth': self.investigation_depth,
            'leads_to_follow': self.leads_to_follow,
            'failed_paths': list(self.failed_paths),
            'status': self.status
        }


class FocusTracker:
    """Manages analysis focuses and drives deep investigation"""

    def __init__(self, repo_path: Path = None, llm_decision_maker=None):
        self.repo_path = repo_path
        self.active_focuses: Dict[str, AnalysisFocus] = {}
        self.focus_history: List[AnalysisFocus] = []
        self.max_concurrent_focuses = 3
        self.focus_counter = 0
        self.llm_decision_maker = llm_decision_maker  # Optional LLM-driven path selection
    
    def create_focus(self, focus_description: str = None, target: str = None, reason: str = "",
                    findings: List[Dict] = None, priority: int = None,
                    focus_type: str = None) -> str:
        """
        Create a new analysis focus (LLM-driven or legacy)

        Args:
            focus_description: Free-form focus description (new LLM-driven approach)
            target: Optional target path
            reason: Why this focus was created
            findings: Initial findings
            priority: Optional explicit priority (1-100)
            focus_type: Legacy parameter for backward compatibility
        """
        self.focus_counter += 1

        # Support both new and legacy API
        if focus_description is None:
            # Legacy mode: use focus_type
            if focus_type:
                focus_description = f"{focus_type} investigation"
                focus_id = f"{focus_type}_{self.focus_counter}"
            else:
                focus_description = "general analysis"
                focus_id = f"focus_{self.focus_counter}"
        else:
            # New LLM-driven mode
            focus_id = f"llm_focus_{self.focus_counter}"

        # Calculate priority
        if priority is None:
            # Legacy: base on focus_type
            if focus_type:
                base_priorities = {
                    'vulnerability': 80,
                    'dependency': 70,
                    'data_flow': 75,
                    'config_chain': 60,
                    'injection_point': 90
                }
                priority = base_priorities.get(focus_type, 50)
            else:
                priority = 50

            # Boost based on findings
            if findings:
                high_risk_count = sum(
                    1 for f in findings
                    if (hasattr(f, 'severity') and f.severity == 'high') or
                       (isinstance(f, dict) and (f.get('risk_level') == 'high' or f.get('severity') == 'high'))
                )
                priority = min(99, priority + high_risk_count * 15)

        focus = AnalysisFocus(focus_description, target, reason, priority)

        if findings:
            for finding in findings:
                focus.add_finding(finding)

        self.active_focuses[focus_id] = focus
        self._manage_focus_capacity()

        print(f"  [FOCUS_CREATED] {focus_description[:60]} (priority: {priority}) - {reason}")
        return focus_id
    
    def get_primary_focus(self) -> Optional[AnalysisFocus]:
        """Get the highest priority active focus"""
        if not self.active_focuses:
            return None
        
        # Sort by priority (descending) then by recency
        sorted_focuses = sorted(
            self.active_focuses.values(),
            key=lambda f: (f.priority, f.last_updated),
            reverse=True
        )
        return sorted_focuses[0]
    
    def update_focus(self, focus_id: str, finding: Dict = None,
                    related_file: str = None, lead: Dict = None) -> bool:
        """Update an existing focus with new information"""
        if focus_id not in self.active_focuses:
            return False

        focus = self.active_focuses[focus_id]

        if finding:
            focus.add_finding(finding)
            # Handle both SecurityFinding objects and dict formats
            if hasattr(finding, 'description'):
                description = finding.description
            else:
                description = finding.get('description', 'New finding')
            print(f"  [FOCUS_UPDATED] Added finding to {focus.target}: {description}")

        if related_file:
            focus.add_related_file(related_file)

        if lead:
            reason = lead.get('reason', lead.get('reasoning', 'Unknown reason'))
            focus.add_lead(lead['path'], reason)
            print(f"  [LEAD_ADDED] New lead for {focus.target}: {lead['path']} - {reason}")

        focus.investigation_depth += 1
        return True

    def mark_path_failed(self, focus_id: str, path: str):
        """Mark a path as failed in the specified focus"""
        if focus_id in self.active_focuses:
            self.active_focuses[focus_id].mark_path_failed(path)
            # Also increment investigation_depth to prevent infinite retries
            self.active_focuses[focus_id].investigation_depth += 1
    
    def get_next_investigation_targets(
        self,
        limit: int = 3,
        analyzed_files: List[str] = None,
        explored_directories: List[str] = None,
        recent_findings: List[Dict] = None
    ) -> List[Dict]:
        """Get the next targets to investigate based on active focuses"""

        # Use LLM-driven path selection if available
        if self.llm_decision_maker:
            return self._llm_select_paths(
                limit=limit,
                analyzed_files=analyzed_files or [],
                explored_directories=explored_directories or [],
                recent_findings=recent_findings or []
            )

        # Fallback to rule-based selection
        return self._rule_based_select_paths(
            limit=limit,
            analyzed_files=analyzed_files or [],
            explored_directories=explored_directories or []
        )

    def _llm_select_paths(
        self,
        limit: int,
        analyzed_files: List[str],
        explored_directories: List[str],
        recent_findings: List[Dict]
    ) -> List[Dict]:
        """
        LLM-driven path selection

        Note: explored_directories contains ALREADY EXPLORED directories.
        We need to find UNEXPLORED directories from subdirectories.
        """
        if not self.active_focuses:
            return []

        # Get primary focus
        primary_focus = self.get_primary_focus()
        if not primary_focus:
            return []

        # Collect all failed paths from all focuses
        all_failed_paths = set()
        for focus in self.active_focuses.values():
            all_failed_paths.update(focus.failed_paths)

        # Find unexplored directories from explored ones
        explored_set = set(explored_directories)
        unexplored_dirs = []

        if self.repo_path:
            # Get subdirectories of explored directories
            for explored_dir in explored_directories:
                try:
                    full_path = self.repo_path / explored_dir
                    if full_path.exists() and full_path.is_dir():
                        for item in full_path.iterdir():
                            if item.is_dir() and not item.name.startswith('.') and not item.name.startswith('__'):
                                rel_path = str(item.relative_to(self.repo_path))
                                if rel_path not in explored_set and rel_path not in all_failed_paths:
                                    unexplored_dirs.append(rel_path)
                except Exception:
                    continue

        # Find unanalyzed files from explored directories
        analyzed_set = set(analyzed_files)
        unanalyzed_files = []

        if self.repo_path:
            for explored_dir in explored_directories:
                try:
                    full_path = self.repo_path / explored_dir
                    if full_path.exists() and full_path.is_dir():
                        for item in full_path.iterdir():
                            if item.is_file() and not item.name.startswith('.'):
                                rel_path = str(item.relative_to(self.repo_path))
                                if rel_path not in analyzed_set and rel_path not in all_failed_paths:
                                    unanalyzed_files.append(rel_path)
                except Exception:
                    continue

        # Prepare focus context for LLM
        focus_context = {
            'focus_description': primary_focus.focus_description,
            'priority': primary_focus.priority,
            'target': primary_focus.target,
            'investigation_depth': primary_focus.investigation_depth
        }

        # Get LLM recommendations using UNEXPLORED paths only
        try:
            targets = self.llm_decision_maker.select_investigation_paths(
                current_focus=focus_context,
                available_paths={
                    'directories': unexplored_dirs,
                    'files': unanalyzed_files
                },
                recent_findings=recent_findings,
                failed_paths=list(all_failed_paths),
                limit=limit
            )

            # Add focus_id to each target
            focus_id = list(self.active_focuses.keys())[
                list(self.active_focuses.values()).index(primary_focus)
            ]
            for target in targets:
                target['focus_id'] = focus_id
                target['focus_type'] = primary_focus.focus_type

            print(f"  [LLM_PATH_SELECT] Selected {len(targets)} targets for: {primary_focus.focus_description[:60]}")
            return targets

        except Exception as e:
            print(f"  [LLM_PATH_SELECT_ERROR] Falling back to rule-based: {e}")
            return self._rule_based_select_paths(limit, analyzed_files, explored_directories)

    def _rule_based_select_paths(
        self,
        limit: int,
        analyzed_files: List[str],
        explored_directories: List[str]
    ) -> List[Dict]:
        """Legacy rule-based path selection"""
        targets = []

        for focus in sorted(self.active_focuses.values(), key=lambda f: f.priority, reverse=True):
            # First priority: follow up on leads
            for lead in focus.leads_to_follow[:2]:  # Top 2 leads per focus
                if isinstance(lead, dict):
                    lead_path = lead['path']
                    # Skip if this path has already failed
                    if lead_path in focus.failed_paths:
                        continue
                    lead_reason = lead.get('reason', lead.get('reasoning', 'Focus-driven'))
                    targets.append({
                        'path': lead_path,
                        'action': 'analyze_file' if self._is_file_path(lead_path) else 'explore_directory',
                        'priority': focus.priority + 5,  # Boost for focus-driven analysis
                        'reason': f"Focus-driven: {lead_reason}",
                        'focus_id': list(self.active_focuses.keys())[list(self.active_focuses.values()).index(focus)],
                        'focus_type': focus.focus_type
                    })

            # Second priority: explore related areas (from ACTUAL explored paths only)
            if focus.investigation_depth < 5:  # Prevent infinite depth
                related_paths = self._get_related_investigation_paths(
                    focus,
                    analyzed_files=analyzed_files,
                    explored_directories=explored_directories
                )
                for path in related_paths[:2]:
                    # Skip if this path has already failed
                    if path in focus.failed_paths:
                        continue
                    targets.append({
                        'path': path,
                        'action': 'analyze_file' if self._is_file_path(path) else 'explore_directory',
                        'priority': focus.priority,
                        'reason': f"Focus expansion: investigating {focus.focus_description[:40]}",
                        'focus_id': list(self.active_focuses.keys())[list(self.active_focuses.values()).index(focus)],
                        'focus_type': focus.focus_type
                    })

            if len(targets) >= limit:
                break

        return targets[:limit]
    
    def should_trigger_reassessment(self, recent_findings: List) -> bool:
        """Determine if new findings warrant immediate focus reassessment"""
        if not recent_findings:
            return False

        # Trigger on significant findings
        high_risk_findings = []
        medium_risk_findings = []

        for f in recent_findings:
            # Handle both SecurityFinding objects and dict formats
            if hasattr(f, 'severity'):
                severity = f.severity
            else:
                severity = f.get('risk_level', f.get('severity', ''))

            if severity == 'high':
                high_risk_findings.append(f)
            elif severity == 'medium':
                medium_risk_findings.append(f)

        if high_risk_findings:
            return True

        # Trigger if we found multiple related medium-risk findings
        if len(medium_risk_findings) >= 2:
            return True
        
        # Trigger if findings suggest a pattern
        if len(recent_findings) >= 3:
            return True
        
        return False
    
    def _manage_focus_capacity(self):
        """Ensure we don't have too many active focuses"""
        if len(self.active_focuses) <= self.max_concurrent_focuses:
            return
        
        # Identify focuses to retire
        sorted_focuses = sorted(
            self.active_focuses.items(),
            key=lambda item: (item[1].priority, item[1].last_updated)
        )
        
        # Retire the lowest priority, oldest focuses
        to_retire = sorted_focuses[:len(self.active_focuses) - self.max_concurrent_focuses]
        
        for focus_id, focus in to_retire:
            if focus.investigation_depth >= 2:  # Only retire if we've done some work
                focus.status = "completed"
                self.focus_history.append(focus)
                del self.active_focuses[focus_id]
                print(f"  [FOCUS_RETIRED] Completed focus: {focus.target} (depth: {focus.investigation_depth})")
    
    def _get_related_investigation_paths(
        self,
        focus: AnalysisFocus,
        analyzed_files: List[str] = None,
        explored_directories: List[str] = None
    ) -> List[str]:
        """
        Extract candidate paths from ACTUAL explored structure.
        Only returns paths that have been discovered during exploration.
        """
        candidates = []
        analyzed_files = analyzed_files or []
        explored_directories = explored_directories or []

        base_dir = Path(focus.target).parent
        base_dir_str = str(base_dir)

        if focus.focus_type == 'vulnerability':
            # Find security-related paths from explored directories
            security_keywords = ['auth', 'security', 'validator', 'middleware', 'permission']
            for dir_path in explored_directories:
                if any(keyword in dir_path.lower() for keyword in security_keywords):
                    # Prefer paths in same or parent directory
                    if base_dir_str in dir_path or dir_path in base_dir_str:
                        candidates.append(dir_path)

            # Find security-related files from analyzed files
            for file_path in analyzed_files:
                file_lower = file_path.lower()
                if any(keyword in file_lower for keyword in security_keywords):
                    # Prefer files in same directory
                    if str(Path(file_path).parent) == base_dir_str:
                        candidates.append(file_path)

        elif focus.focus_type == 'dependency':
            # Look for related utility/config files in same directory
            target_stem = Path(focus.target).stem
            for file_path in analyzed_files:
                if str(Path(file_path).parent) == base_dir_str:
                    file_stem = Path(file_path).stem
                    # Look for *_utils, *_config, *_helper patterns
                    if any(suffix in file_stem for suffix in ['utils', 'config', 'helper', 'common']):
                        candidates.append(file_path)

            # Look for utils/helpers directories
            for dir_path in explored_directories:
                if any(keyword in dir_path.lower() for keyword in ['utils', 'helpers', 'common', 'lib']):
                    if base_dir_str in dir_path:
                        candidates.append(dir_path)

        elif focus.focus_type == 'data_flow':
            # Find data processing related paths
            dataflow_keywords = ['models', 'parsers', 'processors', 'handlers', 'services']
            for dir_path in explored_directories:
                if any(keyword in dir_path.lower() for keyword in dataflow_keywords):
                    candidates.append(dir_path)

            for file_path in analyzed_files:
                if any(keyword in file_path.lower() for keyword in dataflow_keywords):
                    candidates.append(file_path)

        # Remove duplicates and limit to top 5
        candidates = list(dict.fromkeys(candidates))  # Preserve order while removing dupes
        return candidates[:5]
    
    def _is_file_path(self, path: str) -> bool:
        """Determine if a path is likely a file"""
        return '.' in Path(path).name
    
    def get_focus_summary(self) -> Dict:
        """Get a summary of current analysis state"""
        return {
            'active_focuses': len(self.active_focuses),
            'total_findings': sum(len(getattr(f, 'key_findings', [])) for f in self.active_focuses.values()),
            'highest_priority': max([f.priority for f in self.active_focuses.values()], default=0),
            'focuses': [f.to_dict() for f in self.active_focuses.values()]
        }