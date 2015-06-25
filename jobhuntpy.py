# TODO: handle thread failure
# TODO: thread up indeed scarping
# TODO: build up mac GUI
# TODO: test cases

import argparse
import collections
import csv
import getpass
import json
import logging
import threading
import time
import re
import requests

from bs4 import BeautifulSoup

LINKEDIN_ENDPOINT = 'https://www.linkedin.com/'
LINKEDIN_LOGIN_URL = 'https://www.linkedin.com/uas/login-submit'

INDEED_ENDPOINT = 'http://www.indeed.com/'

MOCK_BROWSER_AGENT = {
    'User-agent': 'Mozilla/5.0 (Windows; U; Windows NT 5.1; it; rv:1.8.1.11) Gecko/20071127 Firefox/2.0.0.11'
}

JobContainer = collections.namedtuple('JobContainer', ['link', 'title', 'company', 'location', 'time'])


def parse_args():
    parser = argparse.ArgumentParser(
        description='We need your linkedin email and password to aggregate your data for you.')
    parser.add_argument('-e', '--email', type=str, help='The email you used to sign up in linkedin.')

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

    logging.debug(json.dumps(connections_obj, indent=4))
    logging.info('Total Connection count: {}'.format(connections_obj['paging']['total']))

    query = 'contacts/api/contacts/more/?start=0&count={}&fields=id%2Cname%2Ccompany%2Ctitle%2Cgeo_location'.format(
        connections_obj['paging']['total'])
    response = client.get('{}{}'.format(LINKEDIN_ENDPOINT, query), headers=MOCK_BROWSER_AGENT, timeout=60)

    connections_obj = response.json()
    logging.debug(json.dumps(connections_obj, indent=4))

    return connections_obj['contacts']


def _parse_single_page_for_jobs(page_number, keyword, company, city, state, radius, result_jobs):

    page_url = '{}jobs?as_and={}&as_cmp={}&jt=all&radius={}&l={}%2C+{}&start={}'.format(
        INDEED_ENDPOINT, keyword, company, radius, city, state, page_number * 10)
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
    url = '{}jobs?as_and={}&as_cmp={}&jt=all&radius={}&l={}%2C+{}'.format(
        INDEED_ENDPOINT, keyword, company, radius, city, state)
    response_text = requests.get(url, headers=MOCK_BROWSER_AGENT).text
    response_soup = BeautifulSoup(response_text)

    # get page count
    all_job_count_str = response_soup.find(text=re.compile('Jobs \d+ to \d+ of \d+'))
    all_job_count = 0

    if all_job_count_str:
        all_job_count = int(all_job_count_str.split()[5])
    else:
        raise RuntimeError('Could not figure out the total job count.')

    all_jobs = [] # TODO: use thread safe queue here

    # thread out to get all the job posting in the pages
    if all_job_count != 0:
        page_counts = range(all_job_count / 10)
        thread_pool = []
        started = False

        # thread out to get jobs
        while not started and len(thread_pool) == 0:
            started = True

            # remove the done threads
            for t in thread_pool:
                if not t.isAlive():
                    thread_pool.remove(t)

            # spin of threads if thread count less than 10
            if len(thread_pool) < 10:
                thread = threading.Thread(
                    _parse_single_page_for_jobs,
                    args=(page_counts.next(), keyword, company, city, state, radius, all_jobs))

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

            except Exception, e:
                print(e.message)
                print('Ignoring {}'.format(connection))

    logging.info('Linkedin connections exported.')


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

            except Exception, e:
                print(e.message)
                print('Ignoring {}'.format(job))

    logging.info('All current indeed jobs exported.')


def main():
    args = parse_args()

    print('Please type in your linkedin password.')
    password = getpass.getpass()

    connections = get_all_connections(args.email, password)
    connections_obj_to_csv(connections)

    companies = collections.Set([])
    for connection in connections:
        companies += connection['company']

    jobs = []
    for company in companies:
        logging.info('Downloading all {} jobs from company {}'.format(args.keyword, company))
        jobs.extend(get_all_indeed_jobs(args.keyword, company, args.city, args.state))

    jobs_obj_to_csv(jobs)


if __name__ == '__main__':
    main()