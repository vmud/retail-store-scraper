"""
Notification System for Scraper Events (#63)

Provides pluggable notification support for scraper events like
completion, errors, and change detection results.

Currently supports:
- Slack (via webhook)
- Console (for local testing)

Additional providers can be added by subclassing NotificationProvider.
"""

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

from src.shared.constants import STATUS


__all__ = [
    'ConsoleNotifier',
    'NotificationManager',
    'NotificationProvider',
    'SlackNotifier',
    'get_notifier',
]



try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class NotificationProvider(ABC):
    """Abstract base class for notification providers."""

    @abstractmethod
    def send(self, message: str, level: str = 'info', **kwargs) -> bool:
        """Send a notification.

        Args:
            message: The notification message
            level: Severity level ('info', 'warning', 'error', 'success')
            **kwargs: Additional provider-specific options

        Returns:
            True if notification was sent successfully, False otherwise
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging."""
        pass


class SlackNotifier(NotificationProvider):
    """Slack notification provider using webhooks.

    Requires SLACK_WEBHOOK_URL environment variable.
    """

    # Map notification levels to Slack attachment colors
    LEVEL_COLORS = {
        'info': '#36a64f',      # Green
        'success': '#36a64f',   # Green
        'warning': '#ff9800',   # Orange
        'error': '#f44336',     # Red
    }

    def __init__(self, webhook_url: str):
        """Initialize Slack notifier.

        Args:
            webhook_url: Slack webhook URL
        """
        self.webhook_url = webhook_url

    @property
    def name(self) -> str:
        return "Slack"

    def send(self, message: str, level: str = 'info', **kwargs) -> bool:
        """Send notification to Slack.

        Args:
            message: The notification message
            level: Severity level for color coding
            **kwargs: Optional 'title' for attachment fallback

        Returns:
            True if sent successfully
        """
        if not REQUESTS_AVAILABLE:
            logging.warning("requests library not available for Slack notifications")
            return False

        color = self.LEVEL_COLORS.get(level, self.LEVEL_COLORS['info'])
        title = kwargs.get('title', 'Scraper Notification')

        payload = {
            'attachments': [{
                'color': color,
                'fallback': f'{title}: {message}',
                'title': title,
                'text': message,
                'mrkdwn_in': ['text']
            }]
        }

        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=STATUS.NOTIFICATION_TIMEOUT
            )
            if response.ok:
                logging.debug(f"Slack notification sent: {message[:50]}...")
                return True
            else:
                logging.warning(f"Slack notification failed: {response.status_code}")
                return False
        except requests.RequestException as e:
            logging.warning(f"Slack notification error: {e}")
            return False


class ConsoleNotifier(NotificationProvider):
    """Console notification provider for local testing/development."""

    # Emoji/prefix by level
    LEVEL_PREFIX = {
        'info': 'ℹ️ ',
        'success': '✅',
        'warning': '⚠️ ',
        'error': '❌',
    }

    @property
    def name(self) -> str:
        return "Console"

    def send(self, message: str, level: str = 'info', **kwargs) -> bool:
        """Print notification to console.

        Args:
            message: The notification message
            level: Severity level for prefix

        Returns:
            Always True
        """
        prefix = self.LEVEL_PREFIX.get(level, self.LEVEL_PREFIX['info'])
        title = kwargs.get('title', '')
        if title:
            print(f"{prefix} [{title}] {message}")
        else:
            print(f"{prefix} {message}")
        return True


class NotificationManager:
    """Manager for sending notifications through multiple providers."""

    def __init__(self):
        """Initialize with empty provider list."""
        self._providers: list = []

    def add_provider(self, provider: NotificationProvider) -> None:
        """Add a notification provider.

        Args:
            provider: NotificationProvider instance
        """
        self._providers.append(provider)
        logging.debug(f"Added notification provider: {provider.name}")

    def send(self, message: str, level: str = 'info', **kwargs) -> Dict[str, bool]:
        """Send notification through all registered providers.

        Args:
            message: The notification message
            level: Severity level
            **kwargs: Additional options passed to providers

        Returns:
            Dictionary mapping provider names to success status
        """
        results = {}
        for provider in self._providers:
            try:
                results[provider.name] = provider.send(message, level, **kwargs)
            except Exception as e:
                logging.warning(f"Notification error ({provider.name}): {e}")
                results[provider.name] = False
        return results

    def notify_scraper_complete(
        self,
        retailer: str,
        store_count: int,
        duration_seconds: int
    ) -> None:
        """Send scraper completion notification.

        Args:
            retailer: Retailer name
            store_count: Number of stores scraped
            duration_seconds: Duration in seconds
        """
        duration_str = _format_duration(duration_seconds)
        message = f"*{retailer.title()}* scraper completed: {store_count:,} stores in {duration_str}"
        self.send(message, level='success', title=f'{retailer.title()} Complete')

    def notify_scraper_error(self, retailer: str, error: str) -> None:
        """Send scraper error notification.

        Args:
            retailer: Retailer name
            error: Error message
        """
        message = f"*{retailer.title()}* scraper failed: {error}"
        self.send(message, level='error', title=f'{retailer.title()} Error')

    def notify_changes_detected(
        self,
        retailer: str,
        new_count: int,
        closed_count: int,
        modified_count: int
    ) -> None:
        """Send change detection notification.

        Args:
            retailer: Retailer name
            new_count: Number of new stores
            closed_count: Number of closed stores
            modified_count: Number of modified stores
        """
        changes = []
        if new_count > 0:
            changes.append(f"+{new_count} new")
        if closed_count > 0:
            changes.append(f"-{closed_count} closed")
        if modified_count > 0:
            changes.append(f"~{modified_count} modified")

        if changes:
            message = f"*{retailer.title()}* changes detected: {', '.join(changes)}"
            self.send(message, level='warning', title=f'{retailer.title()} Changes')


def _format_duration(seconds: int) -> str:
    """Format duration in human-readable form."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        mins = seconds // 60
        secs = seconds % 60
        return f"{mins}m {secs}s"
    else:
        hours = seconds // 3600
        mins = (seconds % 3600) // 60
        return f"{hours}h {mins}m"


def get_notifier() -> Optional[NotificationManager]:
    """Get configured notification manager from environment.

    Checks for notification provider configuration in environment variables:
    - SLACK_WEBHOOK_URL: Enables Slack notifications
    - NOTIFICATIONS_CONSOLE: If 'true', enables console output

    Returns:
        NotificationManager with configured providers, or None if none configured
    """
    manager = NotificationManager()
    providers_added = 0

    # Check for Slack webhook
    slack_url = os.environ.get('SLACK_WEBHOOK_URL')
    if slack_url:
        manager.add_provider(SlackNotifier(slack_url))
        providers_added += 1
        logging.info("Slack notifications enabled")

    # Check for console notifications (development/testing)
    if os.environ.get('NOTIFICATIONS_CONSOLE', '').lower() == 'true':
        manager.add_provider(ConsoleNotifier())
        providers_added += 1
        logging.info("Console notifications enabled")

    if providers_added == 0:
        return None

    return manager
