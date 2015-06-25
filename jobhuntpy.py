# TODO: handle thread failure
# TODO: logging to console
# TODO: build up mac/windows GUI
# TODO: test cases

import argparse
import collections
import csv
import getpass
import json
import logging
import sys
import threading
import time
import re
import requests

from bs4 import BeautifulSoup
from sets import Set

LINKEDIN_ENDPOINT = 'https://www.linkedin.com/'
LINKEDIN_LOGIN_URL = 'https://www.linkedin.com/uas/login-submit'

INDEED_ENDPOINT = 'http://www.indeed.com/'

MOCK_BROWSER_AGENT = {
    'User-agent': 'Mozilla/5.0 (Windows; U; Windows NT 5.1; it; rv:1.8.1.11) Gecko/20071127 Firefox/2.0.0.11'
}

JobContainer = collections.namedtuple('JobContainer', ['link', 'title', 'company', 'location', 'time'])

# configure logger
logger = logging.getLogger('jobhuntpy')
logger.setLevel(logging.DEBUG)

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)

logger.addHandler(ch)


def parse_args():
    parser = argparse.ArgumentParser(
        description='We need your linkedin email and password to aggregate your data for you.')
    # args.keyword, args.city, args.state
    parser.add_argument('-e', '--email', type=str, help='The email you used to sign up in linkedin.')
    parser.add_argument('-k', '--keyword', type=str, help='The keyword you wish to appear in the matched jobs.')
    parser.add_argument('-c', '--city', type=str, help='The city you wish to work in.')
    parser.add_argument('-s', '--state', type=str, help='The state of the city, for example, CA for California.')

    return parser.parse_args()


def get_all_connections(email, password):
    client = requests.Session()

    html = client.get(LINKEDIN_ENDPOINT).content
    soup = BeautifulSoup(html)
    csrf = soup.find(id="loginCsrfParam-login")['value']

    login_information = {
        'session_key': email,
        'session_password': password,
        'loginCsrfParam': csrf,
    }

    client.post(LINKEDIN_LOGIN_URL, data=login_information, headers=MOCK_BROWSER_AGENT)

    query = 'contacts/api/contacts/more/?start=0&count=10'
    response = client.get('{}{}'.format(LINKEDIN_ENDPOINT, query), headers=MOCK_BROWSER_AGENT)

    connections_obj = response.json()

    logger.debug(json.dumps(connections_obj, indent=4))
    logger.info('Total Connection count: {}'.format(connections_obj['paging']['total']))

    query = 'contacts/api/contacts/more/?start=0&count={}&fields=id%2Cname%2Ccompany%2Ctitle%2Cgeo_location'.format(
        connections_obj['paging']['total'])
    response = client.get('{}{}'.format(LINKEDIN_ENDPOINT, query), headers=MOCK_BROWSER_AGENT, timeout=60)

    connections_obj = response.json()
    logger.debug(json.dumps(connections_obj, indent=4))

    return connections_obj['contacts']


def _parse_single_page_for_jobs(page_number, keyword, company, city, state, radius, result_jobs):

    page_url = '{}jobs?as_and={}&as_cmp={}&jt=all&radius={}&l={}%2C+{}&start={}'.format(
        INDEED_ENDPOINT, keyword, company, radius, city, state, page_number * 10)

    logger.debug('Scraping page: {}'.format(page_url))

    page_response_text = requests.get(page_url, headers=MOCK_BROWSER_AGENT).text
    page_response_soup = BeautifulSoup(page_response_text)

    job_hrefs = page_response_soup.find_all(class_='jobtitle')
    job_divs = map(lambda j: j.parent, job_hrefs)

    jobs = []

    for job_div in job_divs:

        link_tags = job_div.select('h2 a')
        job_link = '{}{}'.format(INDEED_ENDPOINT, link_tags[0]['href']) if len(link_tags) > 0 else None
        job_title = link_tags[0]['title'] if len(link_tags) > 0 else ''

        location_tag = job_div.select('span span span')
        job_location = location_tag[0].text if len(location_tag) > 0 else ''

        date_tag = job_div.select('span.date')
        job_time = date_tag[0].text if len(date_tag) > 0 else ''

        if job_link != '' and job_title != '':
            jobs.append(JobContainer(job_link, job_title, company, job_location, job_time))

    result_jobs.extend(jobs)


def get_all_indeed_jobs(keyword, company, city, state, radius=50):
    company = company.encode("utf-8")
    keyword = keyword.encode("utf-8")
    city = city.encode("utf-8")
    state = state.encode("utf-8")

    url = '{}jobs?as_and={}&as_cmp={}&jt=all&radius={}&l={}%2C+{}'.format(
        INDEED_ENDPOINT, keyword, company, radius, city, state)

    response_text = requests.get(url, headers=MOCK_BROWSER_AGENT).text
    response_soup = BeautifulSoup(response_text)

    # get page count
    all_job_count_str = response_soup.find(text=re.compile('Jobs \d+ to \d+ of \d+'))
    all_job_count = 0

    if all_job_count_str:
        all_job_count = int(all_job_count_str.split()[5])

    logger.info('Found {} related jobs at {} in {}'.format(all_job_count, company, city))

    all_jobs = []

    # thread out to get all the job posting in the pages
    if all_job_count != 0:
        page_counts = collections.deque(range(all_job_count / 10)) if all_job_count != 0 else [0]
        thread_pool = []

        # thread out to get jobs
        while len(page_counts) != 0 and len(thread_pool) == 0:

            # remove the done threads
            for t in thread_pool:
                if not t.isAlive():
                    thread_pool.remove(t)

            # spin of threads if thread count less than 10
            if len(thread_pool) < 10:
                args = (page_counts.pop(), keyword, company, city, state, radius, all_jobs)
                thread = threading.Thread(target=_parse_single_page_for_jobs, args=args)

                thread.setDaemon(True)
                thread_pool.append(thread)
                thread.start()

            time.sleep(1)

    return all_jobs


def connections_obj_to_csv(connections):
    headers = ['Company', 'Name', 'Title', 'Location']

    with open('connections.csv', 'wb') as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        for connection in connections:
            try:
                data = [
                    connection['company']['name'] if 'company' in connection and connection['company'] else '',
                    connection['name'] if 'name' in connection and connection['name'] else '',
                    connection['title'] if 'title' in connection and connection['title'] else '',
                    connection['geo_location']['name'] if 'geo_location' in connection and connection[
                        'geo_location'] else ''
                ]
                data = map(lambda d: d.encode("utf-8"), data)
                writer.writerow(data)

            except:
                logger.exception('Ignoring {}'.format(connection))

    logger.info('Linkedin connections exported.')


def jobs_obj_to_csv(jobs):
    headers = ['Company', 'Title', 'Location', 'URL', 'Time']

    with open('jobs.csv', 'wb') as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        for job in jobs:
            try:
                data = [job.company, job.title, job.location, job.link, job.time]
                data = map(lambda d: d.encode("utf-8"), data)
                writer.writerow(data)

            except:
                logger.exception('Ignoring {}'.format(job))

    logger.info('All current indeed jobs exported.')


def main():
    args = parse_args()

    print('Please type in your linkedin password.')

    password = getpass.getpass()

    connections = get_all_connections(args.email, password)
    connections_obj_to_csv(connections)

    companies = Set([])
    for connection in connections:
        if connection['company']:
            companies.add(connection['company']['name'])

    jobs = []
    for company in companies:
        jobs.extend(get_all_indeed_jobs(args.keyword, company, args.city, args.state))

    jobs_obj_to_csv(jobs)

    print('All done.')


if __name__ == '__main__':
    main()
