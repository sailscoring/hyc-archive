
import os
import os.path
import urllib.parse
from lxml import html

URL_BASE = 'https://hyc.ie'
USERNAME = os.environ.get('ADMIN_USERNAME')
PASSWORD = os.environ.get('ADMIN_PASSWORD')

def login(session):
    result = session.get(URL_BASE + "/login")
    tree = html.fromstring(result.text)
    authenticity_token = tree.xpath("//input[@name='authenticity_token']/@value")[0]

    payload = {
        'authenticity_token': authenticity_token,
        'user_session[login]': USERNAME,
        'user_session[password]': PASSWORD,
    }

    return session.post(URL_BASE + "/login", data=payload)

def get_events(session, event_type, year):
    result = session.get(URL_BASE + "/admin/results/{}?event_type={}&year={}&&commit=Filter".format(event_type, event_type, year))
    tree = html.fromstring(result.text)
    return tree.xpath("//select[@id='event_title']/option/@value")

def get_edit_refs(session, event_type, year, event_title):
    result = session.get(URL_BASE + "/admin/results?event_title={}&event_type={}&year={}".format(urllib.parse.quote(event_title), event_type, year))
    tree = html.fromstring(result.text)
    return tree.xpath("//tr/td[3]/a[2]/@href")

def get_result(session, edit_ref):
    result = session.get(URL_BASE + edit_ref)
    tree = html.fromstring(result.text)
    try:
        ftp_path = tree.xpath("//input[@name='result[ftp_path]']/@value")[0]
    except IndexError:
        ftp_path = ''
    return {
        "id": edit_ref.split("/")[3],
        "event": tree.xpath("//input[@name='result[event_title]']/@value")[0],
        "class_name": tree.xpath("//input[@name='result[class_name]']/@value")[0],
        "ftp_path": ftp_path
    }

def update_ftp_path(session, edit_ref, ftp_path):
    result = session.get(URL_BASE + edit_ref)
    tree = html.fromstring(result.text)
    data = {}
    inputs = [ "utf8", "authenticity_token", "result[event_type]", "result[year]", "result[event_title]", "result[class_name]"]
    for i in inputs:
        data[i] = tree.xpath("//input[@name='{}']/@value".format(i))[0]
    data["result[ftp_path]"] = ftp_path
    edit_ref = edit_ref.replace("/edit", "")
    return session.put(URL_BASE + edit_ref, data=data)


def get_resources_page(session, url):
    resources = session.get(URL_BASE + url)
    tree = html.fromstring(resources.text)
    resources_hrefs = tree.xpath("//a[@class='inline_download_icon']/@href")
    next_hrefs = tree.xpath("//a[@rel='next']/@href")
    return (resources_hrefs, next_hrefs[0] if len(next_hrefs) > 0 else None)

def get_resources(session):
    resources_hrefs, next_url = get_resources_page(session, "/admin/resources")
    while next_url:
        hrefs, next_url = get_resources_page(session, next_url)
        resources_hrefs.extend(hrefs)
    return resources_hrefs

def get_file(session, url, directory):
    r = session.get(URL_BASE + url)
    filename = os.path.basename(url)
    if "?" in filename:
        filename = filename.split("?")[0]
    open(os.path.join(directory, filename), 'wb').write(r.content)
