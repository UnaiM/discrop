import os.path
import time

import discordsdk

with open(os.path.join(os.path.dirname(__file__), '.application_id')) as f:
    app = discordsdk.Discord(int(f.read().rstrip()), discordsdk.CreateFlags.default)

user_manager = app.get_user_manager()


def on_curr_user_update():
    user = user_manager.get_current_user()
    print(f'Current user : {user.username}#{user.discriminator}')


user_manager.on_current_user_update = on_curr_user_update

# Don't forget to call run_callbacks
while 1:
    time.sleep(1/10)
    app.run_callbacks()
