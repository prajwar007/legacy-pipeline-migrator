from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from time import sleep

import paramiko


@dataclass(frozen=True)
class SftpConfig:
    host: str
    port: int
    username: str
    password: str
    remote_dir: str


class SftpClient:
    def __init__(self, config: SftpConfig) -> None:
        self.config = config

    def poll_for_ready_file(
        self,
        filename: str,
        *,
        timeout_seconds: int = 300,
        interval_seconds: int = 10,
    ) -> bool:
        marker = f"{filename}.done"
        elapsed = 0

        while elapsed <= timeout_seconds:
            # Reconnect on each check rather than holding one connection
            # open for the full poll window — SFTP servers commonly drop
            # idle sessions, which would otherwise fail the whole poll.
            with self._session() as sftp:
                names = set(sftp.listdir(self.config.remote_dir))
            if filename in names and marker in names:
                return True
            sleep(interval_seconds)
            elapsed += interval_seconds
        return False

    def download(self, filename: str, destination: str | Path) -> Path:
        destination_path = Path(destination)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        remote_path = f"{self.config.remote_dir.rstrip('/')}/{filename}"
        with self._session() as sftp:
            sftp.get(remote_path, str(destination_path))
        return destination_path

    @contextmanager
    def _session(self) -> Iterator[paramiko.SFTPClient]:
        # paramiko.SFTPClient.close() only closes the channel (self.sock);
        # it does NOT close the underlying Transport, which owns its own
        # socket and background thread. Closing both here is what actually
        # releases the connection instead of leaking one per call.
        transport = paramiko.Transport((self.config.host, self.config.port))
        try:
            transport.connect(username=self.config.username, password=self.config.password)
            sftp = paramiko.SFTPClient.from_transport(transport)
            try:
                yield sftp
            finally:
                sftp.close()
        finally:
            transport.close()
