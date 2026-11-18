#!/usr/bin/env python3
"""keccak256 — pure-Python, stdlib-only, audit-friendly.

WHY THIS FILE EXISTS: Python's hashlib.sha3_256 is SHA-3, which uses a
different (SHA-3 domain) padding than Keccak. The ERC-8004 anchor's
feedbackHash is keccak256 (Ethereum-style), so an outsider verifier without
Ethereum libraries needs this. Keccak-f[1600] is ~100 lines, fully
auditable, and pinned to public test vectors by the self-test below.

Run `python3 keccak.py` to self-test.
"""
_MASK = 0xFFFFFFFFFFFFFFFF

_RNDC = [
    0x0000000000000001, 0x0000000000008082, 0x800000000000808A,
    0x8000000080008000, 0x000000000000808B, 0x0000000080000001,
    0x8000000080008081, 0x8000000000008009, 0x000000000000008A,
    0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
    0x000000008000808B, 0x800000000000008B, 0x8000000000008089,
    0x8000000000008003, 0x8000000000008002, 0x8000000000000080,
    0x000000000000800A, 0x800000008000000A, 0x8000000080008081,
    0x8000000000008080, 0x0000000080000001, 0x8000000080008008,
]

_ROT_OFF = [[0, 36, 3, 41, 18],
            [1, 44, 10, 45, 2],
            [62, 6, 43, 15, 61],
            [28, 55, 25, 21, 56],
            [27, 20, 39, 8, 14]]


def _rotl64(x, n):
    n %= 64
    return ((x << n) | (x >> (64 - n))) & _MASK if n else x


def _keccak_f(a):
    """a: 5x5 list of lanes, a[x][y]; modified in place."""
    for rnd in range(24):
        # theta
        c = [a[x][0] ^ a[x][1] ^ a[x][2] ^ a[x][3] ^ a[x][4] for x in range(5)]
        d = [c[(x - 1) % 5] ^ _rotl64(c[(x + 1) % 5], 1) for x in range(5)]
        for x in range(5):
            for y in range(5):
                a[x][y] ^= d[x]
        # rho + pi: b[y][(2x+3y) mod 5] = rotl(a[x][y], r[x][y])
        b = [[0] * 5 for _ in range(5)]
        for x in range(5):
            for y in range(5):
                b[y][(2 * x + 3 * y) % 5] = _rotl64(a[x][y], _ROT_OFF[x][y])
        # chi
        for y in range(5):
            for x in range(5):
                a[x][y] = b[x][y] ^ ((~b[(x + 1) % 5][y]) & b[(x + 2) % 5][y]) & _MASK
        # iota
        a[0][0] ^= _RNDC[rnd]
    return a


def _lane(b, i):
    return int.from_bytes(b[8 * i:8 * (i + 1)], "little")


def keccak256(data: bytes) -> bytes:
    rate = 136  # bytes; 1088-bit rate / 256-bit output
    a = [[0] * 5 for _ in range(5)]
    # pad10*1 with the Keccak domain byte 0x01 (SHA-3 would use 0x06).
    # q = 1 is the special case: the single remaining byte must be 0x81
    # (0x01 | 0x80); two appended bytes would overflow the block.
    padded = bytearray(data)
    q = rate - (len(padded) % rate)
    if q == 1:
        padded += bytes([0x81])
    elif q == 2:
        padded += bytes([0x01, 0x80])
    else:
        padded += bytes([0x01]) + b"\x00" * (q - 2) + bytes([0x80])
    padded = bytes(padded)
    for off in range(0, len(padded), rate):
        block = padded[off:off + rate]
        for i in range(rate // 8):
            x, y = i % 5, i // 5
            a[x][y] ^= _lane(block, i)
        _keccak_f(a)
    out = bytearray()
    for y in range(5):
        for x in range(5):
            if len(out) < 32:
                out += a[x][y].to_bytes(8, "little")
    return bytes(out[:32])


if __name__ == "__main__":
    vecs = [
        (b"", "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"),
        (b"abc", "4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45"),
        (b"The quick brown fox jumps over the lazy dog",
         "4d741b6f1eb29cb2a9b9911c82f56fa8d73b04959d3d9d222895df6c0b28aa15"),
    ]
    for msg, want in vecs:
        got = keccak256(msg).hex()
        assert got == want, f"keccak self-test FAILED: {msg!r} -> {got} != {want}"
        print(f"PASS keccak256({msg[:24]!r}) == {got[:20]}...")
    print("keccak self-test: all vectors match")
