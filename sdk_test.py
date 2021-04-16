import os.path
import time

import discordsdk


with open(os.path.join(os.path.dirname(__file__), '.application_id')) as f:
    app = discordsdk.Discord(int(f.read().rstrip()), discordsdk.CreateFlags.default)

lobbymgr = app.get_lobby_manager()


def lobby_search(result):
    if result == discordsdk.Result.ok:
        print(lobbymgr.lobby_count())


query = lobbymgr.get_search_query()
query.limit(10)
lobbymgr.search(search, lobby_search)

while 1:
    time.sleep(1/10)
    app.run_callbacks()
