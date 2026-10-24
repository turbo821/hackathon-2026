"""Разовый помощник: выполнить команду на сервере по SSH.

Использование: python ssh_run.py "<команда>"
Пароль берётся из переменной окружения SSHPASS.
"""

import os
import sys
import time

import paramiko

HOST = os.environ.get("SSH_HOST", "176.124.223.203")
USER = os.environ.get("SSH_USER", "root")
PASSWORD = os.environ["SSHPASS"]


def run(command: str, timeout: int = 180, attempts: int = 4) -> str:
    last_error = ""
    for attempt in range(attempts):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                HOST,
                username=USER,
                password=PASSWORD,
                timeout=30,
                banner_timeout=45,
                auth_timeout=30,
            )
            _, stdout, stderr = client.exec_command(command, timeout=timeout)
            out = stdout.read().decode("utf-8", "replace")
            err = stderr.read().decode("utf-8", "replace")
            code = stdout.channel.recv_exit_status()
            return f"[exit {code}]\n{out}{err}"
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
            time.sleep(5 * (attempt + 1))
        finally:
            client.close()
    return f"[FAILED: {last_error}]"


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    print(run(cmd))
