import os

from dotenv import load_dotenv

load_dotenv()

S3_URL = f"https://{os.getenv('S3_ENDPOINT_URL')}/{os.getenv('S3_BUCKET_NAME')}"

LICENSES = [
    "https://choosealicense.com/licenses/mit/",
    "https://choosealicense.com/licenses/apache-2.0/",
    "https://choosealicense.com/licenses/gpl-3.0/",
    "https://creativecommons.org/licenses/by/4.0/",
    "https://creativecommons.org/licenses/by-sa/4.0/",
    "https://creativecommons.org/publicdomain/zero/1.0/",
]
