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

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)

logger.addHandler(ch)


def parse_args():
    parser = argparse.ArgumentParser(
        description='jobhuntpy grab all the open jobs from indeed.com based on the keyword, ' +
                    'location your desire, and your linkedin connections.')

    parser.add_argument('email', type=str, help='The email you used to sign up in linkedin.')
    parser.add_argument('keyword', type=str, help='The keyword you wish to appear in the matched jobs.')
    parser.add_argument('city', type=str, help='The city you wish to work in.')
    parser.add_argument('state', type=str, help='The state of the city, for example, CA for California.')

    logger.info('Argument parsing successful.')

    return parser.parse_args()


def get_all_connections(email, password):
    '''
    Gets all the connection(friend) information from user's linkedin account.

    :param email:       (str), the email user used to sign up for her linkedin account
    :param password:    (str), the password to user's linkedin account
    :return:            (list), a list of user's connections from her linkedin account
    '''
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
    '''
    _parse_single_page_for_jobs is a private function used by get_all_indeed_jobs to extract
    the jobs from a single indeed.com's job search page.
    :return:
    '''
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
    '''
    Get all the available indeed jobs info with the passed-in parameter as criteria.

    :param keyword:     (str), the keyword used to match the jobs, exp: marketing, software engineering
    :param company:     (str), the company's name used to match the jobs, exp: Apple, google
    :param city:        (str), the city's full name where the job locates, exp: San Francisco, Santa Clara
    :param state:       (str), the state's short name where the job locates, exp: CA, WA
    :param radius:      (int), how far the job can be away from the designated city in miles, exp: 25, 50, 100
    :return:            list(JobContainer), the jobs extracted from indeed.com with the passed-in criteria
    '''
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
        page_counts = collections.deque(range(all_job_count / 10)) if all_job_count > 10 else [0]

        logger.debug('Page numbers to crawl: {}'.format(page_counts))

        thread_pool = []

        # thread out to get jobs
        while len(page_counts) != 0 or len(thread_pool) != 0:

            # remove the done threads
            for t in thread_pool:
                if not t.isAlive():
                    thread_pool.remove(t)

            # spin of threads if thread count less than 10
            if len(thread_pool) < 10 and len(page_counts) > 0:
                page = page_counts.pop()

                logger.debug('Threading out to get jobs in company {} for query page no. {}'.format(company, page))

                args = (page, keyword, company, city, state, radius, all_jobs)
                thread = threading.Thread(target=_parse_single_page_for_jobs, args=args)

                thread.setDaemon(True)
                thread_pool.append(thread)
                thread.start()

            time.sleep(1)

    return all_jobs


def connections_obj_to_csv(connections):
    '''
    Writes a list of user's linkedin connection into a csv file.

    :param connections:     (list), the linkedin connections the user has in her linkedin account
    :return:
    '''
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
    '''
    Writes a list to JobContainer into a csv file.

    :param jobs:    list(JobContainer), the jobs extracted from indeed.com.
    '''
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
