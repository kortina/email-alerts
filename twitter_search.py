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
import urllib




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
      s = text or ''
      s = str(s)
      reg = re.compile(r'(?P<entire_link>(?P<host_and_path>https?\:\/\/[^\s\?\<\>]+)(?P<qs>\?[^\s\<\>]+)?)', re.I)
      if hide_query_strings:
          s = reg.subn(r'<a href="\g<entire_link>">\g<host_and_path></a>', s)[0]
      else:
          s = reg.subn(r'<a href="\g<entire_link>">\g<entire_link></a>', s)[0]
      return s

def linkify_tweet(tweet, linkify_hyperlinks=True):
    if linkify_hyperlinks:
        tweet = replace_plain_links_with_anchor_tags(tweet, hide_query_strings=False)
    tweet = re.sub(r'(\A|\s)@(\w+)',
                   r'\1@<a href="http://www.twitter.com/\2">\2</a>',
                   tweet)
    return re.sub(r'(\A|\s)#(\w+)',
                  r'\1#<a href="http://search.twitter.com/search?q=%23\2">\2</a>',
                  tweet)

def email_template_vars_from_tweet(status):
    """
    Params:
    @tweet dict: parsed JSON for a tweet

    Returns:
    dict of info from the tweet formatted for email template
    """
    d = {}
    d['screen_name'] = smart_str(status.user.screen_name)
    d['profile_image_url'] = smart_str(status.user.profile_image_url)
    d['profile_link'] = "https://twitter.com/%s" % smart_str(status.user.screen_name)
    d['tweet_link'] = "https://twitter.com/%s/status/%s" % (
            smart_str(status.user.screen_name), status.id )
    # parsed_time =  time.strptime(status.created_at, "%a, %d %b %Y %H:%M:%S +0000")
    d['tweet_text'] = smart_str(status.text)
    d['created_at'] = smart_str(status.created_at)
    d['created_at'] = re.sub(r" \+.*$", "", d['created_at'])
    d['created_at'] = re.sub(r":\d\d$", "", d['created_at'])
    d['tweet_id'] = status.id
    d['subject'] = '@' +  d['screen_name'] + ':' + ' ' + d['tweet_text']
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
    <td style="vertical-align:top;" width="25">
        <a href="%(profile_link)s"><img  style="width:48px; height:48px;" src="%(profile_image_url)s" /> 
    </td>
    <td style="vertical-align:top;" width="400">
        %(tweet_text)s
        <br /><br /><br />
        <a href="%(profile_link)s">@%(screen_name)s</a> - 
        <a href="http://twitter.com/home?status=d %(screen_name)s+">DM</a>
        <br /><br /><a href="%(tweet_link)s">%(tweet_link)s</a>
    </td>
    <td width="200" style="vertical-align:top;">
        %(created_at)s
        <br /><a href="%(profile_link)s">%(screen_name)s</a>
        <br />%(name)s
        <br />%(description)s
        <br />
        <br />Followers: %(followers_count)s
        <br />Friends: %(friends_count)s
        <br />Favs: %(favourites_count)s
        <br />Updates: %(statuses_count)s
    </td>
    </tr>
    </table>
    <br /><br />
    """ % subs
    
    html= '<html><body>' + html + '</body></html>'
    
    text = """Author Screenname: %(screen_name)s
    Time: %(created_at)s
    Tweet: %(tweet_text)s
    Link to author's pg: %(profile_link)s
    Link to reply: http://twitter.com/home?status=@%(screen_name)s+">
    """ % template_vars
    return {"html": html, "text": text}




# Store max id we have seen in a file.
# The following methods read from and write to that file.
def format_max_id_filename(max_id_filename):
    return re.sub(r"[\s\'\"]", "_", max_id_filename)

def write_max_id_to_file(max_id_filename, max_id):
    max_id_filename = format_max_id_filename(max_id_filename)
    f = open(max_id_filename, 'w')
    f.write(smart_str(max_id))
    f.close()

def get_max_id(max_id_filename):
    max_id = 0
    max_id_filename = format_max_id_filename(max_id_filename)

    # Ensure file exists
    f = open(max_id_filename, 'a')
    f.close()

    f = open(max_id_filename, 'r')
    line = f.readline()
    f.close()

    line = line.strip()
    if (line  == ''):
        max_id = 0
    else:
        max_id = line

    return long(max_id)

def search_and_email(api, query, max_id_filename, recipients, count=100):
    """
    Params:
    @api twitter.Api: client instance
    @query str: search query for twitter
    @max_id_filename str: file where we store max id we have seen in this search and emailed about. (cursor)
    @recipients str: CSV of emails to notify about tweet
    @count int: max number of tweets to send

    Side Effects:
    Writes to max_id_filename updating the cursor so we don't email about the same tweet 2x.

    """
    max_id = get_max_id(max_id_filename)

    tweets =  api.GetSearch(term=query, max_id=max_id, count=count)
    tweets.sort(key=lambda x: x.id) # ensure tweets are sorted oldest => newest
    for tweet in tweets:
        email_vars = email_template_vars_from_tweet(tweet)
        body = email_body(email_vars)
        email_tweet(to=recipients, subject=email_vars['subject'],
                text=body['text'],
                html=body['html'])
        # mark this tweet as done
        write_max_id_to_file(max_id_filename, tweet.id)


def email_tweet(to, subject, text, html=None):
    gmailer.GMAIL_SETTINGS['user'] = settings.GMAIL_USER
    gmailer.GMAIL_SETTINGS['password'] = settings.GMAIL_PASSWORD
    gmailer.mail(to=to, subject=subject, text=text, html=html)
    

class TestSearch(unittest.TestCase):
    import simplejson
    tweet1 = twitter.Status.NewFromJsonDict(simplejson.loads("""{"created_at": "Thu Jul 04 00:05:55 +0000 2013", "favorited": false, "id": 352578986758512640, "retweeted": false, "source": "<a href=\\"https://venmo.com\\" rel=\\"nofollow\\">Venmo</a>", "text": "Just charged gabrielle-smith - Fireworks https://t.co/8ba4Tr1iet", "truncated": false, "urls": {"https://t.co/8ba4Tr1iet": "https://venmo.com/s/gHdI"}, "user": {"created_at": "Tue Jan 24 22:16:48 +0000 2012", "description": "Restless. Nomad.", "favourites_count": 40, "followers_count": 81, "friends_count": 621, "geo_enabled": true, "id": 473365277, "lang": "en", "location": "Walla Walla", "name": "Trevor Boyson", "profile_background_color": "1A1B1F", "profile_background_tile": false, "profile_image_url": "https://si0.twimg.com/profile_images/1779632153/han_solo_star-wars_normal.jpg", "profile_link_color": "2FC2EF", "profile_sidebar_fill_color": "http://a0.twimg.com/images/themes/theme9/bg.gif", "profile_text_color": "666666", "protected": false, "screen_name": "TrevorBoyson", "statuses_count": 1861, "time_zone": "Pacific Time (US & Canada)", "url": "https://t.co/IT5hKQTt", "utc_offset": -28800}}"""))

    def testEmailTemplateVars(self):
        print self.tweet1.__dict__
        d = email_template_vars_from_tweet(self.tweet1)
        self.assertEqual(d['screen_name'], self.tweet1.user.screen_name)
        self.assertEqual(d['profile_link'], "https://twitter.com/TrevorBoyson")
        self.assertEqual(d['profile_image_url'], self.tweet1.user.profile_image_url)
        self.assertEqual(d['tweet_link'], "https://twitter.com/TrevorBoyson/status/352578986758512640")
        # import pdb; pdb.set_trace()


if __name__ == "__main__":
    """
Example:
python twitter_search.py -f ./maxid1 -r "you@gmail.com" -q "aristotle"
    """
    import argparse
    parser = argparse.ArgumentParser("python twitter_search.py")
    parser.add_argument('-f','--max_id_filename', required=True, dest="max_id_filename", type=str,
                        help="Path to file storing max id of tweets alreadyemailed.")
    parser.add_argument('-r','--recipients', required=True, dest="recipients", type=str,
                        help="CSV of emails to notify about twitter search.")
    parser.add_argument('-q','--query', dest="query", type=str,
                        help="Twitter search query.")

    args = parser.parse_args()

    api = twitter.Api(**settings.TWITTER_SETTINGS)

    search_and_email(api=api, query=args.query,
            max_id_filename=args.max_id_filename, recipients=args.recipients)
