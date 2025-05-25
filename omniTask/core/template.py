from typing import Dict, Any, Optional
import yaml
import json
import os
from pathlib import Path
from .workflow import Workflow
from .registry import TaskRegistry
from ..models.task_group import TaskGroupConfig

class WorkflowTemplate:
    def __init__(self, template_path: str):
        self.template_path = template_path
        self.template_data = self._load_template()

    def _load_template(self) -> Dict[str, Any]:
        if not os.path.exists(self.template_path):
            raise FileNotFoundError(f"Template file not found: {self.template_path}")

        with open(self.template_path, 'r') as f:
            if self.template_path.endswith('.yaml') or self.template_path.endswith('.yml'):
                return yaml.safe_load(f)
            elif self.template_path.endswith('.json'):
                return json.load(f)
            else:
                raise ValueError("Template file must be YAML or JSON")

    def _validate_condition(self, condition: Any) -> None:
        if isinstance(condition, str):
            return
        elif isinstance(condition, dict):
            required_fields = {'operator', 'value', 'path'}
            if not all(field in condition for field in required_fields):
                raise ValueError(f"Condition dict must contain: {required_fields}")
            if condition['operator'] not in {'eq', 'ne', 'gt', 'lt', 'gte', 'lte', 'in', 'not_in'}:
                raise ValueError(f"Invalid operator: {condition['operator']}")
        else:
            raise ValueError("Condition must be a string or dict")

    def create_workflow(self, registry: Optional[TaskRegistry] = None) -> Workflow:
        if not isinstance(self.template_data, dict):
            raise ValueError("Invalid template format: root must be a dictionary")

        workflow_name = self.template_data.get('name')
        if not workflow_name:
            raise ValueError("Template must specify a workflow name")

        workflow = Workflow(workflow_name, registry or TaskRegistry())
        tasks = self.template_data.get('tasks', {})
        global_dependencies = self.template_data.get('dependencies', {})

        for task_name, task_config in tasks.items():
            if not isinstance(task_config, dict):
                raise ValueError(f"Invalid task configuration for {task_name}")

            if 'for_each' in task_config:
                continue

            task_type = task_config.get('type')
            if not task_type:
                raise ValueError(f"Task {task_name} must specify a type")

            config = task_config.get('config', {})
            
            if 'condition' in task_config:
                self._validate_condition(task_config['condition'])
                config['condition'] = task_config['condition']

            task = workflow.create_task(task_type, task_name, config)

            task_deps = set()
            
            if 'dependencies' in task_config:
                task_deps.update(task_config['dependencies'])
            
            if task_name in global_dependencies:
                task_deps.update(global_dependencies[task_name])
            
            for dep in task_deps:
                if dep in tasks and 'for_each' in tasks[dep]:
                    if dep not in workflow.task_groups:
                        group_config = tasks[dep]
                        group = TaskGroupConfig(
                            type=group_config.get('type'),
                            for_each=group_config.get('for_each'),
                            config_template=group_config.get('config_template', {}),
                            max_concurrent=group_config.get('max_concurrent', 10),
                            error_handling=group_config.get('error_handling')
                        )
                        workflow.add_task_group(dep, group)
                task.add_dependency(dep)

        for group_name, group_config in tasks.items():
            if not isinstance(group_config, dict):
                continue

            if 'for_each' not in group_config:
                continue

            if group_name not in workflow.task_groups:
                if not isinstance(group_config.get('for_each'), str):
                    raise ValueError(f"Task group {group_name} must specify a valid for_each path")

                group = TaskGroupConfig(
                    type=group_config.get('type'),
                    for_each=group_config.get('for_each'),
                    config_template=group_config.get('config_template', {}),
                    max_concurrent=group_config.get('max_concurrent', 10),
                    error_handling=group_config.get('error_handling')
                )
                workflow.add_task_group(group_name, group)

        return workflow

    @classmethod
    def from_dict(cls, template_data: Dict[str, Any]) -> 'WorkflowTemplate':
        temp_file = Path('temp_template.yaml')
        try:
            with open(temp_file, 'w') as f:
                yaml.dump(template_data, f)
            return cls(str(temp_file))
        finally:
            if temp_file.exists():
                temp_file.unlink() 