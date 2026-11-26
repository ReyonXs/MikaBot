from functools import cache


@cache
def decode_hex_codepoints(hex_str: bytes) -> str:
    return ''.join([chr(int(part, 16)) for part in hex_str.split(b'-')])
