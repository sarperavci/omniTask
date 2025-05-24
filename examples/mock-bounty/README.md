# Bug Bounty Workflow Example

This example demonstrates a bug bounty workflow that uses OmniTask's dynamic task groups and parallel execution capabilities. The workflow performs subdomain discovery, URL status checking, and result analysis.

## Workflow Overview

The workflow consists of three main components:

1. **Subdomain Scanner**: Discovers subdomains for a target domain
2. **URL Checker**: Checks the status of discovered URLs in parallel
3. **Result Analyzer**: Analyzes and aggregates the results

## Components

### Subdomain Scanner (`subdomain_scanner.py`)
- Simulates subdomain discovery for a target domain
- Generates a list of common subdomains
- Returns structured data about discovered subdomains

### URL Checker (`url_checker.py`)
- Checks the status of individual URLs
- Simulates HTTP responses and response times
- Runs in parallel for multiple URLs
- Returns detailed status information for each URL

### Result Analyzer (`result_analyzer.py`)
- Processes results from URL checks
- Calculates statistics about live/dead URLs
- Provides aggregated analysis of the results

## Workflow Configuration

The workflow is defined in `workflow.yaml`:

```yaml
name: bug_bounty_workflow

tasks:
  subdomain_scanner:
    type: subdomain_scanner
    config:
      target: example.com

  url_checker:
    type: url_checker
    for_each: subdomain_scanner.subdomains
    config_template:
      url: $.url
      timeout: 5
    max_concurrent: 5

  result_analyzer:
    type: result_analyzer
    config:
      analysis_type: "url_status"

dependencies:
  result_analyzer:
    - url_checker
```

## Key Features Demonstrated

1. **Dynamic Task Groups**
   - URL checker tasks are created dynamically based on subdomain scanner output
   - Each discovered subdomain gets its own URL checker task

2. **Parallel Execution**
   - URL checks run concurrently with controlled parallelism
   - `max_concurrent: 5` limits parallel execution to 5 tasks

3. **Output Chaining**
   - Subdomain scanner output feeds into URL checker tasks
   - URL checker results are aggregated for analysis

4. **Task Dependencies**
   - Result analyzer depends on URL checker completion
   - Ensures proper execution order

## Running the Example

1. Navigate to the example directory:
   ```bash
   cd examples/mock-bounty
   ```

2. Run the workflow:
   ```bash
   python main.py
   ```

## Output

The workflow produces detailed output including:
- List of discovered subdomains
- Status of each URL (live/dead)
- Response times and status codes
- Aggregated statistics about the results

## Customization

You can customize the workflow by:
1. Modifying the target domain in `workflow.yaml`
2. Adjusting the `max_concurrent` value for URL checks
3. Adding more analysis types to the result analyzer
4. Extending the subdomain scanner with real discovery methods

## Best Practices Demonstrated

1. **Error Handling**
   - Graceful handling of failed URL checks
   - Proper error propagation through the workflow

2. **Logging**
   - Detailed logging at each step
   - Clear output formatting

3. **Configuration**
   - Flexible task configuration
   - Environment-based settings

4. **Performance**
   - Parallel execution for better performance
   - Controlled concurrency to prevent overload 