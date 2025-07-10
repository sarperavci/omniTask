from omniTask.core.task import StreamingTask
from omniTask.models.task_result import TaskResult
import asyncio
import random
import logging
from datetime import datetime

class StreamingSubdomainScanner(StreamingTask):
    task_name = "streaming_subdomain_scanner"
    library_dependencies = set()

    async def execute_streaming(self) -> TaskResult:
        self.logger = logging.getLogger(f"task.{self.name}")
        self.logger.info(f"Starting streaming subdomain scan for target: {self.config.get('target')}")

        target = self.config.get("target")
        if not target:
            self.logger.error("Target domain not specified")
            return TaskResult(success=False, error="Target domain not specified")

        # Simulate progressive subdomain discovery
        subdomains = ["www", "api", "dev", "staging", "test", "admin", "blog", "mail", "ftp", "cdn"]
        discovered_subdomains = []
        
        self.logger.info("Starting streaming subdomain discovery...")
        
        for i, subdomain in enumerate(subdomains):
            # Simulate discovery time
            await asyncio.sleep(0.5)
            
            discovery_time = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            subdomain_data = {
                "url": f"https://{subdomain}.{target}",
                "status": "discovered",
                "discovery_order": i + 1,
                "discovered_at": discovery_time
            }
            
            discovered_subdomains.append(subdomain_data)
            
            # Yield intermediate result for each discovered subdomain
            await self.yield_result({
                "subdomains": [subdomain_data],
                "total_found": len(discovered_subdomains),
                "progress": f"{i + 1}/{len(subdomains)}"
            })
            
            self.logger.info(f"🔍 [{discovery_time}] Discovered and yielded: {subdomain_data['url']}")
        
        # Return final result
        final_result = {
            "target": target,
            "subdomains": discovered_subdomains,
            "total_found": len(discovered_subdomains),
            "streaming_complete": True
        }
        
        self.logger.info(f"Streaming scan complete. Total subdomains found: {len(discovered_subdomains)}")
        
        return TaskResult(
            success=True,
            output=final_result
        ) 