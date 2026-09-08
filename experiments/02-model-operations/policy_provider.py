"""Synthetic policy-test provider with unique response IDs and request counts."""
import uuid
import run_local_experiment as base

original_document = base.response_document


def unique_document(payload):
    result = original_document(payload)
    result['id'] = 'resp_synthetic_' + uuid.uuid4().hex
    return result


base.response_document = unique_document


class Handler(base.SyntheticProviderHandler):
    requests = 0

    def do_GET(self):
        if self.path == '/stats':
            self._write_json(200, {'requests': Handler.requests})
        else:
            super().do_GET()

    def do_POST(self):
        Handler.requests += 1
        super().do_POST()


if __name__ == '__main__':
    base.ThreadingHTTPServer(('0.0.0.0', 4010), Handler).serve_forever()
