from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import starter
import logging
import check_json

logger = logging.getLogger("checker")
logging.basicConfig()
logger.setLevel(logging.INFO)

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):

    def send_text(self, code: int, message: str):
        self.send_response(code)
        self.send_header("Content-type", "application/text")
        self.send_header("Content-Length", str(len(message)))
        self.end_headers()
        self.wfile.write(message.encode("utf-8"))

    def send_json(self, data):
        text = json.dumps(data, indent=4, default=str)
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.send_header("Content-Length", str(len(text)))
        self.end_headers()
        self.wfile.write(text.encode("utf-8"))

    def do_GET(self):
        try:
            list = self.path.split("/")
            paths = list[1:]
            if len(paths) > 0:
                if len(paths) == 2:
                    if paths[0] == "result":
                        uid = paths[1]
                        result = starter.task_get(uid)
                        if result == None:
                            self.send_text(400, uid + " not found")
                            return
                        else:
                            self.send_json(result)
                            return
                    #
                self.send_text(400, "wait /result/f50ec0b7-f960-400d-91f0-c42a6d44e3d0")
                return
            #

            self.send_text("Hello, world!")
        except Exception as e:
            logger.exception(e)
            self.send_text(500, starter.exception_str(e))

    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length)
            logger.info(self.path + ", Content-Length=" + str(content_length))

            input = json.loads(body)
            check_json.check(input)
            uid = starter.task_add(input)
            self.send_text(200, uid)

        except check_json.CheckJsonException as e:
            logger.error("json error: " + e.message)
            self.send_text(500, "json error: " + e.message)
        except json.decoder.JSONDecodeError as e:
            logger.error("json error: " + body.decode("utf-8"))
            self.send_text(500, "json parsing error: pos=" + str(e.pos) + ", line=" + str(e.lineno) + ", col=" + str(e.colno))
        except Exception as e:
            logger.exception(e)
            self.send_text(500, starter.exception_str(e))

httpd = HTTPServer(('0.0.0.0', 3356), SimpleHTTPRequestHandler)
logger.info("server start forever")
httpd.serve_forever()