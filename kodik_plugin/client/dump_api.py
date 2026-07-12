import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class KodikDumpClient:
    """
    Client for downloading large JSON database dumps from Kodik.
    """

    def __init__(self, token: str, timeout: int = 60):
        self.token = token
        self.timeout = timeout

    def download_dump(self, dump_name: str) -> str:
        """
        Downloads a dump file streamingly and saves it to the local logs directory.
        Returns the absolute path to the downloaded file.
        """
        url = f"https://dumps.kodikres.com/{dump_name}.json?token={self.token}"
        safe_name = dump_name.replace('/', '_')
        file_path = settings.LOG_DIR / f"kodik_dump_{safe_name}.json"

        logger.info(f"Starting download of Kodik dump: {dump_name} to {file_path}")

        try:
            with requests.get(url, stream=True, timeout=self.timeout) as r:
                r.raise_for_status()
                with open(file_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            logger.info("Dump download completed successfully.")
            return str(file_path)
        except requests.RequestException as e:
            logger.error(f"Failed to download dump {dump_name}. Network error: {e}")
            raise
