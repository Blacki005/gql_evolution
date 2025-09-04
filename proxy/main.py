import os
import asyncio
from aiohttp import web, ClientSession

# The target server to proxy requests to
TARGET_SERVER = os.getenv("TARGET_SERVER", "http://host.docker.internal:8001")

async def handle_request(request):
    """
    Handles incoming requests and forwards them to the target server.
    """
    async with ClientSession() as session:
        # Construct the URL to forward the request
        target_url = f"{TARGET_SERVER}{request.path_qs}"

        # Forward the request to the target server
        async with session.request(
            method=request.method,
            url=target_url,
            headers=request.headers,
            data=await request.read(),
            allow_redirects=False
        ) as response:
            # Return the response from the target server back to the client
            headers = response.headers.copy()
            body = await response.read()

            # Create the response object
            return web.Response(
                status=response.status,
                body=body,
                headers=headers,
            )

async def run_server():
    """
    Starts the reverse-proxy server.
    """
    app = web.Application()
    app.router.add_route('*', '/{tail:.*}', handle_request)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=8000)
    await site.start()
    print(f"Reverse proxy server started on http://0.0.0.0:8000 redirecting to {TARGET_SERVER}")
    try:
        while True:
            await asyncio.sleep(3600)  # Keep the server running
    except asyncio.CancelledError:
        await runner.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        print("Server stopped.")
