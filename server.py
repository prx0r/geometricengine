import os, json, sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
from pathlib import Path

os.environ["TOKENIZERS_PARALLELISM"] = "false"
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.graph import graph
from src.weights import apply_feedback

DB_PATH = "data/engine.sqlite"

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    pass

class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}

        if self.path == "/api/chat":
            try:
                result = graph.invoke(
                    {"thread_id": body.get("thread_id", "web"),
                     "user_text": body["user_text"],
                     "failure_tags": body.get("failure_tags", []),
                     "rejected_seed": body.get("rejected_seed", {}),
                     "rejected_response": body.get("rejected_response", "")},
                    {"configurable": {"thread_id": body.get("thread_id", "web")}},
                )
                resp = {"final_response": result.get("final_response", ""),
                        "pathway_run_id": result.get("pathway_run_id", ""),
                        "hermes_seed": result.get("hermes_seed", {}),
                        "candidate_nodes": result.get("candidate_nodes", {}),
                        "retrieved_hyperedges": result.get("retrieved_hyperedges", []),
                        "user_text": body.get("user_text", "")}
            except Exception as e:
                resp = {"error": str(e)}
            self._json(resp)
        elif self.path == "/api/feedback":
            apply_feedback(DB_PATH, body["pathway_run_id"], body["score"])
            self._json({"ok": True})
        else:
            self._json({"error": "not found"}, 404)

    def _json(self, data, code=200):
        data_bytes = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data_bytes)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data_bytes)

    def log_message(self, fmt, *args):
        pass

PORT = int(os.environ.get("PORT", 2222))
server = ThreadedHTTPServer(("0.0.0.0", PORT), Handler)
print(f"Server on 0.0.0.0:{PORT}")
server.serve_forever()
