from typing import Dict, Any, Optional
import yaml
import json
import os
from pathlib import Path
from .workflow import Workflow
from .registry import TaskRegistry

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

    def create_workflow(self, registry: Optional[TaskRegistry] = None) -> Workflow:
        if not isinstance(self.template_data, dict):
            raise ValueError("Invalid template format: root must be a dictionary")

        workflow_name = self.template_data.get('name')
        if not workflow_name:
            raise ValueError("Template must specify a workflow name")

        workflow = Workflow(workflow_name, registry or TaskRegistry())
        tasks = self.template_data.get('tasks', {})
        dependencies = self.template_data.get('dependencies', {})

        for task_name, task_config in tasks.items():
            if not isinstance(task_config, dict):
                raise ValueError(f"Invalid task configuration for {task_name}")

            task_type = task_config.get('type')
            if not task_type:
                raise ValueError(f"Task {task_name} must specify a type")

            config = task_config.get('config', {})
            task = workflow.create_task(task_type, task_name, config)

            if task_name in dependencies:
                for dep in dependencies[task_name]:
                    task.add_dependency(dep)

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