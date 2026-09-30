
import datetime
import logging
import requests
import time
import os
import sys
from dotenv import load_dotenv
load_dotenv()
BASE_URL = "https://www.zerochan.net"
USER_AGENT = os.getenv("USER_AGENT")
RATE_LIMIT_DELAY = 1.1 
IMMICH_API_KEY = os.getenv("IMMICH_API_KEY")
IMMICH_UPLOAD_URL = os.getenv("IMMICH_UPLOAD_URL")
PAGE_SIZE = 100 

if not os.path.exists("data"):
    os.makedirs("data")

logging.basicConfig(level=logging.INFO, format="%(message)s",filename="data/zerochan_api.log",filemode='w')
logger = logging.getLogger(__name__)
class RateLimiter:
    """Rate limiter to ensure we don't exceed the API's rate limit."""

    def __init__(self,images_limit: int):
        self.interval = 60 / images_limit
        self.last = 0.0

    def wait(self):
        delta = time.monotonic() - self.last
        if delta < self.interval:
            time.sleep(self.interval - delta)
        self.last = time.monotonic()

limiter = RateLimiter(images_limit=30)  # Limit to 30 images per minute
sesion = requests.Session()
assert USER_AGENT is not None, "USER_AGENT environment variable is not set"
sesion.headers.update({"User-Agent": USER_AGENT})

def _request(url: str, params: dict | None = None, retries: int = 3) -> requests.Response:
    """Wrapper request dengan retry dan rate limit."""
    for attempt in range(retries):
        response = sesion.get(url, params=params, timeout=60)
        if response.status_code == 429:
            logger.warning("Too many requests (429). Waiting before retrying...")
            # print("Too many requests (429). Waiting before retrying...")
            time.sleep(retries * 60)  # Wait longer before retrying
            continue
        response.raise_for_status()
        limiter.wait()
        return response
    logger.error("Failed to get response after multiple retries")
    raise Exception("Failed to get response after multiple retries")

def _get(path: str, params: dict | None = None) -> dict:
    """Wrapper GET request dengan header wajib + delay rate limit."""
    limiter.wait()
    params = dict(params or {}, json="")  # trigger response JSON
    response = _request(f"{BASE_URL}{path}", params=params).json()
    return response

def iter_all_entries(tag: str): 
    """ Iterate through all entries for a given tag, handling pagination automatically."""
    path = "/" + tag.replace(" ", "+")
    page = 1
    while True:
        items = _get(path, {"p": page, "l": PAGE_SIZE}).get("items", [])
        if not items:
            return
        logger.info(f"Fetched {len(items)} items from page {page} for tag '{tag}'")
        print(f"Fetched {len(items)} items from page {page} for tag '{tag}'")
        yield from items
        page += 1
def load_done() -> set[str]:
    """Load the set of already downloaded entry IDs from a file."""
    done_file = "data/done.txt"
    if os.path.exists(done_file):
        with open(done_file, "r") as f:
            return set(line.strip() for line in f)
    return set()

def mark_done(entry_id: str):
    """Mark an entry ID as done by appending it to the done.txt file."""
    with open("data/done.txt", "a") as f:
        if entry_id not in load_done():
            f.write(f"{entry_id}\n")

def download_all(tag: str, save_dir: str = "./tmp"):
    """Download all images to project tmp folder,
    since the given tmp folder from the system is not
    effect to the project flow, and if the tmp directory
    using tmp system the name of the file will be random and not readable,
    so we need to save it in the project tmp folder.
    """
    os.makedirs(save_dir, exist_ok=True)
   
    done = skipped = 0
    done_id = load_done()

    for entry in iter_all_entries(tag):
        entry_id = str(entry['id'])
        if entry_id in done_id:
            skipped += 1
            logger.info(f"Entry {entry_id} already downloaded, skipping. Total skipped: {skipped}")
            # print(f"Entry {entry_id} already downloaded, skipping. Total skipped: {skipped}")
            continue
        try:
            detail = _get(f"/{entry_id}")
            url = detail.get("full") or detail.get("large") or detail.get('potrait') or detail.get('landscape')
            if not url:
                logger.warning(f"No image URL for entry {entry_id}, skipping.")
                print(f"No image URL for entry {entry_id}, skipping.")
                continue
            limiter.wait()
            data = _request(url).content
            assets_id = upload_image_to_immich(f"{entry_id}_{os.path.basename(url)}", data, entry_id)
            mark_done(entry_id)
            done_id.add(entry_id)
            done += 1
            logger.info(f"Downloaded and uploaded entry {entry_id} to Immich with asset ID {assets_id}. Total done: {done}, skipped: {skipped}")
            
        except Exception as e:
            print(f"Error processing entry {entry_id}: {e}")
            

    logger.info(f"Finished processing tag '{tag}'. Total done: {done}, skipped: {skipped}")
    logger.info("================= Download Complete =================")

    




def upload_image_to_immich(file_name: str, data:bytes, entry_id: str,retries: int = 3) -> str:
    """ Upload donwloaded image to Immich server. """
    now = datetime.datetime.now().isoformat()
    assert IMMICH_API_KEY is not None, "IMMICH_API_KEY environment variable is not set"
    assert IMMICH_UPLOAD_URL is not None, "IMMICH_UPLOAD_URL environment variable is not set"
    for attempt in range(retries):
        try:
            response = requests.post(
                IMMICH_UPLOAD_URL,
                headers={"x-api-key": IMMICH_API_KEY},
                files={"assetData": (file_name,data)},
                data={
                    "deviceAssetId": f"zerochan_{entry_id}",
                    "deviceId": "zerochan_script",
                    "fileCreatedAt": now,
                    "fileModifiedAt": now,
                    },
                )
            if response.status_code in (200, 201):
                
                return response.json()['id']  # Return the ID of the uploaded asset from Immich response
            else:
                logger.warning(f"Attempt {attempt + 1}: Cannot upload to Immich, status code: {response.status_code}")
                return f"Cannot upload to Immich, status code: {response.status_code}"
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1}: Error uploading to Immich: {e}")
            
        time.sleep(5*attempt)  # Wait before retrying
  
    
    
    return "Failed to upload image to Immich after all retries."


if __name__ == "__main__":

    if len(sys.argv) < 2:
        logger.error("Character not provided. Usage: python zerochan_api.py <tag>")
        print("Usage: python zerochan_api.py <tag>")
        sys.exit(1)

    tag = sys.argv[1]
    try:
        download_all(tag)
    except Exception as e:
        logger.error(f"Error during download/upload process: {e}")
        print(f"Error during download/upload process: {e}")