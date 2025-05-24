from omniTask.core.task import Task
from omniTask.models.task_result import TaskResult
import logging

class ResultAnalyzer(Task):
    task_name = "result_analyzer"
    library_dependencies = set()

    async def execute(self) -> TaskResult:
        self.logger = logging.getLogger(f"task.{self.name}")
        self.logger.info("Starting result analysis")

        url_checker_results = self.get_output("prev.results")
        self.logger.info(f"Found { (url_checker_results)} URL check results")
        
        live_urls = [r for r in url_checker_results if r["is_live"]]
        dead_urls = [r for r in url_checker_results if not r["is_live"]]

        analysis = {
            "total_urls": len(url_checker_results),
            "live_urls": len(live_urls),
            "dead_urls": len(dead_urls),
            "live_url_list": [r["url"] for r in live_urls],
            "dead_url_list": [r["url"] for r in dead_urls],
            "average_response_time": sum(r["response_time"] for r in url_checker_results) / len(url_checker_results) if url_checker_results else 0
        }

        self.logger.info(f"Analysis complete: {analysis['live_urls']} live URLs, {analysis['dead_urls']} dead URLs")
        
        return TaskResult(
            success=True,
            output=analysis
        ) 