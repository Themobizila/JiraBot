"""
Modulo de notificacoes locais para o Windows (JiraBot).
"""

from __future__ import annotations

import logging
import subprocess
from typing import Optional

logger = logging.getLogger("JiraBot.Notifier")


def send_notification(title: str, message: str, enabled: bool = True) -> None:
    """Envia uma notificacao nativa no Windows usando PowerShell/BurntToast sem travar a thread."""
    if not enabled:
        return

    logger.info(f"Notificacao: [{title}] {message}")

    # Escapar aspas simples para script PowerShell
    safe_title = title.replace("'", "''")
    safe_msg = message.replace("'", "''")

    ps_script = f"""
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
    $template = @"
    <toast>
        <visual>
            <binding template="ToastGeneric">
                <text>{safe_title}</text>
                <text>{safe_msg}</text>
            </binding>
        </visual>
    </toast>
"@
    $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
    $xml.LoadXml($template)
    $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
    $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("JiraBot")
    $notifier.Show($toast)
    """

    try:
        # Executa em segundo plano sem janela
        subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
    except Exception as e:
        logger.debug(f"Falha ao enviar notificacao PowerShell: {e}")
