"""
Centralized logging configuration for the Flask API.
"""
import logging
import logging.handlers
import os
from datetime import datetime


def setup_logging():
    """Configure logging for the Flask application."""
    
    # Create logs directory if it doesn't exist
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Create logger
    logger = logging.getLogger('flask_api')
    logger.setLevel(logging.DEBUG)
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(funcName)s() - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler for all logs
    log_file = os.path.join(log_dir, 'app.log')
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10485760,  # 10MB
        backupCount=10
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    logger.addHandler(file_handler)
    
    # File handler for rate limit logs
    rate_limit_file = os.path.join(log_dir, 'ratelimit.log')
    rate_limit_handler = logging.handlers.RotatingFileHandler(
        rate_limit_file,
        maxBytes=5242880,  # 5MB
        backupCount=5
    )
    rate_limit_handler.setLevel(logging.WARNING)
    rate_limit_handler.setFormatter(detailed_formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    logger.addHandler(console_handler)
    
    # Rate limit logger
    rate_limit_logger = logging.getLogger('flask_api.ratelimit')
    rate_limit_logger.addHandler(rate_limit_handler)
    rate_limit_logger.setLevel(logging.WARNING)
    
    return logger, rate_limit_logger


# Initialize loggers
api_logger, rate_limit_logger = setup_logging()
