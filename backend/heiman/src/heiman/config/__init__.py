import logging
import sys
from pathlib import Path
from datetime import datetime

from .settings import get_settings, reset_settings, reload_settings


class DetailedFormatter(logging.Formatter):
    """详细日志格式，包含时间、模块、函数、行号等信息"""

    def format(self, record):
        record.timestamp = datetime.now().isoformat()
        if not hasattr(record, 'module_path'):
            record.module_path = f"{record.module}.{record.funcName}"
        return super().format(record)


def init_logging() -> None:
    """初始化日志系统，配置详细的日志格式和输出"""
    settings = get_settings()
    log_dir = settings.logging.log_dir
    log_dir.mkdir(parents=True, exist_ok=True)

    log_level = getattr(logging, settings.logging.level.upper(), logging.INFO)

    # 详细格式：时间 | 级别 | 模块.函数 | 行号 | 消息
    detailed_format = "%(asctime)s | %(levelname)-8s | %(module_path)s:%(lineno)d | %(message)s"

    # 创建根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 清除现有 handlers
    root_logger.handlers.clear()

    # 控制台 handler（简洁格式）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    console_handler.setFormatter(logging.Formatter(console_format, datefmt="%H:%M:%S"))
    root_logger.addHandler(console_handler)

    # 文件 handler（详细格式）
    log_file = log_dir / "heiman-agent.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(log_level)
    file_handler.setFormatter(DetailedFormatter(detailed_format, datefmt="%Y-%m-%d %H:%M:%S"))
    root_logger.addHandler(file_handler)

    # 错误日志单独文件
    error_log_file = log_dir / "heiman-agent-error.log"
    error_handler = logging.FileHandler(error_log_file, encoding="utf-8")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(DetailedFormatter(detailed_format, datefmt="%Y-%m-%d %H:%M:%S"))
    root_logger.addHandler(error_handler)

    # 配置关键模块的日志级别
    logging.getLogger("heiman.collector").setLevel(log_level)
    logging.getLogger("heiman.rule").setLevel(log_level)
    logging.getLogger("heiman.classifier").setLevel(log_level)
    logging.getLogger("heiman.manager").setLevel(log_level)
    logging.getLogger("heiman.database").setLevel(log_level)
    logging.getLogger("heiman.router").setLevel(log_level)

    # 降低第三方库日志级别
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    logging.info("Logging initialized: level=%s, dir=%s, file=%s", settings.logging.level, log_dir, log_file)


def get_logger(name: str) -> logging.Logger:
    """获取指定模块的日志器"""
    return logging.getLogger(name)