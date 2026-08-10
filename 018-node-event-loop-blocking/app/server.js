const fs = require("fs");
const http = require("http");
const { execFile, execFileSync } = require("child_process");

const completions = "/var/lib/checkout-node/completed.log";
const sleep = "/run/current-system/sw/bin/sleep";

const runTask = (done) => { execFileSync(sleep, ["1"]); done(); };

function finish(id, response) {
  fs.appendFileSync(completions, `${id}\n`);
  response.writeHead(200, { "content-type": "text/plain" });
  response.end("completed");
}

const server = http.createServer((request, response) => {
  if (request.method === "GET" && request.url === "/health") {
    response.writeHead(200, { "content-type": "text/plain" });
    response.end("ok");
    return;
  }

  const match = request.url.match(/^\/tasks\/([^/]+)$/);
  if (request.method === "POST" && match) {
    runTask(() => finish(match[1], response));
    return;
  }

  response.writeHead(404, { "content-type": "text/plain" });
  response.end("missing");
});

server.listen(3000, "127.0.0.1");
