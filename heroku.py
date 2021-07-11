import base64
import os

# for heroku deployment. encode private files such as config.py as base64 config vars. annoying but it works.
for k, v in os.environ.items():
    if k.startswith("PRIVATEFILE_"):
        k = k.replace("PRIVATEFILE_", "", 1)
        if os.path.exists(k):
            print(f"{k} exists, skipping.")
        else:
            file = base64.b64decode(v)
            with open(k, "wb+") as f:
                f.write(file)
