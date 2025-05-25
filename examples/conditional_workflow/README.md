# Conditional Workflow Example

This example demonstrates OmniTask's conditional task execution feature. The workflow processes a set of random numbers and takes different paths based on their characteristics.

## Workflow Structure

1. **Data Generation**
   - `generate_data`: Generates random numbers between 1 and 100
   - Configurable parameters: `min_value`, `max_value`, `count`

2. **Statistics Calculation**
   - `calculate_stats`: Calculates basic statistics (average, min, max)
   - Handles data type conversion and validation
   - Provides comprehensive statistics output

3. **Conditional Processing**
   - `process_large_numbers`: Processes numbers if average > 50
   - `process_small_numbers`: Processes numbers if average <= 50
   - Both tasks use the same threshold (50) but different conditions
   - Processes numbers based on the threshold value

4. **Conditional Saving**
   - `save_large_results`: Saves results if large number processing was successful
   - `save_small_results`: Saves results if small number processing was successful
   - Includes detailed analysis in the output files

5. **Summary Generation**
   - `generate_summary`: Creates a summary of the entire process
   - Includes all statistics and the chosen processing path

## Running the Example

1. Make sure you have OmniTask installed:
   ```bash
   pip install omniTask
   ```

2. Run the example:
   ```bash
   python main.py
   ```

## Expected Output

The workflow will:
1. Generate random numbers (10 numbers between 1 and 100)
2. Calculate their statistics (count, average, min, max)
3. Based on the average:
   - If > 50: Process large numbers and save to `large_numbers.txt`
   - If <= 50: Process small numbers and save to `small_numbers.txt`
4. Generate a summary in `summary.txt`

### Output Files

- `large_numbers.txt` or `small_numbers.txt`: Contains analysis of processed numbers
  - Average value
  - List of processed numbers
  - Count of processed numbers
  - Threshold used

- `summary.txt`: Contains overall workflow summary
  - Total number of values
  - Average, max, and min values
  - Chosen processing path
  - Complete list of numbers

## Key Features Demonstrated

- Conditional task execution based on task outputs
- Multiple execution paths
- Task dependency management
- Output chaining between tasks
- File operations with dynamic content
- Error handling and validation
- Type conversion and data processing
- Detailed logging and status reporting

## Files

- `workflow.yaml`: Workflow definition with conditions
- `tasks.py`: Task implementations
- `main.py`: Script to run the workflow
- `README.md`: This documentation

## Error Handling

The workflow includes comprehensive error handling:
- Input validation in all tasks
- Type conversion with error handling
- Conditional execution based on task success
- Detailed error reporting in logs
- File existence checking
- Task status tracking 