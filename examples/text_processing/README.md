# Text Processing Example

This example demonstrates a simple text processing workflow using OmniTask. The workflow:
1. Creates a text file
2. Reads its contents
3. Processes the text in multiple ways
4. Saves the processed results

## Tasks
- `file_ops`: Handles file operations (read/write/append)
- `count`: Counts text statistics (words/characters/lines)
- `uppercase`: Converts text to uppercase

## Running the Example
You can run the example in two ways:

### Using Python Code
```bash
python main.py
```

### Using Workflow Template
```bash
python template_main.py
```

The template version uses a YAML file (`workflow.yaml`) to define the workflow structure, making it easier to maintain and modify the workflow configuration.

## Expected Output
- `demo.txt`: Original text file
- `uppercase.txt`: Text converted to uppercase
- Console output showing task results and statistics 