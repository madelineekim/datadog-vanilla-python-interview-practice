import argparse
from http.server import HTTPServer

from pulse.handler import Handler
from pulse.state import State


def create_server(host='127.0.0.1', port=8000, state=None):
    server = HTTPServer((host, port), Handler)
    server.state = state if state is not None else State()
    return server


def main():
    parser = argparse.ArgumentParser(description='Run Pulse')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    server = create_server(args.host, args.port)
    print('Pulse listening on http://{}:{}'.format(*server.server_address), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
