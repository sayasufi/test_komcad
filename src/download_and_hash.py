"""
Модуль для клонирования репозитория и вычисления SHA256 хэшей файлов.
"""

import asyncio
import hashlib
import logging
import tempfile
from pathlib import Path
from typing import List, Tuple

import aiofiles
from git import GitCommandError, Repo

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

CHUNK_SIZE = 8192  # Определяем константу для размера читаемого блока


class RepositoryHandler:
    """
    Класс для обработки репозитория: клонирование, вычисление хэшей файлов.
    """

    def __init__(self, repo_url: str) -> None:
        """Инициализация класса с указанием URL репозитория.

        :param repo_url: URL репозитория для клонирования.
        """
        self.repo_url = repo_url
        self.repo_path: Path = None

    async def hash_file(self, file_path: Path) -> str:
        """
        Вычисляет SHA256 хэш для указанного файла.

        :param file_path: Путь к файлу, для которого нужно вычислить хэш.
        :return: Строка с SHA256 хэшем файла.
        """
        sha256 = hashlib.sha256()
        async with aiofiles.open(file_path, "rb") as file_to_hash:
            while True:
                chunk = await file_to_hash.read(CHUNK_SIZE)
                if not chunk:
                    break
                sha256.update(chunk)
        return sha256.hexdigest()

    def clone_repo(self, temp_dir: Path) -> None:
        """Клонирует репозиторий в временную директорию.

        :param temp_dir: Путь к временной директории.
        :raises GitCommandError: Если происходит ошибка
        при клонировании репозитория.
        """
        self.repo_path = temp_dir / "repo"
        logging.info("Клонирование репозитория в %s", self.repo_path)
        try:
            Repo.clone_from(self.repo_url, self.repo_path)
        except GitCommandError as error:
            logging.error("Ошибка при клонировании репозитория: %s", error)
            raise

    async def collect_files(self) -> List[Path]:
        """Собирает список всех файлов в репозитории, исключая директорию .git.

        :return: Список путей к файлам.
        """
        return [
            file_path
            for file_path in self.repo_path.rglob("*")
            if file_path.is_file() and ".git" not in file_path.parts
        ]

    async def compute_hashes(
        self, files_to_hash: List[Path]
    ) -> List[Tuple[Path, str]]:
        """Вычисляет SHA256 хэши для списка файлов.

        :param files_to_hash: Список путей к файлам для вычисления хэшей.
        :return: Список кортежей (путь к файлу, SHA256 хэш).
        """
        tasks = [self.hash_file(file_path) for file_path in files_to_hash]
        hashes = await asyncio.gather(*tasks)
        return list(zip(files_to_hash, hashes))

    async def process_files(self) -> None:
        """Обрабатывает файлы в клонированном репозитории:
        вычисляет и выводит SHA256 хэши.
        """
        file_hashes = await self.compute_hashes(await self.collect_files())
        for file_path, hash_val in file_hashes:
            logging.info("%s: %s", file_path, hash_val)

    async def run(self) -> None:
        """Основной метод для выполнения клонирования и обработки файлов
        в репозитории.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            self.clone_repo(temp_path)
            await self.process_files()


def main() -> None:
    """Основная функция для запуска."""
    repo_url = "https://gitea.radium.group/radium/project-configuration.git"
    repo_handler = RepositoryHandler(repo_url)
    asyncio.run(repo_handler.run())


if __name__ == "__main__":
    main()
