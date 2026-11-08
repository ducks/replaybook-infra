import http.server
import os
from pathlib import Path
import pwd
import grp
import re
import stat

root = Path("/var/lib/receipts")

class Handler(http.server.BaseHTTPRequestHandler):
    def reply(self, code, text):
        self.send_response(code); self.end_headers(); self.wfile.write(text.encode())

    def receipt(self):
        prefix = "/receipts/"
        if not self.path.startswith(prefix): return None
        identifier = self.path[len(prefix):]
        return identifier if re.fullmatch(r"[a-zA-Z0-9_-]{1,200}", identifier) else None

    def do_GET(self):
        if self.path == "/health": return self.reply(200, "ready")
        if self.path == "/identity": return self.reply(200, pwd.getpwuid(os.geteuid()).pw_name)
        if self.path == "/history":
            try: return self.reply(200, (root / "incoming/historical").read_text())
            except OSError: return self.reply(503, "storage unavailable")
        if self.path == "/storage-policy":
            info = (root / "incoming").stat()
            files = list((root / "incoming").iterdir())
            safe_files = all(stat.S_IMODE(p.stat().st_mode) == 0o640 and p.stat().st_uid == pwd.getpwnam("receipt-writer").pw_uid and p.stat().st_gid == grp.getgrnam("receipts").gr_gid for p in files)
            return self.reply(200, "restricted" if safe_files and stat.S_IMODE(info.st_mode) == 0o750 and info.st_uid == pwd.getpwnam("receipt-writer").pw_uid and info.st_gid == grp.getgrnam("receipts").gr_gid else "unsafe")
        identifier = self.receipt()
        if identifier:
            path = root / "incoming" / identifier
            try:
                present = path.read_text() == identifier
            except PermissionError: return self.reply(503, "storage unavailable")
            except FileNotFoundError: present = False
            return self.reply(200 if present else 404, "present" if present else "missing")
        self.reply(404,"not found")

    def do_POST(self):
        if os.environ.get("READ_ONLY"): return self.reply(405, "read only")
        identifier = self.receipt()
        if not identifier: return self.reply(404, "not found")
        try:
            path = root / "incoming" / identifier
            with path.open("w") as target:
                target.write(identifier); target.flush(); os.fsync(target.fileno())
            self.reply(201, "stored")
        except OSError as error:
            self.log_error("receipt persistence failed: %s", error)
            self.reply(503, "storage unavailable")

if __name__ == "__main__":
    http.server.ThreadingHTTPServer(("127.0.0.1", int(os.environ.get("PORT", "3000"))), Handler).serve_forever()
