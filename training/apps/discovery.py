import http.server
import socket
import urllib.request

upstream = urllib.request.build_opener(urllib.request.ProxyHandler({}))

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            if self.path == "/health":
                with upstream.open("http://inventory.internal:3001/health", timeout=2) as response:
                    body = response.read()
            elif self.path == "/resolve/inventory":
                body = (socket.gethostbyname("inventory.internal") + "\n").encode()
            elif self.path == "/resolve/metrics":
                body = (socket.gethostbyname("metrics.internal") + "\n").encode()
            else:
                self.send_error(404); return
            self.send_response(200)
        except (OSError, urllib.error.URLError) as error:
            self.log_error("upstream discovery failed: %s", error)
            body = b"upstream discovery unavailable\n"
            self.send_response(503)
        self.end_headers()
        self.wfile.write(body)

if __name__ == "__main__":
    http.server.ThreadingHTTPServer(("127.0.0.1", 3000), Handler).serve_forever()
