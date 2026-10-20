"""
Script para geracao de atalho executavel robusto e compativel com a Barra de Tarefas do Windows 11.
"""

from pathlib import Path
import subprocess
import sys


def create_pinnable_shortcut():
    proj_dir = Path(__file__).parent.resolve()
    ico_path = (proj_dir / "assets" / "jirabot.ico").resolve()
    bat_path = (proj_dir / "iniciar.bat").resolve()
    lnk_proj = (proj_dir / "JiraBot.lnk").resolve()

    desktop_dir = Path.home() / "Desktop"
    lnk_desktop = (desktop_dir / "JiraBot.lnk").resolve() if desktop_dir.exists() else None

    cmd_exe = Path(r"C:\Windows\System32\cmd.exe")

    # Argumentos com escape seguro para diretorios com espacos
    # /k garante que a janela do terminal permaneca aberta exibindo o menu interativo
    cmd_args = f'/k "cd /d ""{str(proj_dir)}"" && python cli.py menu"'

    ps_commands = [
        "$ws = New-Object -ComObject WScript.Shell",
        f'$s1 = $ws.CreateShortcut("{str(lnk_proj)}")',
        f'$s1.TargetPath = "{str(cmd_exe)}"',
        f'$s1.Arguments = \'{cmd_args}\'',
        f'$s1.WorkingDirectory = "{str(proj_dir)}"',
        f'$s1.IconLocation = "{str(ico_path)},0"',
        "$s1.Description = 'JiraBot - Gerenciador Inteligente de Horas e Worklog do Jira'",
        "$s1.Save()",
    ]

    if lnk_desktop:
        ps_commands.extend([
            f'$s2 = $ws.CreateShortcut("{str(lnk_desktop)}")',
            f'$s2.TargetPath = "{str(cmd_exe)}"',
            f'$s2.Arguments = \'{cmd_args}\'',
            f'$s2.WorkingDirectory = "{str(proj_dir)}"',
            f'$s2.IconLocation = "{str(ico_path)},0"',
            "$s2.Description = 'JiraBot - Gerenciador Inteligente de Horas e Worklog do Jira'",
            "$s2.Save()",
        ])

    cmd = ["powershell", "-NoProfile", "-Command", "; ".join(ps_commands)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        print("Atalho robusto gerado com sucesso!")
        print(f"  - Local: {lnk_proj}")
    else:
        print(f"Erro ao gerar atalho: {res.stderr}")


if __name__ == "__main__":
    create_pinnable_shortcut()
