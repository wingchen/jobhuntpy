# TODO: thread up indeed scarping

import argparse
import csv
import getpass
import json
import logging
import requests

from bs4 import BeautifulSoup

LINKEDIN_ENDPOINT = 'https://www.linkedin.com/'
LINKEDIN_LOGIN_URL = 'https://www.linkedin.com/uas/login-submit'

INDEED_ENDPOINT = 'http://www.indeed.com/'

MOCK_BROWSER_AGENT = {
    'User-agent': 'Mozilla/5.0 (Windows; U; Windows NT 5.1; it; rv:1.8.1.11) Gecko/20071127 Firefox/2.0.0.11'
}


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


def get_all_indeed_related_jobs(driver, keyword, company, city, radius=50):
    pass


def connections_obj_to_csv(connections):
    headers = ['Company', 'Name', 'Title', 'location']

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


def main():
    args = parse_args()

    print('Please type in your linkedin password.')
    password = getpass.getpass()

    connections = get_all_connections(args.email, password)
    connections_obj_to_csv(connections)


if __name__ == '__main__':
    main()