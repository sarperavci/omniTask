from omniTask.core.task import Task
from omniTask.models.task_result import TaskResult
import logging
import time

class ResultAnalyzer(Task):
    task_name = "result_analyzer"
    library_dependencies = set()

    async def execute(self) -> TaskResult:
        self.logger = logging.getLogger(f"task.{self.name}")
        self.logger.info("Starting streaming result analysis")

        try:
            url_checker_results = self.get_output("prev.results")
            self.logger.info(f"Found {len(url_checker_results)} URL check results from streaming")
        except Exception as e:
            self.logger.error(f"Failed to get URL checker results: {e}")
            return TaskResult(success=False, error=f"Failed to get results: {e}")
        
        live_urls = [r for r in url_checker_results if r.get("is_live", False)]
        dead_urls = [r for r in url_checker_results if not r.get("is_live", False)]

        analysis = {
            "analysis_type": self.config.get("analysis_type", "streaming_analysis"),
            "total_urls": len(url_checker_results),
            "live_urls": len(live_urls),
            "dead_urls": len(dead_urls),
            "live_url_list": [r["url"] for r in live_urls],
            "dead_url_list": [r["url"] for r in dead_urls],
            "average_response_time": sum(r.get("response_time", 0) for r in url_checker_results) / len(url_checker_results) if url_checker_results else 0,
            "analyzed_at": time.time(),
            "streaming_enabled": True
        }

        self.logger.info(f"Streaming analysis complete: {analysis['live_urls']} live URLs, {analysis['dead_urls']} dead URLs")
        
        return TaskResult(
            success=True,
            output=analysis
        ) 