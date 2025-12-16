"""Asyncio-compatible stdin/stdout streams that work on Windows.

On Windows, ProactorEventLoop cannot use
connect_read_pipe/connect_write_pipe with sys.stdin/stdout because
they aren't opened with the OVERLAPPED flag required for IOCP. Or
something, like that.  This is a longstanding CPython thing:

https://github.com/python/cpython/issues/71019

This module provides a threaded workaround that bridges blocking stdio
to async pipes.
"""

import asyncio
import os
import sys
import threading
from typing import Tuple


async def create_stdin_reader(use_thread: bool) -> asyncio.StreamReader:
    """
    Create an asyncio StreamReader for stdin.

    Uses a background thread to bridge blocking stdin to an async pipe on Windows.
    """
    loop = asyncio.get_event_loop()

    if use_thread:
        # A thread reads blockingly from stdin and writes to the
        # write-end of a pipe.  The read-end of a pipe is passed to
        # connect_read_pipe.
        read_fd, write_fd = os.pipe()

        def helper():
            pipe_write = os.fdopen(write_fd, 'wb', buffering=0)
            try:
                stdin_fd = sys.stdin.fileno()
                while True:
                    data = os.read(stdin_fd, 4096)
                    if not data:
                        break
                    pipe_write.write(data)
            finally:
                pipe_write.close()

        threading.Thread(target=helper, daemon=True, name="stdin-reader").start()

        # Open the read_fd as a file object for connect_read_pipe
        read_file = os.fdopen(read_fd, 'rb', buffering=0)
    else:
        # Direct approach (Linux/macOS): connect directly to sys.stdin
        read_file = sys.stdin

    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, read_file)
    return reader


async def create_stdout_writer(use_thread: bool) -> asyncio.StreamWriter:
    """
    Create an asyncio StreamWriter for stdout.

    Uses a background thread to bridge an async pipe to blocking stdout on Windows.
    """
    loop = asyncio.get_event_loop()

    if use_thread:
        # A thread reads blockingly from the read end of a pipe and
        # writes to stdout.  The write end of a pipe is passed to
        # connect_write_pipe.
        read_fd, write_fd = os.pipe()

        def helper():
            pipe_read = os.fdopen(read_fd, 'rb', buffering=0)
            try:
                while True:
                    data = pipe_read.read(4096)
                    if not data:
                        break
                    sys.stdout.buffer.write(data)
                    sys.stdout.buffer.flush()
            finally:
                pipe_read.close()

        threading.Thread(target=helper, daemon=True, name="stdout-writer").start()

        # Create asyncio writer from the write end of the pipe
        write_file = os.fdopen(write_fd, 'wb', buffering=0)
    else:
        # Direct approach (Linux/macOS): connect directly to sys.stdout
        write_file = sys.stdout

    transport, protocol = await loop.connect_write_pipe(
        asyncio.streams.FlowControlMixin, write_file
    )
    writer = asyncio.StreamWriter(transport, protocol, None, loop)
    return writer
