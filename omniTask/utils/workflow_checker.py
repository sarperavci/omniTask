from typing import Dict, Set, List, Optional, Any, Tuple
from ..core.workflow import Workflow
from ..core.task import Task, StreamingTask
from ..models.task_group import TaskGroupConfig, StreamingTaskGroup
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
        self.task_group_configs: Dict[str, Dict[str, Any]] = {}
        self.streaming_tasks: Set[str] = set()
        self.streaming_task_groups: Set[str] = set()
        self._analyze_tasks()
        self._analyze_task_groups()
        self._analyze_streaming_components()

    @staticmethod
    def analyze_successful_taskresult_output_keys(cls, method_name='execute'):
        method = getattr(cls, method_name)
        source = inspect.getsource(method).lstrip()
        tree = ast.parse(source)

        keys = []
        dict_assignments = {}
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                if (len(node.targets) == 1 and 
                    isinstance(node.targets[0], ast.Name) and 
                    isinstance(node.value, ast.Dict)):
                    var_name = node.targets[0].id
                    dict_keys = []
                    for key in node.value.keys:
                        if isinstance(key, ast.Constant):
                            dict_keys.append(key.value)
                    dict_assignments[var_name] = dict_keys
                
                elif (len(node.targets) == 1 and 
                      isinstance(node.targets[0], ast.Subscript) and
                      isinstance(node.targets[0].value, ast.Name) and
                      isinstance(node.targets[0].slice, ast.Constant)):
                    var_name = node.targets[0].value.id
                    key = node.targets[0].slice.value
                    if var_name not in dict_assignments:
                        dict_assignments[var_name] = []
                    if key not in dict_assignments[var_name]:
                        dict_assignments[var_name].append(key)

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

                    if success_value is True:
                        # Handle direct dictionary literals
                        if isinstance(output_value, ast.Dict):
                            for key in output_value.keys:
                                if isinstance(key, ast.Constant):
                                    keys.append(key.value)
                        # Handle variable references
                        elif isinstance(output_value, ast.Name):
                            var_name = output_value.id
                            if var_name in dict_assignments:
                                keys.extend(dict_assignments[var_name])

        return keys

    def _analyze_tasks(self):
        for task in self.workflow.get_all_tasks():
            task_class = task.__class__
            
            if isinstance(task, StreamingTask):
                self.streaming_tasks.add(task.name)
                output_keys = set()
                if hasattr(task_class, 'execute_streaming'):
                    output_keys.update(self.analyze_successful_taskresult_output_keys(task_class, 'execute_streaming'))
                if hasattr(task_class, 'execute'):
                    output_keys.update(self.analyze_successful_taskresult_output_keys(task_class, 'execute'))
                self.task_output_keys[task.name] = output_keys
            else:
                output_keys = set(self.analyze_successful_taskresult_output_keys(task_class))
                self.task_output_keys[task.name] = output_keys
                
            self.task_dependencies[task.name] = task.task_dependencies

    def _analyze_task_groups(self):
        for group_name, group in self.workflow.task_groups.items():
            self.task_group_configs[group_name] = {
                'type': group.config.type,
                'for_each': group.config.for_each,
                'config_template': group.config.config_template,
                'max_concurrent': group.config.max_concurrent,
                'streaming_enabled': group.config.streaming_enabled
            }
            self.task_output_keys[group_name] = {'results'}
            
            if isinstance(group, StreamingTaskGroup):
                self.streaming_task_groups.add(group_name)

    def _analyze_streaming_components(self):
        pass

    def _check_streaming_task_implementation(self, task: Task) -> List[str]:
        errors = []
        
        if not isinstance(task, StreamingTask):
            return errors
            
        task_class = task.__class__
        
        if not hasattr(task_class, 'execute_streaming'):
            errors.append(f"Streaming task {task.name}: Missing execute_streaming() method implementation")
        else:
            try:
                source = inspect.getsource(task_class.execute_streaming)
                if 'NotImplementedError' in source and 'raise NotImplementedError' in source:
                    errors.append(f"Streaming task {task.name}: execute_streaming() method raises NotImplementedError - must be implemented")
            except (TypeError, OSError):
                errors.append(f"Streaming task {task.name}: Could not analyze execute_streaming() method")
        
        errors.extend(self._check_streaming_task_yield_usage(task))
        
        return errors

    def _check_streaming_task_yield_usage(self, task: Task) -> List[str]:
        errors = []
        
        if not isinstance(task, StreamingTask):
            return errors
            
        task_class = task.__class__
        
        try:
            if hasattr(task_class, 'execute_streaming'):
                source = inspect.getsource(task_class.execute_streaming)
                source = textwrap.dedent(source)
                tree = ast.parse(source)
                
                has_yield_result = False
                has_await_yield_result = False
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        if (isinstance(node.func, ast.Attribute) and 
                            isinstance(node.func.value, ast.Name) and 
                            node.func.value.id == 'self' and 
                            node.func.attr == 'yield_result'):
                            has_yield_result = True
                            break
                    elif isinstance(node, ast.Await):
                        if (isinstance(node.value, ast.Call) and
                            isinstance(node.value.func, ast.Attribute) and 
                            isinstance(node.value.func.value, ast.Name) and 
                            node.value.func.value.id == 'self' and 
                            node.value.func.attr == 'yield_result'):
                            has_yield_result = True
                            has_await_yield_result = True
                            break
                
                if not has_yield_result:
                    errors.append(f"Streaming task {task.name}: execute_streaming() method should call yield_result() to emit intermediate results")
                elif has_yield_result and not has_await_yield_result:
                    errors.append(f"Streaming task {task.name}: yield_result() calls should use 'await' keyword since it's an async method")
                    
        except (TypeError, SyntaxError, IndentationError) as e:
            errors.append(f"Streaming task {task.name}: Failed to analyze yield_result usage: {str(e)}")
        
        return errors

    def _check_streaming_task_group_config(self, group_name: str, config: Dict[str, Any]) -> List[str]:
        errors = []
        
        if not config.get('streaming_enabled', False):
            return errors
            
        for_each_path = config.get('for_each', '')
        if for_each_path:
            task_name = for_each_path.split('.')[0]
            
            if task_name not in self.streaming_tasks:
                errors.append(f"Streaming task group {group_name}: for_each path '{for_each_path}' references non-streaming task '{task_name}'. Streaming task groups should reference streaming tasks.")
        
        max_concurrent = config.get('max_concurrent', 10)
        if not isinstance(max_concurrent, int) or max_concurrent < 1:
            errors.append(f"Streaming task group {group_name}: max_concurrent must be a positive integer, got {max_concurrent}")
        elif max_concurrent > 50:
            errors.append(f"Streaming task group {group_name}: max_concurrent value {max_concurrent} might be too high and could cause resource exhaustion")
        
        return errors

    def _check_streaming_workflow_consistency(self) -> List[str]:
        errors = []
        
        for task_name in self.streaming_tasks:
            has_streaming_dependents = False
            
            for group_name in self.streaming_task_groups:
                group_config = self.task_group_configs.get(group_name, {})
                for_each_path = group_config.get('for_each', '')
                if for_each_path.startswith(task_name):
                    has_streaming_dependents = True
                    break
            
            if not has_streaming_dependents:
                errors.append(f"Streaming task {task_name}: No streaming task groups depend on this task. Consider using a regular Task instead of StreamingTask if streaming is not needed.")
        
        for group_name in self.streaming_task_groups:
            group_config = self.task_group_configs.get(group_name, {})
            for_each_path = group_config.get('for_each', '')
            
            if for_each_path:
                referenced_task = for_each_path.split('.')[0]
                if referenced_task not in self.streaming_tasks:
                    errors.append(f"Streaming task group {group_name}: References non-streaming task '{referenced_task}' in for_each path. This may not work as expected.")
        
        errors.extend(self._check_consecutive_streaming_tasks())
        
        return errors

    def _check_consecutive_streaming_tasks(self) -> List[str]:
        errors = []
        
        # Build a map of task dependencies to check for consecutive streaming tasks
        for task_name in self.streaming_tasks:
            task_dependencies = self.task_dependencies.get(task_name, [])
            
            # Check if any of the direct dependencies are also streaming tasks
            for dep_name in task_dependencies:
                if dep_name in self.streaming_tasks:
                    errors.append(f"Streaming task {task_name}: Cannot depend directly on another streaming task '{dep_name}'. A streaming task must be collected by a single task before continuing the workflow.")
        
        return errors

    def _validate_streaming_task_output_keys(self, task: Task) -> List[str]:
        errors = []
        
        if not isinstance(task, StreamingTask):
            return errors
            
        task_name = task.name
        output_keys = self.task_output_keys.get(task_name, set())
        
        if not output_keys:
            errors.append(f"Streaming task {task_name}: No output keys detected. Streaming tasks should return structured output.")
        
        streaming_indicators = {'streaming_complete', 'total_found', 'progress', 'items', 'results'}
        has_streaming_indicator = any(key in output_keys for key in streaming_indicators)
        
        if not has_streaming_indicator:
            errors.append(f"Streaming task {task_name}: Consider including streaming indicators like 'streaming_complete', 'total_found', or 'progress' in output for better streaming workflow support.")
        
        return errors

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

            deps = self.task_dependencies.get(task_name, [])
            if steps_back > len(deps):
                return False, [f"Only {len(deps)} previous task(s) available. Use 'prev' to 'prev{len(deps)}'."]

            target_task = deps[-steps_back]
            if remaining_path:
                valid, suggestions = self._validate_path(task_name, f"{target_task}.{remaining_path}")
                return valid, suggestions
            return True, []

        target_task = parts[0]
        if task_name in self.task_dependencies and target_task not in self.task_dependencies[task_name]:
            return False, self._get_suggestions(task_name, path)

        if len(parts) == 1:
            return True, []

        if target_task not in self.task_output_keys:
            return False, []

        current_keys = self.task_output_keys[target_task]
        current_path = parts[1]

        if target_task in self.task_group_configs and current_path != 'results':
            return False, [f"Task group {target_task} only has 'results' key available"]

        for part in parts[1:]:
            if part not in current_keys:
                return False, self._get_suggestions(task_name, path)
            current_keys = self.task_output_keys.get(f"{target_task}.{part}", set())

        return True, []

    def _validate_task_group_path(self, group_name: str, path: str) -> Tuple[bool, List[str]]:
        if not path:
            return True, []

        parts = path.split('.')
        if not parts:
            return True, []

        target_task = parts[0]
        if target_task not in self.task_output_keys:
            similar_tasks = get_close_matches(target_task, list(self.task_output_keys.keys()), n=3, cutoff=0.6)
            if similar_tasks:
                return False, [f"Did you mean one of these tasks? {', '.join(similar_tasks)}"]
            return False, [f"Task '{target_task}' not found"]

        if len(parts) == 1:
            return True, []

        current_keys = self.task_output_keys[target_task]
        for part in parts[1:]:
            if part not in current_keys:
                if target_task in self.task_group_configs and part != 'results':
                    return False, [f"Task group {target_task} only has 'results' key available"]
                similar_keys = self._get_similar_keys(target_task, part)
                if similar_keys:
                    return False, [f"Did you mean one of these keys from {target_task}? {', '.join(similar_keys)}"]
                return False, [f"Key '{part}' not found in task '{target_task}'"]
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

    def _validate_task_group_config(self, group_name: str, config: Dict[str, Any]) -> List[str]:
        errors = []
        
        if 'for_each' not in config:
            errors.append(f"Task group {group_name}: Missing 'for_each' field")
        else:
            valid, suggestions = self._validate_task_group_path(group_name, config['for_each'])
            if not valid:
                error_msg = f"Task group {group_name}: Invalid 'for_each' path '{config['for_each']}'"
                if suggestions:
                    error_msg += f"\nSuggestions: {'; '.join(suggestions)}"
                errors.append(error_msg)

        if 'config_template' not in config:
            errors.append(f"Task group {group_name}: Missing 'config_template' field")
        else:
            template = config['config_template']
            if not isinstance(template, dict):
                errors.append(f"Task group {group_name}: 'config_template' must be a dictionary")
            else:
                for key, value in template.items():
                    if isinstance(value, str):
                        matches = re.findall(r'\${([^}]+)}', value)
                        for match in matches:
                            # Skip validation for the special 'item' placeholder
                            if match == 'item':
                                continue
                            valid, suggestions = self._validate_task_group_path(group_name, match)
                            if not valid:
                                error_msg = f"Task group {group_name}: Invalid path '{match}' in config_template key '{key}'"
                                if suggestions:
                                    error_msg += f"\nSuggestions: {'; '.join(suggestions)}"
                                errors.append(error_msg)

        if 'max_concurrent' in config:
            max_concurrent = config['max_concurrent']
            if not isinstance(max_concurrent, int) or max_concurrent < 1:
                errors.append(f"Task group {group_name}: 'max_concurrent' must be a positive integer")

        if config.get('streaming_enabled', False):
            errors.extend(self._check_streaming_task_group_config(group_name, config))

        return errors

    def check_workflow(self) -> List[str]:
        errors = []
        
        for task in self.workflow.get_all_tasks():
            errors.extend(self._check_task_config(task))
            errors.extend(self._check_task_code(task))
            
            if isinstance(task, StreamingTask):
                errors.extend(self._check_streaming_task_implementation(task))
                errors.extend(self._validate_streaming_task_output_keys(task))
        
        for group_name, config in self.task_group_configs.items():
            errors.extend(self._validate_task_group_config(group_name, config))
        
        if self.streaming_tasks or self.streaming_task_groups:
            errors.extend(self._check_streaming_workflow_consistency())
            
        return errors

    def validate_workflow(self) -> bool:
        errors = self.check_workflow()
        if errors:
            for error in errors:
                print(f"Validation Error: {error}")
            return False
        return True

    def check_streaming_workflow(self) -> List[str]:
        errors = []
        
        for task_name in self.streaming_tasks:
            task = self.workflow.get_task(task_name)
            errors.extend(self._check_streaming_task_implementation(task))
            errors.extend(self._validate_streaming_task_output_keys(task))
        
        for group_name in self.streaming_task_groups:
            config = self.task_group_configs.get(group_name, {})
            errors.extend(self._check_streaming_task_group_config(group_name, config))
        
        errors.extend(self._check_streaming_workflow_consistency())
        
        return errors

    def validate_streaming_workflow(self) -> bool:
        errors = self.check_streaming_workflow()
        if errors:
            for error in errors:
                print(f"Streaming Validation Error: {error}")
            return False
        return True