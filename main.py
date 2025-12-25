#!/usr/bin/env python3
"""
Job posting monitoring main script
"""

import yaml
import os
from dotenv import load_dotenv
import logging
from recruit import JobScheduler

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config(config_path: str = 'config.yaml') -> dict:
    """Load configuration file"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config
    except FileNotFoundError:
        logger.error(f"Config file not found: {config_path}")
        logger.info("Please create config.yaml file. See config.yaml.example for reference.")
        raise
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        raise


def main():
    """Main function"""
    # Load environment variables
    load_dotenv()
    
    # Load configuration
    config = load_config()
    
    # Get email settings from environment variables if not in config.yaml
    if config.get('notifications', {}).get('email', {}).get('enabled'):
        email_config = config['notifications']['email']
        if not email_config.get('from_email'):
            email_config['from_email'] = os.getenv('EMAIL_USER', '')
        if not email_config.get('to_email'):
            email_config['to_email'] = os.getenv('EMAIL_TO', '')
        if not email_config.get('password'):
            email_config['password'] = os.getenv('EMAIL_PASSWORD', '')
    
    # Start scheduler
    scheduler = JobScheduler(config)
    scheduler.start()


if __name__ == '__main__':
    main()

