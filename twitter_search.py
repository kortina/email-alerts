import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'httplib2'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'python-oauth2'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'python-twitter'))

import re
import gmailer
import twitter
import settings
import unittest


# Returns a bytestring version of 's', encoded as specified in 'encoding'.
# https://gist.github.com/andreisavu/192270
def smart_str(s, encoding='utf-8', errors='strict'):
    """
    Returns a bytestring version of 's', encoded as specified in 'encoding'.
    """
    if not isinstance(s, basestring):
        try:
            return str(s)
        except UnicodeEncodeError:
            return unicode(s).encode(encoding, errors)
    elif isinstance(s, unicode):
        return s.encode(encoding, errors)
    elif s and encoding != 'utf-8':
        return s.decode('utf-8', errors).encode(encoding, errors)
    else:
        return s


def replace_plain_links_with_anchor_tags(text, hide_query_strings=True):
    text = text or ''
    text = str(text)
    exp = '(?P<entire_link>(?P<host_and_path>https?\:\/\/[^\s\?\<\>]+)' \
          + '(?P<qs>\?[^\s\<\>]+)?)'
    reg = re.compile(exp, re.I)
    if hide_query_strings:
        exp = r'<a href="\g<entire_link>">\g<host_and_path></a>'
        text = reg.subn(exp, text)[0]
    else:
        exp = r'<a href="\g<entire_link>">\g<entire_link></a>'
        text = reg.subn(exp, text)[0]
    return text


def linkify_tweet(tweet, linkify_hyperlinks=True):
    if linkify_hyperlinks:
        tweet = replace_plain_links_with_anchor_tags(tweet,
                                                     hide_query_strings=False)
    tweet = re.sub(r'(\A|\s)@(\w+)',
                   r'\1@<a href="http://www.twitter.com/\2">\2</a>',
                   tweet)
    exp = r'\1#<a href="http://search.twitter.com/search?q=%23\2">\2</a>'
    return re.sub(r'(\A|\s)#(\w+)',
                  exp,
                  tweet)


def email_template_vars_from_tweet(status):
    """
    Params:
    @tweet dict: parsed JSON for a tweet

    Returns:
    dict of info from the tweet formatted for email template
    """
    d = {}
    screen_name = status.user.screen_name
    d['screen_name'] = smart_str(screen_name)
    d['profile_image_url'] = smart_str(status.user.profile_image_url)
    d['ext_url'] = smart_str(status.user.url or '')
    d['profile_link'] = "https://twitter.com/%s" % smart_str(screen_name)
    d['tweet_link'] = "https://twitter.com/%s/status/%s" % (
        smart_str(status.user.screen_name),
        status.id)
    d['tweet_text'] = smart_str(status.text)
    d['created_at'] = smart_str(status.created_at)
    d['created_at'] = re.sub(r" \+.*$", "", d['created_at'])
    d['created_at'] = re.sub(r":\d\d$", "", d['created_at'])
    d['tweet_id'] = status.id
    d['subject'] = '@' + d['screen_name'] + ':' + ' ' + d['tweet_text']
    d['name'] = smart_str(status.user.name)
    d['description'] = smart_str(status.user.description)
    d['favourites_count'] = smart_str(status.user.favourites_count)
    d['followers_count'] = smart_str(status.user.followers_count)
    d['statuses_count'] = smart_str(status.user.statuses_count)
    d['friends_count'] = smart_str(status.user.friends_count)
    return d


def email_body(template_vars):
    """
    Params:
    @template_vars dict: contains tweet info

    Returns:
    dict {
        "html": html body
        "text": plaintext body
    }
    """
    subs = template_vars
    subs['tweet_text'] = linkify_tweet(subs['tweet_text'])
    subs['description'] = linkify_tweet(subs['description'])
    html = """
    <table border="0" cellspacing="0" cellpadding="5">
    <tr>
    <td style="vertical-align:top;">
        <a href="%(profile_link)s"><img style="width:48px;
                                               height:48px;
                                               padding-right:5px;"
                                        src="%(profile_image_url)s" />
    </td>
    <td style="vertical-align:top;" width="400">
        %(tweet_text)s
        <br /><br /><br />
        <a href="%(profile_link)s">@%(screen_name)s</a> -
        <a href="http://twitter.com/home?status=d %(screen_name)s+">DM</a>
        <br />%(created_at)s
        <br /><a href="%(tweet_link)s">%(tweet_link)s</a>
        <div style="max-width:350px;">
            <br ><br /><a href="%(profile_link)s">%(screen_name)s</a>
            - %(name)s
            <br /><a href="%(ext_url)s">%(ext_url)s</a>
            <br />
            <br />%(description)s
            <br />
            <br />followers: %(followers_count)s
            <br />friends: %(friends_count)s
            <br />favs: %(favourites_count)s
            <br />updates: %(statuses_count)s
        </div>
    </td>
    </tr>
    </table>
    <br /><br />
    """ % subs

    html = '<html><body>' + html + '</body></html>'

    text = """Author Screenname: %(screen_name)s
    Time: %(created_at)s
    Tweet: %(tweet_text)s
    Link to author's pg: %(profile_link)s
    Link to reply: http://twitter.com/home?status=@%(screen_name)s+">
    """ % template_vars
    return {"html": html, "text": text}


# Store max id we have seen in a file.
# The following methods read from and write to that file.
def format_since_id_filename(since_id_filename):
    return re.sub(r"[\s\'\"]", "_", since_id_filename)


def write_since_id_to_file(since_id_filename, since_id):
    since_id = long(since_id)
    if since_id <= get_since_id(since_id_filename):
        return
    since_id_filename = format_since_id_filename(since_id_filename)
    f = open(since_id_filename, 'w')
    f.write(smart_str(since_id))
    f.close()


def get_since_id(since_id_filename):
    since_id = 0
    since_id_filename = format_since_id_filename(since_id_filename)

    # Ensure file exists
    f = open(since_id_filename, 'a')
    f.close()

    f = open(since_id_filename, 'r')
    line = f.readline()
    f.close()

    line = line.strip()
    if (line == ''):
        since_id = 0
    else:
        since_id = line

    return long(since_id)


def search_and_email(api, query, since_id_filename, recipients, count=100):
    """
    Params:
    @api twitter.Api: client instance
    @query str: search query for twitter
    @since_id_filename str: file where we store max id we have seen
                            in this search and emailed about. (cursor)
    @recipients str: CSV of emails to notify about tweet
    @count int: max number of tweets to send

    Side Effects:
    Writes to since_id_filename updating the cursor so we don't
    email about the same tweet 2x.

    """
    since_id = get_since_id(since_id_filename)

    tweets = api.GetSearch(term=query, since_id=since_id, count=count,
                           language="en")
    # ensure tweets are sorted oldest => newest
    tweets.sort(key=lambda x: x.id)
    for tweet in tweets:
        email_vars = email_template_vars_from_tweet(tweet)
        body = email_body(email_vars)
        email_tweet(to=recipients, subject=email_vars['subject'],
                    text=body['text'],
                    html=body['html'])

        # import pdb; pdb.set_trace()
        # mark this tweet as done
        write_since_id_to_file(since_id_filename, tweet.id)


def email_tweet(to, subject, text, html=None):
    gmailer.GMAIL_SETTINGS['user'] = settings.GMAIL_USER
    gmailer.GMAIL_SETTINGS['password'] = settings.GMAIL_PASSWORD
    gmailer.mail(to=to, subject=subject, text=text,
                 html=html, cache_connection=True)


class TestSearch(unittest.TestCase):
    import simplejson
    tweet1 = twitter.Status.NewFromJsonDict(simplejson.loads("""{"created_at": "Thu Jul 04 00:05:55 +0000 2013", "favorited": false, "id": 352578986758512640, "retweeted": false, "source": "<a href=\\"https://venmo.com\\" rel=\\"nofollow\\">Venmo</a>", "text": "Just charged gabrielle-smith - Fireworks https://t.co/8ba4Tr1iet", "truncated": false, "urls": {"https://t.co/8ba4Tr1iet": "https://venmo.com/s/gHdI"}, "user": {"created_at": "Tue Jan 24 22:16:48 +0000 2012", "description": "Restless. Nomad.", "favourites_count": 40, "followers_count": 81, "friends_count": 621, "geo_enabled": true, "id": 473365277, "lang": "en", "location": "Walla Walla", "name": "Trevor Boyson", "profile_background_color": "1A1B1F", "profile_background_tile": false, "profile_image_url": "https://si0.twimg.com/profile_images/1779632153/han_solo_star-wars_normal.jpg", "profile_link_color": "2FC2EF", "profile_sidebar_fill_color": "http://a0.twimg.com/images/themes/theme9/bg.gif", "profile_text_color": "666666", "protected": false, "screen_name": "TrevorBoyson", "statuses_count": 1861, "time_zone": "Pacific Time (US & Canada)", "url": "https://t.co/IT5hKQTt", "utc_offset": -28800}}"""))

    def testEmailTemplateVars(self):
        print self.tweet1.__dict__
        d = email_template_vars_from_tweet(self.tweet1)
        self.assertEqual(d['screen_name'], self.tweet1.user.screen_name)
        self.assertEqual(d['profile_link'], "https://twitter.com/TrevorBoyson")
        self.assertEqual(d['profile_image_url'],
                         self.tweet1.user.profile_image_url)
        link = "https://twitter.com/TrevorBoyson/status/352578986758512640"
        self.assertEqual(d['tweet_link'], link)


if __name__ == "__main__":
    """
Example:
python twitter_search.py -f ./since_id.txt -r "you@gmail.com" -q "aristotle"
    """
    import argparse
    parser = argparse.ArgumentParser("python twitter_search.py")
    parser.add_argument('-f', '--since_id_filename', required=True,
                        dest="since_id_filename", type=str,
                        help="Path to file storing max id of tweets emailed.")
    parser.add_argument('-r', '--recipients', required=True,
                        dest="recipients", type=str,
                        help="CSV of emails to notify about twitter search.")
    parser.add_argument('-q', '--query', dest="query", type=str,
                        help="Twitter search query.")

    args = parser.parse_args()

    api = twitter.Api(**settings.TWITTER_SETTINGS)

    search_and_email(api=api, query=args.query,
                     since_id_filename=args.since_id_filename,
                     recipients=args.recipients)
