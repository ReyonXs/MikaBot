from http import HTTPStatus

from furl import furl

METADATA_DIRECTORY_URL = furl(
    'https://api.github.com/repos/xsalazar/emoji-kitchen-backend/contents/app',
    args={'ref': 'main'},
)
METADATA_FILENAME = 'metadata.json'

UPDATE_INTERVAL_DAYS = 7
RETRY_DELAY_MINUTES = 3
RETRYABLE_HTTP_STATUSES = frozenset(
    {
        HTTPStatus.REQUEST_TIMEOUT,
        HTTPStatus.TOO_MANY_REQUESTS,
        HTTPStatus.INTERNAL_SERVER_ERROR,
        HTTPStatus.BAD_GATEWAY,
        HTTPStatus.SERVICE_UNAVAILABLE,
        HTTPStatus.GATEWAY_TIMEOUT,
    }
)

TABLE_NAMES = {
    'metadata': 'EmojiKitchenMetadata',
    'code': 'EmojiKitchenCodes',
    'data': 'EmojiKitchenData',
    'pair': 'EmojiKitchenPairs',
}
COMBINATIONS_VIEW_NAME = 'EmojiKitchenCombinations'
BATCH_SIZE = 2000
IMAGE_CACHE_SIZE = 50
MMAP_RELEASE_INTERVAL_BYTES = 2 * 1024 * 1024
