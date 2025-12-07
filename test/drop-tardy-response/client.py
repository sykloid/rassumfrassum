#!/usr/bin/env python3
"""
Test client for tardy-initialize-response test.
Verifies that tardy initialize responses are dropped.
"""

import asyncio

from rassumfrassum.test2 import LspTestEndpoint, log

async def main():
    """Test that tardy initialize responses are dropped."""

    client = await LspTestEndpoint.create()

    # Send initialize
    req_id = await client.request('initialize', {})

    # Expect initialize response (aggregated, but only from S1 due to timeout)
    response = await client.read_response(req_id)
    result = response['result']
    capabilities = result.get('capabilities', {})
    server_info = result.get('serverInfo', {})

    log("client", f"Got initialize response from: {server_info.get('name', 'unknown')}")

    # Send initialized notification
    await client.notify('initialized', {})

    # Wait for potential tardy response from S2
    # S2 delays 2500ms, aggregation timeout is 2000ms
    # Wait 2700ms total to ensure tardy response has arrived at rass
    log("client", "Waiting for potential tardy initialize response...")
    await asyncio.sleep(2.7)

    # Critical assertion: verify no duplicate initialize response
    await client.assert_no_message_pending(timeout_sec=0.1)
    log("client", "Tardy initialize response was correctly dropped!")

    await client.shutdown()

if __name__ == '__main__':
    asyncio.run(main())
