from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pipeline.sftp_client import SftpClient, SftpConfig


@pytest.fixture
def config() -> SftpConfig:
    return SftpConfig(
        host="sftp.example.test",
        port=2222,
        username="migrator",
        password="pass",
        remote_dir="/incoming",
    )


def _mock_transport_and_sftp():
    mock_transport = MagicMock()
    mock_sftp = MagicMock()
    return mock_transport, mock_sftp


def test_session_closes_both_sftp_client_and_transport(config: SftpConfig) -> None:
    # This is the regression test for the leak: paramiko.SFTPClient.close()
    # does not close the underlying Transport, so both must be closed
    # explicitly. Assert on both mocks independently.
    mock_transport, mock_sftp = _mock_transport_and_sftp()

    with (
        patch("pipeline.sftp_client.paramiko.Transport", return_value=mock_transport),
        patch("pipeline.sftp_client.paramiko.SFTPClient.from_transport", return_value=mock_sftp),
    ):
        client = SftpClient(config)
        with client._session() as sftp:
            assert sftp is mock_sftp

    mock_sftp.close.assert_called_once()
    mock_transport.close.assert_called_once()


def test_session_closes_transport_even_if_block_raises(config: SftpConfig) -> None:
    mock_transport, mock_sftp = _mock_transport_and_sftp()

    with (
        patch("pipeline.sftp_client.paramiko.Transport", return_value=mock_transport),
        patch("pipeline.sftp_client.paramiko.SFTPClient.from_transport", return_value=mock_sftp),
    ):
        client = SftpClient(config)
        with pytest.raises(RuntimeError):
            with client._session():
                raise RuntimeError("boom")

    mock_sftp.close.assert_called_once()
    mock_transport.close.assert_called_once()


def test_poll_for_ready_file_returns_true_when_marker_present(config: SftpConfig) -> None:
    mock_transport, mock_sftp = _mock_transport_and_sftp()
    mock_sftp.listdir.return_value = ["transactions.txt", "transactions.txt.done"]

    with (
        patch("pipeline.sftp_client.paramiko.Transport", return_value=mock_transport),
        patch("pipeline.sftp_client.paramiko.SFTPClient.from_transport", return_value=mock_sftp),
    ):
        client = SftpClient(config)
        result = client.poll_for_ready_file(
            "transactions.txt", timeout_seconds=5, interval_seconds=1
        )

    assert result is True
    # Each poll check opens and closes its own session rather than holding
    # one connection open for the whole timeout window.
    mock_transport.close.assert_called_once()


def test_poll_for_ready_file_returns_false_when_marker_missing(config: SftpConfig) -> None:
    mock_transport, mock_sftp = _mock_transport_and_sftp()
    mock_sftp.listdir.return_value = ["transactions.txt"]  # marker never appears

    with (
        patch("pipeline.sftp_client.paramiko.Transport", return_value=mock_transport),
        patch("pipeline.sftp_client.paramiko.SFTPClient.from_transport", return_value=mock_sftp),
        patch("pipeline.sftp_client.sleep"),  # skip real waiting in the test
    ):
        client = SftpClient(config)
        result = client.poll_for_ready_file(
            "transactions.txt", timeout_seconds=2, interval_seconds=1
        )

    assert result is False


def test_download_creates_parent_directory_and_fetches_file(config: SftpConfig, tmp_path) -> None:
    mock_transport, mock_sftp = _mock_transport_and_sftp()
    destination = tmp_path / "nested" / "transactions.txt"

    with (
        patch("pipeline.sftp_client.paramiko.Transport", return_value=mock_transport),
        patch("pipeline.sftp_client.paramiko.SFTPClient.from_transport", return_value=mock_sftp),
    ):
        client = SftpClient(config)
        result_path = client.download("transactions.txt", destination)

    assert result_path == destination
    assert destination.parent.exists()
    mock_sftp.get.assert_called_once_with("/incoming/transactions.txt", str(destination))
    mock_transport.close.assert_called_once()
