from typing import Dict, Set, List, Optional, Any, Tuple
from ..core.workflow import Workflow
from ..core.task import Task
from .path_parser import PathParser
import re
import inspect
import ast
import textwrap
from difflib import get_close_matches

class WorkflowChecker:
    def __init__(self, workflow: Workflow):
        self.workflow = workflow
        self.task_output_keys: Dict[str, Set[str]] = {}
        self.task_dependencies: Dict[str, List[str]] = {}
        self._analyze_tasks()

    @staticmethod
    def analyze_successful_taskresult_output_keys(cls, method_name='execute'):
        method = getattr(cls, method_name)
        source = inspect.getsource(method).lstrip()
        tree = ast.parse(source)

        keys = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if (isinstance(func, ast.Name) and func.id == 'TaskResult') or \
                   (isinstance(func, ast.Attribute) and func.attr == 'TaskResult'):

                    success_value = None
                    output_value = None
                    for kw in node.keywords:
                        if kw.arg == 'success':
                            if isinstance(kw.value, ast.Constant):
                                success_value = kw.value.value
                        elif kw.arg == 'output':
                            output_value = kw.value

                    if success_value is True and isinstance(output_value, ast.Dict):
                        for key in output_value.keys:
                            if isinstance(key, ast.Constant):
                                keys.append(key.value)

        return keys

    def _analyze_tasks(self):
        for task in self.workflow.get_all_tasks():
            task_class = task.__class__
            output_keys = set(self.analyze_successful_taskresult_output_keys(task_class))
            self.task_output_keys[task.name] = output_keys
            self.task_dependencies[task.name] = task.task_dependencies

    def _get_similar_keys(self, task_name: str, invalid_key: str, threshold: float = 0.6) -> List[str]:
        if task_name not in self.task_output_keys:
            return []
        
        available_keys = list(self.task_output_keys[task_name])
        return get_close_matches(invalid_key, available_keys, n=3, cutoff=threshold)

    def _get_suggestions(self, task_name: str, path: str) -> List[str]:
        suggestions = []
        parts = path.split('.')
        
        if not parts:
            return suggestions

        if parts[0].startswith('prev'):
            steps_back, remaining_path = PathParser.parse_relative_path(parts[0])
            if steps_back is None:
                suggestions.append("Invalid 'prev' format. Use 'prev' or 'prevN' where N is a number.")
                return suggestions

            deps = self.task_dependencies[task_name]
            if steps_back > len(deps):
                suggestions.append(f"Only {len(deps)} previous task(s) available. Use 'prev' to 'prev{len(deps)}'.")
                return suggestions

            target_task = deps[-steps_back]
            if remaining_path:
                similar_keys = self._get_similar_keys(target_task, remaining_path)
                if similar_keys:
                    suggestions.append(f"Did you mean one of these keys from {target_task}? {', '.join(similar_keys)}")
            return suggestions

        target_task = parts[0]
        if target_task not in self.task_dependencies[task_name]:
            similar_tasks = get_close_matches(target_task, self.task_dependencies[task_name], n=3, cutoff=0.6)
            if similar_tasks:
                suggestions.append(f"Did you mean one of these tasks? {', '.join(similar_tasks)}")
            return suggestions

        if len(parts) == 1:
            return suggestions

        if target_task not in self.task_output_keys:
            return suggestions

        current_keys = self.task_output_keys[target_task]
        current_path = parts[1]

        if current_path not in current_keys:
            similar_keys = self._get_similar_keys(target_task, current_path)
            if similar_keys:
                suggestions.append(f"Did you mean one of these keys from {target_task}? {', '.join(similar_keys)}")

        return suggestions

    def _validate_path(self, task_name: str, path: str) -> Tuple[bool, List[str]]:
        if not path:
            return True, []

        parts = path.split('.')
        if not parts:
            return True, []

        if parts[0].startswith('prev'):
            steps_back, remaining_path = PathParser.parse_relative_path(parts[0])
            if steps_back is None:
                return False, ["Invalid 'prev' format. Use 'prev' or 'prevN' where N is a number."]

            deps = self.task_dependencies[task_name]
            if steps_back > len(deps):
                return False, [f"Only {len(deps)} previous task(s) available. Use 'prev' to 'prev{len(deps)}'."]

            target_task = deps[-steps_back]
            if remaining_path:
                valid, suggestions = self._validate_path(task_name, f"{target_task}.{remaining_path}")
                return valid, suggestions
            return True, []

        target_task = parts[0]
        if target_task not in self.task_dependencies[task_name]:
            return False, self._get_suggestions(task_name, path)

        if len(parts) == 1:
            return True, []

        if target_task not in self.task_output_keys:
            return False, []

        current_keys = self.task_output_keys[target_task]
        current_path = parts[1]

        for part in parts[1:]:
            if part not in current_keys:
                return False, self._get_suggestions(task_name, path)
            current_keys = self.task_output_keys.get(f"{target_task}.{part}", set())

        return True, []

    def _validate_condition(self, task: Task, condition: Any) -> List[str]:
        errors = []
        
        if isinstance(condition, dict):
            if 'path' not in condition:
                errors.append(f"Task {task.name}: Condition missing 'path' field")
                return errors
                
            path = condition['path']
            valid, suggestions = self._validate_path(task.name, path)
            if not valid:
                error_msg = f"Task {task.name}: Invalid path '{path}' in condition"
                if suggestions:
                    error_msg += f"\nSuggestions: {'; '.join(suggestions)}"
                errors.append(error_msg)
                
            if 'operator' not in condition:
                errors.append(f"Task {task.name}: Condition missing 'operator' field")
            elif condition['operator'] not in {'eq', 'ne', 'gt', 'lt', 'gte', 'lte', 'in', 'not_in'}:
                valid_ops = {'eq', 'ne', 'gt', 'lt', 'gte', 'lte', 'in', 'not_in'}
                similar_ops = get_close_matches(condition['operator'], valid_ops, n=3, cutoff=0.6)
                error_msg = f"Task {task.name}: Invalid operator '{condition['operator']}' in condition"
                if similar_ops:
                    error_msg += f"\nDid you mean one of these? {', '.join(similar_ops)}"
                errors.append(error_msg)
                
            if 'value' not in condition:
                errors.append(f"Task {task.name}: Condition missing 'value' field")
                
        elif isinstance(condition, str):
            matches = re.findall(r'\${([^}]+)}', condition)
            for match in matches:
                valid, suggestions = self._validate_path(task.name, match)
                if not valid:
                    error_msg = f"Task {task.name}: Invalid path '{match}' in condition string"
                    if suggestions:
                        error_msg += f"\nSuggestions: {'; '.join(suggestions)}"
                    errors.append(error_msg)
                    
        return errors

    def _check_task_config(self, task: Task) -> List[str]:
        errors = []
        config = task.config or {}

        for key, value in config.items():
            if isinstance(value, str):
                matches = re.findall(r'\${([^}]+)}', value)
                for match in matches:
                    valid, suggestions = self._validate_path(task.name, match)
                    if not valid:
                        error_msg = f"Task {task.name}: Invalid path '{match}' in config key '{key}'"
                        if suggestions:
                            error_msg += f"\nSuggestions: {'; '.join(suggestions)}"
                        errors.append(error_msg)
            elif key == 'condition':
                errors.extend(self._validate_condition(task, value))

        return errors

    def _check_task_code(self, task: Task) -> List[str]:
        errors = []
        task_class = task.__class__
        try:
            source = inspect.getsource(task_class.execute)
            source = textwrap.dedent(source)
            tree = ast.parse(source)

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Attribute) and node.func.attr == 'get_output':
                        if node.args:
                            path_arg = node.args[0]
                            if isinstance(path_arg, ast.Constant):
                                path = path_arg.value
                                valid, suggestions = self._validate_path(task.name, path)
                                if not valid:
                                    error_msg = f"Task {task.name}: Invalid path '{path}' in get_output call"
                                    if suggestions:
                                        error_msg += f"\nSuggestions: {'; '.join(suggestions)}"
                                    errors.append(error_msg)
        except (TypeError, SyntaxError, IndentationError) as e:
            errors.append(f"Task {task.name}: Failed to analyze code: {str(e)}")

        return errors

    def check_workflow(self) -> List[str]:
        errors = []
        for task in self.workflow.get_all_tasks():
            errors.extend(self._check_task_config(task))
            errors.extend(self._check_task_code(task))
        return errors

    def validate_workflow(self) -> bool:
        errors = self.check_workflow()
        if errors:
            for error in errors:
                print(f"Validation Error: {error}")
            return False
        return True