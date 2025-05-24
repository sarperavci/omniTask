import logging

class TaskLogFormatter(logging.Formatter):
    def format(self, record):
        if hasattr(record, 'task_name'):
            record.task_info = f"[{record.task_name}({record.task_type})]"
        else:
            record.task_info = ""
            
        if hasattr(record, 'status'):
            record.status_info = f"[{record.status}]"
        else:
            record.status_info = ""
            
        if hasattr(record, 'timestamp'):
            record.time_info = f"[{record.timestamp}]"
        else:
            record.time_info = ""
            
        return super().format(record)

def setup_task_logging(level=logging.INFO):
    logging.basicConfig(level=level)
    formatter = TaskLogFormatter(
        '%(asctime)s %(levelname)s %(task_info)s %(status_info)s %(time_info)s %(message)s'
    )
    
    for handler in logging.getLogger().handlers:
        handler.setFormatter(formatter) 