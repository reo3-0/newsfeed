import pandas as pd
import os
import requests
import json
import feedparser
from datetime import datetime
import pytz
from bs4 import BeautifulSoup

def process_rss(source_url, source_name):
    # Tested with TNR
    # 0.430080 seconds with RSS (100 articles) --> nearly 100 times faster for MORE articles
    # 40.485987 seconds (57 articles)
    if 'feed' in source_url or '.xml' in source_url or 'rss' in source_url:
        source_url_rss = source_url
    else:
        source_url_rss = source_url + '/feed'
    feed = feedparser.parse(source_url_rss)
    list_of_articles_rows = []
    # Loop through articles
    for entry in feed.entries:
        title = entry.title
        url = entry.link
         # unpacks the list of date/time values and feeds it into datetime() 
         # then converts it from utc to eastern 
        published_date = datetime(*entry.published_parsed[:6]).replace(tzinfo=pytz.utc).astimezone(pytz.timezone('US/Eastern'))
        list_of_articles_rows.append([published_date, title, url, source_name])
    return list_of_articles_rows

def elie_rss():
    feed = feedparser.parse("https://www.thenation.com/feed/?post_type=article")
    list_of_articles_rows = []
    # Loop through articles
    for entry in feed.entries:
        if entry.author == 'Elie Mystal':
            title = entry.title
            url = entry.link
            # unpacks the list of date/time values and feeds it into datetime() 
            # then converts it from utc to eastern 
            published_date = datetime(*entry.published_parsed[:6]).replace(tzinfo=pytz.utc).astimezone(pytz.timezone('US/Eastern'))
            list_of_articles_rows.append([published_date, title, url, "Elie"])
    return list_of_articles_rows

def get_pub_date(url):
    resp = requests.get(url)
    soup = BeautifulSoup(resp.text, "html.parser")
    # #1 – look for <meta property="article:published_time">
    tag = soup.find("meta", {"property": "article:published_time"})
    if tag and tag.has_attr("content"):
        return tag["content"]
    # #2 – look for JSON-LD
    for script in soup.find_all("script", {"type":"application/ld+json"}):
        try:
            data = json.loads(script.string)
            # support list or dict
            for item in (data if isinstance(data, list) else [data]):
                if "datePublished" in item:
                    return item["datePublished"]
        except:
            continue
    return None

def archive_results(article_list_of_lists):
    archive = pd.read_csv('daily_news_archive.csv')

    # Turn the list of lists into a dataframe with uniform column naming 
    df_these_articles = pd.DataFrame(article_list_of_lists).rename(columns={0: "Publication Datetime", 1: "Headline", 2: "URL", 3: "Source"}) 
    df_these_articles['Publication Datetime'] = pd.to_datetime(df_these_articles['Publication Datetime']) #, utc=True , format='%y%m%d'
    df_these_articles.sort_values(by=['Publication Datetime'], ascending=False, inplace=True)
    df_these_articles['Publication Date'] = df_these_articles['Publication Datetime'].dt.date
    #print('A')

    # Suite to skip updating the archive if the newest URL is already in the archive. Trying to save computation, not sure if it's that helpful.
    first_row_of_new_scrape_exists_in_archive = ((archive == df_these_articles.iloc[0,]).all(axis=1)).any()
    if first_row_of_new_scrape_exists_in_archive:
        #print('B')
        pass
    else:
        # A trick to update the archive with whichever rows has the most complete data. 
        # If a row in the archive is missing a title and the new data has the title, it will keep the new data and drop the archive row
        new_archive = pd.concat([archive, df_these_articles]) #.drop_duplicates('URL').reset_index(drop=True)
        new_archive['missing_count'] = new_archive.isnull().sum(axis=1)
        new_archive.sort_values(by=['missing_count'], ascending = False, inplace=True)
        new_archive = new_archive.drop_duplicates('URL', keep = 'first').reset_index(drop=True)
        new_archive = new_archive.drop(['missing_count'], axis=1)
        #print('C')
        # Suite to MAKE SURE that the updated archive is at least as big as the existing archive
        if len(new_archive) < len(archive):
            print('Failed to update archive: Something is going wrong. Updated archive should never be fewer rows than old archive.')
            #print('D')
            pass
        else:
            print('E')
            new_archive.to_csv('daily_news_archive.csv', index=False)

def update_archive():
    archive_results(elie_rss())
    sources_dict = {"http://www.pewresearch.org/publications": 'Pew',
                    "https://newrepublic.com/rss.xml": 'The New Republic',
                    "http://api.axios.com": 'Axios',
                    "https://prospect.org/api/rss/content_full.rss": 'The American Prospect',
                    "https://newrepublic.com/rss.xml": "The New Republic",
                    "https://www.dropsitenews.com/feed": "Drop Site",
                    "https://www.thebignewsletter.com/feed": "BIG",
                    "https://www.sustainabilitybynumbers.com/feed":"Sustainability by numbers",
                    "https://www.kenklippenstein.com/feed":"Klippenstein",
                    "http://youngmenresearchinitiative.substack.com/feed":"Young Men Research Initiative",
                    "https://www.gelliottmorris.com/feed":"G. Elliot Morris",
                    "https://www.propublica.org/feeds/propublica/main": "ProPublica",
                    "https://jacobin.com/": "Jacobin"}
    for url, source_name in sources_dict.items():
        archive_results(process_rss(url, source_name))

update_archive()
