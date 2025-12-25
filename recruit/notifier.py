"""
Notification module
Sends notifications via terminal, email, SMS, etc.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict
import logging
import os
import json
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Notifier:
    """Notification class"""
    
    def __init__(self, config: Dict):
        """
        Args:
            config: Notification configuration dictionary
        """
        self.config = config
        self.terminal_enabled = config.get('terminal', True)
        self.email_config = config.get('email', {})
        self.email_enabled = config.get('email', {}).get('enabled', False)
        self.file_config = config.get('file', {})
        self.file_enabled = config.get('file', {}).get('enabled', False)
    
    def notify_terminal(self, jobs: List[Dict]):
        """Print job postings to terminal"""
        if not self.terminal_enabled or not jobs:
            return
        
        print("\n" + "="*80)
        print(f"🚀 New job postings found! ({len(jobs)} items)")
        print("="*80)
        
        for i, job in enumerate(jobs, 1):
            print(f"\n[{i}] {job.get('title', 'N/A')}")
            print(f"    Company: {job.get('company', 'N/A')}")
            print(f"    Link: {job.get('link', 'N/A')}")
            print(f"    Source: {job.get('source', 'N/A')}")
            print(f"    Similarity: {job.get('similarity', 0):.2%}")
            print(f"    Matched Keyword: {job.get('matched_keyword', 'N/A')}")
            
            if job.get('detail'):
                detail = job.get('detail', '')[:100]
                print(f"    Detail: {detail}...")
        
        print("\n" + "="*80 + "\n")
    
    def notify_email(self, jobs: List[Dict]):
        """Send job postings via email"""
        if not self.email_enabled or not jobs:
            return
        
        try:
            smtp_server = self.email_config.get('smtp_server', 'smtp.gmail.com')
            smtp_port = self.email_config.get('smtp_port', 587)
            from_email = self.email_config.get('from_email') or os.getenv('EMAIL_USER')
            to_email = self.email_config.get('to_email') or os.getenv('EMAIL_TO')
            password = self.email_config.get('password') or os.getenv('EMAIL_PASSWORD')
            
            if not all([from_email, to_email, password]):
                logger.warning("Email configuration incomplete. Skipping email notification.")
                return
            
            # Create email message
            msg = MIMEMultipart()
            msg['From'] = from_email
            msg['To'] = to_email
            msg['Subject'] = f"New job postings found! ({len(jobs)} items)"
            
            # Create email body
            body = f"""
New job postings have been found! ({len(jobs)} items)

"""
            for i, job in enumerate(jobs, 1):
                body += f"""
[{i}] {job.get('title', 'N/A')}
Company: {job.get('company', 'N/A')}
Link: {job.get('link', 'N/A')}
Source: {job.get('source', 'N/A')}
Similarity: {job.get('similarity', 0):.2%}
Matched Keyword: {job.get('matched_keyword', 'N/A')}

"""
            
            body += f"""
---
Sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            # Send email
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(from_email, password)
                server.send_message(msg)
            
            logger.info(f"Email notification sent to {to_email}")
        
        except Exception as e:
            logger.error(f"Error sending email: {e}")
    
    def notify_file(self, jobs: List[Dict]):
        """Save job postings to file"""
        if not self.file_enabled or not jobs:
            return
        
        try:
            output_dir = self.file_config.get('output_dir', 'output')
            file_format = self.file_config.get('format', 'json')  # 'json' or 'txt'
            
            # Create output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            if file_format.lower() == 'json':
                filename = os.path.join(output_dir, f'job_postings_{timestamp}.json')
                self._save_json(jobs, filename)
            else:
                filename = os.path.join(output_dir, f'job_postings_{timestamp}.txt')
                self._save_text(jobs, filename)
            
            logger.info(f"Job postings saved to {filename}")
        
        except Exception as e:
            logger.error(f"Error saving to file: {e}")
    
    def _save_json(self, jobs: List[Dict], filename: str):
        """Save jobs to JSON file"""
        output_data = {
            'timestamp': datetime.now().isoformat(),
            'count': len(jobs),
            'jobs': jobs
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    def _save_text(self, jobs: List[Dict], filename: str):
        """Save jobs to text file"""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write(f"New job postings found! ({len(jobs)} items)\n")
            f.write(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("="*80 + "\n\n")
            
            for i, job in enumerate(jobs, 1):
                f.write(f"[{i}] {job.get('title', 'N/A')}\n")
                f.write(f"    Company: {job.get('company', 'N/A')}\n")
                f.write(f"    Link: {job.get('link', 'N/A')}\n")
                f.write(f"    Source: {job.get('source', 'N/A')}\n")
                f.write(f"    Similarity: {job.get('similarity', 0):.2%}\n")
                f.write(f"    Matched Keyword: {job.get('matched_keyword', 'N/A')}\n")
                
                if job.get('detail'):
                    detail = job.get('detail', '')
                    f.write(f"    Detail: {detail}\n")
                
                f.write("\n")
            
            f.write("="*80 + "\n")
    
    def notify(self, jobs: List[Dict]):
        """Send notifications through all enabled channels"""
        if not jobs:
            return
        
        self.notify_terminal(jobs)
        self.notify_email(jobs)
        self.notify_file(jobs)

