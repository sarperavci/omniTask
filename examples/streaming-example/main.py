import asyncio
import sys
import os
import logging
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from omniTask.core.registry import TaskRegistry
from omniTask.core.template import WorkflowTemplate
from omniTask.utils.logging import setup_task_logging, TaskLogFormatter

def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    console_handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s: %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

async def main():
    setup_logging()
    logger = logging.getLogger("streaming_main")
    
    start_time = datetime.now()
    logger.info(f"🚀 Starting streaming workflow demonstration at {start_time.strftime('%H:%M:%S.%f')[:-3]}")
    
    try:
        # Create task registry and load tasks
        registry = TaskRegistry()
        registry.load_tasks_from_directory(os.path.join(os.path.dirname(__file__), "tasks"))
        logger.info("📦 Loaded streaming tasks from directory")

        # Create workflow from template
        template = WorkflowTemplate(os.path.join(os.path.dirname(__file__), "streaming_workflow.yaml"))
        workflow = template.create_workflow(registry)
        logger.info("📋 Created streaming workflow from template")
        
        if workflow.streaming_enabled:
            logger.info("✅ Streaming mode is ENABLED for this workflow")
        else:
            logger.info("❌ Streaming mode is DISABLED for this workflow") 

        # Run the workflow
        execution_start = datetime.now()
        logger.info(f"🎬 Starting workflow execution at {execution_start.strftime('%H:%M:%S.%f')[:-3]}")
        results = await workflow.run()
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        execution_duration = (end_time - execution_start).total_seconds()

        logger.info(f"\n🎉 Streaming workflow completed at {end_time.strftime('%H:%M:%S.%f')[:-3]}")
        logger.info(f"⏱️  Total time: {duration:.2f}s, Execution time: {execution_duration:.2f}s")
        logger.info("\n📊 Workflow Results:")
        logger.info("=" * 50)
        
        # Display subdomain scanner results
        scanner_result = results.get("streaming_subdomain_scanner")
        if scanner_result and scanner_result.success:
            logger.info(f"\n🔍 Streaming Subdomain Scanner:")
            logger.info(f"  Target: {scanner_result.output.get('target')}")
            logger.info(f"  Total subdomains found: {scanner_result.output.get('total_found')}")
            logger.info(f"  Streaming complete: {scanner_result.output.get('streaming_complete')}")

        # Display URL checker results
        url_checker_result = results.get("streaming_url_checker")
        if url_checker_result and url_checker_result.success:
            url_results = url_checker_result.output.get("results", [])
            live_count = sum(1 for r in url_results if r.get("is_live", False))
            dead_count = sum(1 for r in url_results if not r.get("is_live", False))
            
            logger.info(f"\n🌐 Streaming URL Checker:")
            logger.info(f"  Total URLs processed: {len(url_results)}")
            logger.info(f"  Live URLs: {live_count} ✅")
            logger.info(f"  Dead URLs: {dead_count} ❌")
            
            logger.info(f"\n📋 Detailed Results:")
            for result in url_results:
                status = "✅ LIVE" if result.get("is_live", False) else "❌ DEAD"
                logger.info(f"  {status} {result.get('url', 'Unknown URL')}")
                logger.info(f"    Status Code: {result.get('status_code', 'N/A')}")
                logger.info(f"    Response Time: {result.get('response_time', 0):.2f}s")

        # Display analysis results
        analysis_result = results.get("result_analyzer")
        if analysis_result and analysis_result.success:
            analysis = analysis_result.output
            logger.info(f"\n📈 Result Analysis:")
            logger.info(f"  Analysis Type: {analysis.get('analysis_type')}")
            logger.info(f"  Total URLs: {analysis.get('total_urls')}")
            logger.info(f"  Live URLs: {analysis.get('live_urls')}")
            logger.info(f"  Dead URLs: {analysis.get('dead_urls')}")
            logger.info(f"  Average Response Time: {analysis.get('average_response_time', 0):.2f}s")
            logger.info(f"  Streaming Analysis: {'✅' if analysis.get('streaming_enabled') else '❌'}")

        logger.info(f"\n🎯 Key Features Demonstrated:")
        logger.info(f"  ✅ Streaming task yielding intermediate results")
        logger.info(f"  ✅ Dynamic task group processing streaming data")
        logger.info(f"  ✅ Parallel execution with controlled concurrency")
        logger.info(f"  ✅ Real-time processing as data becomes available")

    except Exception as e:
        logger.error(f"❌ Streaming workflow failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main()) 