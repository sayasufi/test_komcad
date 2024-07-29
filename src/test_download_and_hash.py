import asyncio
import pytest
import tempfile
from pathlib import Path
from git import Repo, GitCommandError
from download_and_hash import RepositoryHandler, main
from typing import List
from unittest.mock import patch, AsyncMock
import logging


class TestRepositoryHandler:
    REPO_URL = "https://github.com/psf/requests"

    @pytest.mark.asyncio
    async def test_repository_handler(self) -> None:
        """
        Тестовая функция для клонирования репозитория и вычисления SHA256 хэшей для каждого файла.
        """
        handler = RepositoryHandler(self.REPO_URL)
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            handler.clone_repo(temp_path)

            # Проверка, что файлы были успешно извлечены
            extracted_files: List[Path] = [
                file_path
                for file_path in Path(handler.repo_path).rglob("*")
                if file_path.is_file() and ".git" not in file_path.parts
            ]
            assert len(extracted_files) > 0

            # Создание задач на хэширование файлов и проверка хэшей
            tasks = [handler.hash_file(file_path) for file_path in extracted_files]
            hashes = await asyncio.gather(*tasks)
            assert all(
                len(hash_val) == 64 for hash_val in hashes
            )  # Длина SHA256 хэша должна быть 64 символа

    @pytest.mark.asyncio
    async def test_clone_repo_failure(self) -> None:
        """
        Тестовая функция для проверки обработки ошибок при клонировании репозитория.
        """
        handler = RepositoryHandler("https://invalid.url/repo.git")
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            with pytest.raises(GitCommandError):
                handler.clone_repo(temp_path)

    @pytest.mark.asyncio
    async def test_empty_repository(self) -> None:
        """
        Тестовая функция для проверки обработки пустого репозитория.
        """
        handler = RepositoryHandler(self.REPO_URL)
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            handler.clone_repo(temp_path)
            # Удаление всех файлов из репозитория
            for file_path in Path(handler.repo_path).rglob("*"):
                if file_path.is_file():
                    file_path.unlink()
            extracted_files = await handler.collect_files()
            assert len(extracted_files) == 0

    @pytest.mark.asyncio
    async def test_process_files_with_mock(self) -> None:
        """
        Тестовая функция для проверки метода process_files с использованием mock.
        """
        handler = RepositoryHandler(self.REPO_URL)
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            handler.clone_repo(temp_path)
            files_to_hash = await handler.collect_files()
            with patch.object(
                handler, "compute_hashes", new_callable=AsyncMock
            ) as mock_compute_hashes:
                await handler.process_files()
                mock_compute_hashes.assert_called_once_with(files_to_hash)

    @pytest.mark.asyncio
    async def test_hash_file_exception(self) -> None:
        """
        Тестовая функция для проверки обработки исключений при чтении файлов.
        """
        handler = RepositoryHandler(self.REPO_URL)
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            handler.clone_repo(temp_path)
            # Создаем фиктивный файл, который вызывает исключение при чтении
            broken_file = Path(handler.repo_path) / "broken_file.txt"
            with broken_file.open("wb") as f:
                f.write(b"dummy content")
            with patch("aiofiles.open", side_effect=IOError):
                with pytest.raises(IOError):
                    await handler.hash_file(broken_file)

    @pytest.mark.asyncio
    async def test_clone_repo_git_error(self) -> None:
        """
        Тестовая функция для проверки обработки GitCommandError при клонировании репозитория.
        """
        handler = RepositoryHandler("https://invalid.url/repo.git")
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            with patch.object(
                Repo, "clone_from", side_effect=GitCommandError("error", 1)
            ):
                with pytest.raises(GitCommandError):
                    handler.clone_repo(temp_path)

    @pytest.mark.asyncio
    async def test_logging_info(self, caplog) -> None:
        """
        Тестовая функция для проверки логирования информации.
        """
        handler = RepositoryHandler(self.REPO_URL)
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            handler.clone_repo(temp_path)
            files_to_hash = await handler.collect_files()
            file_hashes = await handler.compute_hashes(files_to_hash)
            with caplog.at_level(logging.INFO):
                await handler.process_files()
                for file_path, hash_val in file_hashes:
                    assert f"{file_path}: {hash_val}" in caplog.text

    @pytest.mark.asyncio
    async def test_run_method(self) -> None:
        """
        Тестовая функция для проверки метода run.
        """
        handler = RepositoryHandler(self.REPO_URL)
        with patch.object(handler, "clone_repo") as mock_clone_repo, patch.object(
            handler, "process_files"
        ) as mock_process_files:
            await handler.run()
            mock_clone_repo.assert_called_once()
            mock_process_files.assert_called_once()

    def test_main_execution(self, monkeypatch) -> None:
        """
        Тестовая функция для проверки основной точки входа.
        """
        with patch("download_and_hash.asyncio.run") as mock_run:
            import download_and_hash

            monkeypatch.setattr(download_and_hash, "__name__", "__main__")
            download_and_hash.main()
            mock_run.assert_called_once()


if __name__ == "__main__":
    pytest.main()
