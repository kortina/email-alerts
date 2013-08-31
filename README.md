A simple script to email alert about new Twitter search results.

You must create a `settings.py` file in this directory, defining the following:

    TWITTER_SETTINGS = {
        "consumer_key": "..",
        "consumer_secret": "..",
        "access_token_key": "..",
        "access_token_secret": ".."
    }

    GMAIL_USER = ".."
    GMAIL_PASSWORD = ".."

Example:

    python twitter_search.py -f ./maxid1 -r "you@gmail.com" -q "aristotle"

You might run this on a cron, every 2 minutes:

      */2 * * * * cd /mnt/email-mentions && python twitter_search.py -f ./aristotle_maxid -r "you@gmail.com" -q "aristotle" > aristotle.log 2>&1


TODO, add support for these other types of searches:

* Facebook search
* iTunes App Store Reviews
* Google Play Store Reviews

